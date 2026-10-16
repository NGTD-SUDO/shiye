"""搜索 API 路由：关键词全文搜索（可按学科过滤）"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.deps import get_current_user
from app.services.search_service import search

router = APIRouter(prefix="/search", tags=["搜索"])


@router.get("")
def search_pages(
    q: str = Query(..., min_length=1, max_length=100, description="搜索关键词"),
    subject_id: int | None = None,
    page: int = 1,
    size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not q.strip():
        raise HTTPException(status_code=422, detail="搜索关键词不能为空")
    return search(db, user.id, q, subject_id=subject_id, page=page, size=size)
