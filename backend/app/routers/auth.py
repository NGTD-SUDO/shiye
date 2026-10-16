"""认证 API 路由：微信登录 + 开发模式登录 + 我的信息 + 注销账号"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.page import Page
from app.models.user import User
from app.routers.deps import get_current_user
from app.schemas.auth import (
    DevLoginRequest,
    TokenResponse,
    UpdateMeRequest,
    WechatLoginRequest,
)
from app.services import fts, storage_service
from app.services.auth_service import dev_login, wechat_login

router = APIRouter(prefix="/auth", tags=["认证"])


def _user_response(user: User) -> dict:
    return {
        "id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url or "",
        "created_at": user.created_at.isoformat(),
    }


@router.post("/wechat", response_model=TokenResponse)
def wechat_auth(req: WechatLoginRequest, db: Session = Depends(get_db)):
    """微信授权登录：App 拿到 code 后调用"""
    return wechat_login(db, req.code)


@router.post("/dev-login", response_model=TokenResponse)
def dev_auth(req: DevLoginRequest, db: Session = Depends(get_db)):
    """开发模式免登通道（仅 SHIYE_DEV_MODE=true 时可用）

    若后端配置了 INVITE_CODE，必须带 invite_code 参数。
    """
    return dev_login(db, req.openid, req.nickname, req.invite_code)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _user_response(user)


@router.patch("/me")
def update_me(req: UpdateMeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.nickname is not None:
        user.nickname = req.nickname.strip() or user.nickname
    if req.avatar_url is not None:
        user.avatar_url = req.avatar_url or None
    db.commit()
    db.refresh(user)
    return _user_response(user)


@router.delete("/me")
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """注销账号（T12-6）：删除该用户**全部数据 + 图片文件物理删除**

    履行隐私政策 6.4「注销账号」承诺（删除权）。删除范围：
    - 数据库：`pages` / `chapters` / `subjects` / `users`（模型已声明 `cascade="all, delete-orphan"`）
    - 搜索索引：逐页删除 `pages_fts` 行（否则会留下指向已删页的索引）
    - 文件：每页的 `image_key` / `thumb_key` **物理删除**（不是只删库 —— 那是假删除）
    - 该用户 token 随之失效：用户记录不存在 → 后续请求 401

    只删自己（`user.id` 来自 token），不存在跨用户删除。
    """
    pages = db.query(Page).filter(Page.user_id == user.id).all()
    keys: list[str | None] = []
    for page in pages:
        fts.delete_page(db, page.id)
        keys.extend([page.image_key, page.thumb_key])

    # 先删文件再删库：即便后续 commit 失败，也不会出现「库没了、图还在」
    storage_service.delete_keys(keys)

    db.delete(user)  # 级联删除 subjects → chapters / pages
    db.commit()
    return {"ok": True}
