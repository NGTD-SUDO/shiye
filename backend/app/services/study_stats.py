"""学情统计纯函数（T5-1）

从真实数据计算统计，绝不硬编码任何数字。无副作用，可单测。
0 页也返回结构完整的 stats（各计数为 0），不抛异常。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.page import OCR_DONE, OCR_FAILED, OCR_PROCESSING, Page
from app.models.subject import Subject

# 失败页列表上限（用于提示「需重拍/重试」）
FAILED_PAGES_LIMIT = 10
# 很久没新增页的学科列表上限
STALE_SUBJECTS_LIMIT = 5
# 判定「很久没新增」的天数阈值
STALE_DAYS = 7
# 近 30 天趋势的天数（T9-5：payload 侧日期映射依赖此契约，见 app/ai/service.py::_trend_lines）
TREND_DAYS = 30


def _as_utc(dt: datetime | None) -> datetime | None:
    """统一转 UTC；naive 视为 UTC"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    """datetime -> ISO 字符串；None -> None"""
    dt = _as_utc(dt)
    return dt.isoformat() if dt else None


def compute_stats(
    db: Session,
    user_id: int,
    subject_id: int | None = None,
    now: datetime | None = None,
) -> dict:
    """计算学情统计（无副作用，可单测）。

    Args:
        db: 数据库会话
        user_id: 当前用户 id
        subject_id: 可选，只统计该学科
        now: 可选，「今天」锚点（测试传固定值；默认当前 UTC 时间）
    """
    if now is None:
        now = datetime.now(timezone.utc)
    today = now.date()

    # 页查询：按 user 过滤，可选 subject
    page_q = db.query(Page).filter(Page.user_id == user_id)
    if subject_id is not None:
        page_q = page_q.filter(Page.subject_id == subject_id)
    pages = page_q.all()

    total_pages = len(pages)
    ocr_done = sum(1 for p in pages if p.ocr_state == OCR_DONE)
    ocr_failed = sum(1 for p in pages if p.ocr_state == OCR_FAILED)
    ocr_processing = sum(1 for p in pages if p.ocr_state == OCR_PROCESSING)
    # total 为 0 时 0.0，避免除零 NaN
    done_ratio = (ocr_done / total_pages) if total_pages else 0.0

    # 近 30 天趋势：固定 TREND_DAYS 个元素，日期连续升序，含今天；无数据日期补 0
    trend = [0] * TREND_DAYS
    for p in pages:
        d = _as_utc(p.created_at).date()
        days_ago = (today - d).days
        if 0 <= days_ago < TREND_DAYS:
            trend[TREND_DAYS - 1 - days_ago] += 1

    # 学科分组
    subj_q = db.query(Subject).filter(Subject.user_id == user_id)
    if subject_id is not None:
        subj_q = subj_q.filter(Subject.id == subject_id)
    subjects_all = subj_q.order_by(Subject.id).all()

    pages_by_subject: dict[int, list[Page]] = {}
    for p in pages:
        pages_by_subject.setdefault(p.subject_id, []).append(p)

    subjects = []
    stale_names = []
    for s in subjects_all:
        sp = pages_by_subject.get(s.id, [])
        sp_done = sum(1 for p in sp if p.ocr_state == OCR_DONE)
        last = max((p.created_at for p in sp), default=None)
        subjects.append({
            "subject_id": s.id,
            "name": s.name,
            "page_count": len(sp),
            "done_ratio": (sp_done / len(sp)) if sp else 0.0,
            "last_page_at": _iso(last),
        })
        # ≥7 天没新增页（有页但最后一页距今 ≥7 天）→ stale；0 页不算（无学习记录可判断）
        if sp and last is not None and (now - _as_utc(last)) >= timedelta(days=STALE_DAYS):
            stale_names.append(s.name)

    chapters = _build_chapters(db, subjects_all, pages)

    failed_pages = [
        {"page_id": p.id, "title": p.title or "(无标题)"}
        for p in pages
        if p.ocr_state == OCR_FAILED
    ][:FAILED_PAGES_LIMIT]

    return {
        "total_pages": total_pages,
        "ocr_done": ocr_done,
        "ocr_failed": ocr_failed,
        "ocr_processing": ocr_processing,
        "done_ratio": done_ratio,
        "days_30_trend": trend,
        "subjects": subjects,
        "chapters": chapters,
        "failed_pages": failed_pages,
        "stale_subjects": stale_names[:STALE_SUBJECTS_LIMIT],
        # 页标题列表（供 AI 报告 payload 组装，成本控制用；原始未截断）
        "page_titles": [p.title for p in pages],
    }


def _build_chapters(db: Session, subjects_all: list[Subject], pages: list[Page]) -> list[dict]:
    """章分组（含「未分章」桶：chapter_id=None 的页）。0 页时返回空列表。"""
    if not pages:
        return []

    subj_ids = [s.id for s in subjects_all]
    chapters_all = (
        db.query(Chapter).filter(Chapter.subject_id.in_(subj_ids)).order_by(Chapter.id).all()
        if subj_ids
        else []
    )

    pages_by_chapter: dict[int, list[Page]] = {}
    unassigned_count = 0
    unassigned_last: datetime | None = None
    for p in pages:
        if p.chapter_id is None:
            unassigned_count += 1
            if unassigned_last is None or _as_utc(p.created_at) > unassigned_last:
                unassigned_last = _as_utc(p.created_at)
        else:
            pages_by_chapter.setdefault(p.chapter_id, []).append(p)

    result = [
        {
            "chapter_id": None,
            "name": "未分章",
            "page_count": unassigned_count,
            "last_page_at": _iso(unassigned_last),
        }
    ]
    for c in chapters_all:
        cp = pages_by_chapter.get(c.id, [])
        last = max((p.created_at for p in cp), default=None)
        result.append({
            "chapter_id": c.id,
            "name": c.name,
            "page_count": len(cp),
            "last_page_at": _iso(last),
        })
    return result
