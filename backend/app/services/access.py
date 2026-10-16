"""资源归属与存在性校验：跨路由复用的 404/403 守卫"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.page import Page
from app.models.subject import Subject


def require_subject(db: Session, user_id: int, subject_id: int) -> Subject:
    obj = db.get(Subject, subject_id)
    if not obj or obj.user_id != user_id:
        raise HTTPException(status_code=404, detail="学科不存在")
    return obj


def require_chapter(db: Session, user_id: int, subject_id: int, chapter_id: int) -> Chapter:
    obj = db.get(Chapter, chapter_id)
    if not obj or obj.subject_id != subject_id:
        raise HTTPException(status_code=404, detail="章不存在")
    require_subject(db, user_id, subject_id)
    return obj


def require_page(db: Session, user_id: int, page_id: int) -> Page:
    obj = db.get(Page, page_id)
    if not obj or obj.user_id != user_id:
        raise HTTPException(status_code=404, detail="笔记页不存在")
    return obj
