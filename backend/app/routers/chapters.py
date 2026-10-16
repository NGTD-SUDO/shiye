"""章 API 路由（学科下二级分组）：CRUD，删除章时页保留、归入未分章"""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.service import organize_text
from app.database import get_db
from app.models.chapter import Chapter
from app.models.chapter_organization import ChapterOrganization
from app.models.page import Page
from app.models.user import User
from app.routers.deps import get_current_user
from app.routers.pages import get_ai_provider_dep
from app.schemas.chapter import ChapterCreate, ChapterUpdate
from app.services import export_service
from app.services.access import require_chapter, require_subject

router = APIRouter(prefix="/subjects/{subject_id}/chapters", tags=["章"])


def _chapter_dict(chapter: Chapter, page_count: int) -> dict:
    return {
        "id": chapter.id,
        "subject_id": chapter.subject_id,
        "name": chapter.name,
        "sort_order": chapter.sort_order,
        "page_count": page_count,
        "created_at": chapter.created_at.isoformat(),
    }


def _load_page_counts(db: Session, subject_id: int) -> dict[int, int]:
    rows = db.execute(
        text(
            "SELECT chapter_id, COUNT(*) AS cnt FROM pages "
            "WHERE subject_id = :sid AND chapter_id IS NOT NULL GROUP BY chapter_id"
        ),
        {"sid": subject_id},
    ).mappings().all()
    return {row["chapter_id"]: int(row["cnt"]) for row in rows}


