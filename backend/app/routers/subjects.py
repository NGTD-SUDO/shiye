"""学科 API 路由：CRUD + 页数统计 + 级联删除"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.page import Page
from app.models.subject import Subject
from app.models.user import User
from app.routers.deps import get_current_user
from app.schemas.subject import SubjectCreate, SubjectUpdate
from app.services import fts, storage_service
from app.services.access import require_subject

router = APIRouter(prefix="/subjects", tags=["学科"])


def _subject_dict(subject: Subject, page_count: int, done_count: int, chapter_count: int) -> dict:
    return {
        "id": subject.id,
        "name": subject.name,
        "color": subject.color,
        "icon": subject.icon,
        "sort_order": subject.sort_order,
        "page_count": page_count,
        "done_count": done_count,
        "chapter_count": chapter_count,
        "created_at": subject.created_at.isoformat(),
    }


def _load_counts(db: Session, user_id: int) -> tuple[dict[int, tuple[int, int]], dict[int, int]]:
    """一次聚合：{subject_id: (total, done)} 与 {subject_id: chapter_count}"""
    page_rows = db.execute(
        text(
            "SELECT subject_id, COUNT(*) AS total, "
            "SUM(CASE WHEN ocr_state = 'done' THEN 1 ELSE 0 END) AS done "
            "FROM pages WHERE user_id = :uid GROUP BY subject_id"
        ),
        {"uid": user_id},
    ).mappings().all()
    chapter_rows = db.execute(
        text("SELECT subject_id, COUNT(*) AS cnt FROM chapters GROUP BY subject_id")
    ).mappings().all()

    page_map: dict[int, tuple[int, int]] = {}
    for row in page_rows:
        page_map[row["subject_id"]] = (int(row["total"]), int(row["done"] or 0))
    chapter_map = {row["subject_id"]: int(row["cnt"]) for row in chapter_rows}
    return page_map, chapter_map


@router.get("")
def list_subjects(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subjects = (
        db.query(Subject)
        .filter(Subject.user_id == user.id)
        .order_by(Subject.sort_order, Subject.id)
        .all()
    )
    page_map, chapter_map = _load_counts(db, user.id)
    return [
        _subject_dict(s, *page_map.get(s.id, (0, 0)), chapter_map.get(s.id, 0))
        for s in subjects
    ]


@router.post("", status_code=201)
def create_subject(
    req: SubjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exists = (
        db.query(Subject)
        .filter(Subject.user_id == user.id, Subject.name == req.name.strip())
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="已存在同名学科")

    max_order = (
        db.query(Subject)
        .filter(Subject.user_id == user.id)
        .order_by(Subject.sort_order.desc())
        .first()
    )
    subject = Subject(
        user_id=user.id,
        name=req.name.strip(),
        color=req.color,
        icon=req.icon,
        sort_order=(max_order.sort_order + 1) if max_order else 0,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return _subject_dict(subject, 0, 0, 0)


@router.patch("/{subject_id}")
def update_subject(
    subject_id: int,
    req: SubjectUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = require_subject(db, user.id, subject_id)

    fields = req.model_fields_set
    if "name" in fields:
        new_name = req.name.strip()
        dup = (
            db.query(Subject)
            .filter(Subject.user_id == user.id, Subject.name == new_name, Subject.id != subject.id)
            .first()
        )
        if dup:
            raise HTTPException(status_code=409, detail="已存在同名学科")
        subject.name = new_name
    if "color" in fields:
        subject.color = req.color
    if "icon" in fields:
        subject.icon = req.icon
    if "sort_order" in fields:
        subject.sort_order = req.sort_order

    db.commit()
    db.refresh(subject)
    page_map, chapter_map = _load_counts(db, user.id)
    return _subject_dict(subject, *page_map.get(subject.id, (0, 0)), chapter_map.get(subject.id, 0))


@router.delete("/{subject_id}")
def delete_subject(
    subject_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除学科：其下所有章与页一并删除，页的图片文件与索引同步清理"""
    subject = require_subject(db, user.id, subject_id)

    pages = (
        db.query(Page)
        .filter(Page.subject_id == subject.id, Page.user_id == user.id)
        .all()
    )
    for page in pages:
        fts.delete_page(db, page.id)
        storage_service.delete_keys([page.image_key, page.thumb_key])
    db.delete(subject)  # 级联删除 chapters/pages
    db.commit()
    return {"ok": True}
