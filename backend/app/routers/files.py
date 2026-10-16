"""图片文件 API：原图/缩略图访问（签名 URL 优先，JWT 兜底，仅本人目录）

鉴权双通道：
- 请求带 e + s 查询参数且 verify() 通过 → 放行（不需要 JWT）
- 没有签名参数 → 走 JWT 通道（user 必须非 None，否则 401）
- 签名参数存在但校验失败/过期 → 403
- 无论哪条通道，key 必须以 {user_id}/ 开头，越权一律按 404 返回

安全语义（必须留档）：
- 签名 URL **持有即授权**——15 分钟内任何人拿到链接均可访问对应图片，
  不需要 JWT、不校验当前请求者身份。这等同 S3 预签名 URL 的取舍。
- 签名绑定 owner_id + key + exp，换 key / 换用户都会 403。
- 泄露应对：(1) 缩短 FILE_URL_TTL_SECONDS；(2) 前端刷新列表即拿新签名、
  旧签名自然过期失效；(3) 后续可叠加 IP / 设备绑定增强。
- JWT 通道保留归属校验（key.startswith(user.id)），越权返回 404 不泄露存在性。
"""
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services import storage_service
from app.services.auth_service import get_user_by_token
from app.services.file_signing import verify as verify_signature

router = APIRouter(prefix="/files", tags=["文件"])

# 可选 Bearer：缺凭据返回 None（不抛 401），让签名通道有机会放行
_optional_security = HTTPBearer(auto_error=False)


def _optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_security),
    db: Session = Depends(get_db),
) -> User | None:
    """解析 JWT；无凭据或 token 无效均返回 None（交由路由决定 401 还是走签名）"""
    if credentials is None:
        return None
    try:
        return get_user_by_token(db, credentials.credentials)
    except Exception:
        return None


def _owner_id_from_key(key: str) -> int | None:
    """从 key 提取归属用户 id（形如 {user_id}/{文件名}）"""
    head = key.split("/", 1)[0]
    try:
        return int(head)
    except ValueError:
        return None


@router.get("/{key:path}")
def get_file(
    key: str,
    e: str | None = Query(default=None),
    s: str | None = Query(default=None),
    user: User | None = Depends(_optional_user),
):
    """按存储 key 取图；签名 URL 优先，JWT 兜底

    - 签名通道：有 e+s 且 verify 通过 → 放行（key 归属已由签名绑定 owner_id+key 保证）
    - JWT 通道：无签名时 user 必须非 None，且 key 必须以 {user.id}/ 开头
    - 无任何凭据（无签名、无 Bearer）→ 401
    """
    has_sig = e is not None and s is not None

    if has_sig:
        owner_id = _owner_id_from_key(key)
        if owner_id is None:
            raise HTTPException(status_code=404, detail="文件不存在")
        if not verify_signature(key, owner_id, e, s):
            raise HTTPException(status_code=403, detail="图片链接已过期或失效，请刷新")
        # 签名通过：key 归属已由签名（绑定 owner_id + key + exp）保证，放行
    else:
        # 无签名参数 → 必须走 JWT
        if user is None:
            raise HTTPException(status_code=401, detail="未登录")
        if not key.startswith(f"{user.id}/"):
            raise HTTPException(status_code=404, detail="文件不存在")

    try:
        path: Path = storage_service.path_for(key)
    except ValueError:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)