@router.get("")
def list_chapters(
    subject_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_subject(db, user.id, subject_id)
    chapters = (
        db.query(Chapter)
        .filter(Chapter.subject_id == subject_id)
        .order_by(Chapter.sort_order, Chapter.id)
        .all()
    )
    counts = _load_page_counts(db, subject_id)
    return [_chapter_dict(c, counts.get(c.id, 0)) for c in chapters]


@router.post("", status_code=201)
def create_chapter(
    subject_id: int,
    req: ChapterCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_subject(db, user.id, subject_id)
    dup = (
        db.query(Chapter)
        .filter(Chapter.subject_id == subject_id, Chapter.name == req.name.strip())
        .first()
    )
    if dup:
        raise HTTPException(status_code=409, detail="学科下已存在同名章")
    max_order = (
        db.query(Chapter)
        .filter(Chapter.subject_id == subject_id)
        .order_by(Chapter.sort_order.desc())
        .first()
    )
    chapter = Chapter(
        subject_id=subject_id,
        name=req.name.strip(),
        sort_order=(max_order.sort_order + 1) if max_order else 0,
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return _chapter_dict(chapter, 0)


@router.patch("/{chapter_id}")
def update_chapter(
    subject_id: int,
    chapter_id: int,
    req: ChapterUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chapter = require_chapter(db, user.id, subject_id, chapter_id)
    fields = req.model_fields_set
    if "name" in fields:
        dup = (
            db.query(Chapter)
            .filter(
                Chapter.subject_id == subject_id,
                Chapter.name == req.name.strip(),
                Chapter.id != chapter.id,
            )
            .first()
        )
        if dup:
            raise HTTPException(status_code=409, detail="学科下已存在同名章")
        chapter.name = req.name.strip()
    if "sort_order" in fields:
        chapter.sort_order = req.sort_order
    db.commit()
    db.refresh(chapter)
    counts = _load_page_counts(db, subject_id)
    return _chapter_dict(chapter, counts.get(chapter.id, 0))


@router.delete("/{chapter_id}")
def delete_chapter(
    subject_id: int,
    chapter_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除章：章内页保留并归入「未分章」（chapter_id 置空）"""
    chapter = require_chapter(db, user.id, subject_id, chapter_id)
    db.execute(
        text("UPDATE pages SET chapter_id = NULL WHERE chapter_id = :cid"),
        {"cid": chapter.id},
    )
    db.delete(chapter)
    db.commit()
    return {"ok": True}


@router.get("/{chapter_id}/export")
def export_chapter(
    subject_id: int,
    chapter_id: int,
    format: str = "md",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出整章为 Markdown / 纯文本（T11-A2，新增接口，方案 A）

    取数：各页 `structured_text` 优先、空则回退 `ocr_text`；两者都空的页**跳过但记数**。
    开头**必须**标注来源（混合来源时给出准确页数），绝不让用户误以为导出稿 = App 内那份统一整理稿。
    跨用户 / 不存在 → **404**；章下所有页都无文本 → **400**。

    排序说明：任务书写「按 sort_order, id」，但 `Page` 模型**没有 sort_order 字段**（且本批不许改表结构）
    → 实际按 `(是否已编号, page_no, id)` 升序，保证顺序确定且「已编号的页」在前。
    """
    # 归属 / 存在性：任一步失败统一成同一文案，避免通过响应体差异反推「章是否存在 / 属于谁」
    try:
        chapter = require_chapter(db, user.id, subject_id, chapter_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="章不存在") from exc
        raise
    pages = (
        db.query(Page)
        .filter(Page.chapter_id == chapter.id, Page.user_id == user.id)
        .order_by(Page.page_no.is_(None), Page.page_no, Page.id)
        .all()
    )
    subject_name = chapter.subject.name if chapter.subject else ""

    try:
        fmt = export_service.normalize_format(format)
        content, filename = export_service.build_chapter_export(
            pages, subject_name, chapter.name, fmt
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=export_service.CONTENT_TYPES[fmt],
        headers={"Content-Disposition": export_service.content_disposition(filename)},
    )


@router.post("/{chapter_id}/organize")
def organize_chapter(
    subject_id: int,
    chapter_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider=Depends(get_ai_provider_dep),
):
    """AI 整理整章笔记：合并章下所有页 OCR 文本后整理"""
    chapter = require_chapter(db, user.id, subject_id, chapter_id)
    pages = (
        db.query(Page)
        .filter(Page.chapter_id == chapter.id, Page.user_id == user.id)
        .order_by(Page.id)
        .all()
    )
    if not pages:
        raise HTTPException(status_code=400, detail="该章下没有笔记页")
    merged = "\n\n---\n\n".join(
        f"【第 {i+1} 页】\n{p.ocr_text}" for i, p in enumerate(pages) if p.ocr_text.strip()
    )
    if not merged.strip():
        raise HTTPException(status_code=400, detail="章下笔记均无 OCR 文本")

    try:
        result = organize_text(provider, merged, "chapter")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI 整理失败：{exc}")

    # T12-0：把结果**落库**（此前只 return —— 用户每点一次就重烧一次 AI，刷新即丢）。
    # 每次整理插一条新记录、不覆盖旧记录；接口只返回本次这一条。
    org = ChapterOrganization(
        chapter_id=chapter.id,
        user_id=user.id,
        structured_text=result,
        # 只有 OCR 正文非空的页才真正参与了整理（与上面 merged 的口径一致）
        source_page_count=len([p for p in pages if p.ocr_text.strip()]),
        # provider 抽象层未定义模型名，用 getattr 尽力取（DeepSeek 实现暴露了 self.model）；
        # 取不到就留空串，**不硬编**
        model_name=getattr(provider, "model", "") or "",
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    # 返回值**只加不删**：原有 chapter_id / chapter_name / structured_text 原样保留（老前端不破）
    return {
        "chapter_id": chapter.id,
        "chapter_name": chapter.name,
        "structured_text": result,
        "organization_id": org.id,
        "created_at": org.created_at.isoformat(),
    }


@router.get("/{chapter_id}/organization/latest")
def get_latest_chapter_organization(
    subject_id: int,
    chapter_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取该章**最新一次** AI 整理稿。

    - 空态（该章从未整理过）返回 `{"empty": true, "reason": ...}` + **HTTP 200**（不是 404）
    - 越权校验**复用 `require_chapter`**：别人的章 / 不存在的章一律 404，
      且响应体与「章不存在」完全一致（T9 已确立的规则）
    """
    # 归属 / 存在性：任一步失败统一成同一文案，避免通过响应体差异反推「章是否存在 / 属于谁」
    # （与同文件 export_chapter 同一做法；校验仍**复用 require_chapter**，未自己写查询条件）
    try:
        require_chapter(db, user.id, subject_id, chapter_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="章不存在") from exc
        raise
    org = (
        db.query(ChapterOrganization)
        .filter(ChapterOrganization.chapter_id == chapter_id)
        .order_by(ChapterOrganization.created_at.desc(), ChapterOrganization.id.desc())
        .first()
    )
    if org is None:
        return {"empty": True, "reason": "该章还没有整理记录"}
    return {
        "chapter_id": org.chapter_id,
        "structured_text": org.structured_text,
        "created_at": org.created_at.isoformat(),
        "source_page_count": org.source_page_count,
        "model_name": org.model_name,
    }
