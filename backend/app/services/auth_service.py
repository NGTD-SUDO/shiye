"""认证业务逻辑：JWT、微信登录、开发模式登录"""
import hmac
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    DEV_MODE,
    INVITE_CODE,
    SECRET_KEY,
    WECHAT_APPID,
    WECHAT_SECRET,
)
from app.models.user import User

WECHAT_OAUTH_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
WECHAT_USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"

_logger = logging.getLogger(__name__)


def create_access_token(user_id: int) -> str:
    """签发 JWT 令牌"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    """解析 JWT，返回 user_id；无效抛 401"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效")
        return int(user_id)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效")


def _find_or_create_wechat_user(
    db: Session, openid: str, unionid: str | None, nickname: str, avatar_url: str
) -> User:
    """按 openid/unionid 查找用户，否则创建"""
    user = db.query(User).filter(User.wechat_openid == openid).first()
    if not user and unionid:
        user = db.query(User).filter(User.wechat_unionid == unionid).first()
    if user:
        if nickname and user.nickname == "拾页用户":
            user.nickname = nickname
        return user

    user = User(
        wechat_openid=openid,
        wechat_unionid=unionid,
        nickname=nickname or "拾页用户",
        avatar_url=avatar_url or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _token_payload(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user_id": user.id,
        "nickname": user.nickname,
    }


def wechat_login(db: Session, code: str) -> dict:
    """微信授权登录：code → 微信用户信息 → 创建/查找用户 → 返回 JWT"""
    if not WECHAT_APPID or not WECHAT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="服务端未配置微信登录（SHIYE_WECHAT_APPID/SECRET）",
        )

    import httpx

    # ① code 换 access_token + openid
    with httpx.Client(timeout=10) as client:
        resp = client.get(
            WECHAT_OAUTH_URL,
            params={
                "appid": WECHAT_APPID,
                "secret": WECHAT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        token_data = resp.json()
    if "errcode" in token_data and token_data["errcode"] != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"微信授权失败: {token_data.get('errmsg', '未知错误')}",
        )
    openid = token_data.get("openid")
    unionid = token_data.get("unionid")
    access_token = token_data.get("access_token")
    if not openid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="微信授权失败：未获取到 openid")

    # ② 取昵称头像
    nickname = "微信用户"
    avatar_url = ""
    if access_token:
        with httpx.Client(timeout=10) as client:
            resp = client.get(WECHAT_USERINFO_URL, params={"access_token": access_token, "openid": openid})
            info = resp.json()
        if "errcode" not in info or info["errcode"] == 0:
            nickname = info.get("nickname") or nickname
            avatar_url = info.get("headimgurl", "")

    user = _find_or_create_wechat_user(db, openid, unionid, nickname, avatar_url)
    db.commit()
    return _token_payload(user)


def dev_login(db: Session, openid: str, nickname: str | None, invite_code: str | None = None) -> dict:
    """开发模式免登通道：仅 SHIYE_DEV_MODE=true 时开放

    邀请码校验顺序（不可变）：
    1. 先判 DEV_MODE（未开启 → 403「开发模式未开启」）
    2. 若 INVITE_CODE 非空 → 必须校验 invite_code（hmac.compare_digest 常量时间比较，不匹配 → 403「邀请码无效」）
    3. 若 INVITE_CODE 为空 → 保持现有行为（本地开发免码）

    INVITE_CODE 与用户提交值都不进日志。
    """
    if not DEV_MODE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="开发模式未开启")

    # 邀请码校验（仅当后端配置了 INVITE_CODE 时）
    if INVITE_CODE:
        if not invite_code or not hmac.compare_digest(str(invite_code), INVITE_CODE):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="邀请码无效")

    openid = openid.strip()
    if not openid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="openid 不能为空")
    user = _find_or_create_wechat_user(db, openid, None, nickname or "拾页用户", "")
    db.commit()
    return _token_payload(user)


def get_user_by_token(db: Session, token: str) -> User:
    """根据 JWT 取用户，供依赖注入

    T12-6：用户记录不存在（含**账号已注销**）一律 **401** —— 此时令牌已不代表任何有效账号，
    属「未认证」而非「资源不存在」，前端据此清 token 回登录页。
    """
    user_id = decode_access_token(token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或账号已注销",
        )
    return user
