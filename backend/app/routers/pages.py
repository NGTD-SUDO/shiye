"""页 API 路由：上传/批量/列表/详情/修改/删除/重识别"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.config import MAX_BATCH_FILES, MAX_UPLOAD_BYTES
from app.database import get_db
from app.models.page import OCR_STATES, Page
from app.models.user import User
from app.routers.deps import get_current_user
from app.schemas.page import PageUpdate
from app.services import export_service, fts, storage_service
from app.services.file_signing import sign_url
from app.services.access import require_chapter, require_page, require_subject
from app.services.ocr_service import OcrProcessor, get_ocr_processor
from app.ai.service import create_provider, organize_text

router = APIRouter(prefix="/pages", tags=["页"])


def get_ai_provider_dep():
    return create_provider()


def serialize_page(page: Page, user_id: int) -> dict:
    """序列化页；产出绑定 user_id 的签名 URL（15 分钟有效）

    user_id 必填——所有调用点都在已登录请求上下文里，应通过 user.id 传入。
    字段名保持 image_url/thumb_url/image_key/thumb_key 不变；
    thumb_key 为 None 时 thumb_url 为 None。
    """
    image_url = sign_url(page.image_key, user_id)
    thumb_url = None
    if page.thumb_key is not None:
        thumb_url = sign_url(page.thumb_key, user_id)
    return {
        "id": page.id,
        "subject_id": page.subject_id,
        "subject_name": page.subject.name if page.subject else None,
        "chapter_id": page.chapter_id,
        "chapter_name": page.chapter.name if page.chapter else None,
        "title": page.title,
        "image_key": page.image_key,
        "thumb_key": page.thumb_key,
        "image_url": image_url,
        "thumb_url": thumb_url,
        "width": page.width,
        "height": page.height,
        "ocr_text": page.ocr_text,
        "ocr_state": page.ocr_state,
        "ocr_error": page.ocr_error,
        "ocr_conf": page.ocr_conf,
        "structured_text": page.structured_text,
        "page_no": page.page_no,
        "created_at": page.created_at.isoformat(),
        "updated_at": page.updated_at.isoformat() if page.updated_at else None,
    }


def _read_upload(upload: UploadFile) -> bytes:
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="单张图片不能超过 20MB")
    return data


@router.post("/batch", status_code=201)
def create_pages_batch(
    files: list[UploadFile] = File(...),
    subject_id: int = Form(...),
    chapter_id: int | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    processor: OcrProcessor = Depends(get_ocr_processor),
):
    """批量导入：多张图片同归一个学科/章，逐张建页并投递 OCR"""
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(status_code=413, detail=f"一次最多导入 {MAX_BATCH_FILES} 张")
    subject = require_subject(db, user.id, subject_id)
    if chapter_id is not None:
        require_chapter(db, user.id, subject_id, chapter_id)

    created_ids: list[int] = []
    for upload in files:
        data = _read_upload(upload)
        try:
            # T2-5: 上传校验（非图片/像素超限/解压炸弹）抛 ValueError 转 400，文案透传
            info = storage_service.save_image_bytes(user.id, data, upload.filename or "image")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        page = Page(
            user_id=user.id,
            subject_id=subject.id,
            chapter_id=chapter_id,
            image_key=info["image_key"],
            thumb_key=info["thumb_key"],
            width=info["width"],
            height=info["height"],
        )
        db.add(page)
        db.flush()
        fts.upsert_page(db, page.id, "", "")
        created_ids.append(page.id)

    db.commit()
    for page_id in created_ids:
        processor.enqueue(page_id)

    pages = (
        db.query(Page)
        .options(joinedload(Page.subject), joinedload(Page.chapter))
        .filter(Page.id.in_(created_ids))
        .all()
    )
    return {"created": len(pages), "pages": [serialize_page(p, user.id) for p in pages]}


@router.post("", status_code=201)
def create_page(
    file: UploadFile = File(...),
    subject_id: int = Form(...),
    chapter_id: int | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    processor: OcrProcessor = Depends(get_ocr_processor),
):
    """单张上传：建页并投递 OCR（可后续补标题）"""
    subject = require_subject(db, user.id, subject_id)
    if chapter_id is not None:
        require_chapter(db, user.id, subject_id, chapter_id)

    data = _read_upload(file)
    try:
        # T2-5: 上传校验（非图片/像素超限/解压炸弹）抛 ValueError 转 400，文案透传
        info = storage_service.save_image_bytes(user.id, data, file.filename or "image")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    page = Page(
        user_id=user.id,
        subject_id=subject.id,
        chapter_id=chapter_id,
        image_key=info["image_key"],
        thumb_key=info["thumb_key"],
        width=info["width"],
        height=info["height"],
    )
    db.add(page)
    db.flush()
    fts.upsert_page(db, page.id, "", "")
    db.commit()
    processor.enqueue(page.id)
    db.refresh(page)
    return serialize_page(page, user.id)


@router.get("")
def list_pages(
    subject_id: int | None = None,
    chapter_id: int | None = None,
    state: str | None = None,
    page: int = 1,
    size: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if state and state not in OCR_STATES:
        raise HTTPException(status_code=422, detail=f"非法的 OCR 状态: {state}")
    size = min(max(size, 1), 200)
    page = max(page, 1)

    query = db.query(Page).options(joinedload(Page.subject), joinedload(Page.chapter))
    query = query.filter(Page.user_id == user.id)
    if subject_id is not None:
        require_subject(db, user.id, subject_id)
        query = query.filter(Page.subject_id == subject_id)
    if chapter_id is not None:
        query = query.filter(Page.chapter_id == chapter_id)
    if state:
        query = query.filter(Page.ocr_state == state)

    total = query.count()
    pages = (
        query.order_by(Page.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return {"total": total, "items": [serialize_page(p, user.id) for p in pages]}


@router.get("/{page_id}")
def get_page(
    page_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page = (
        db.query(Page)
        .options(joinedload(Page.subject), joinedload(Page.chapter))
        .filter(Page.id == page_id, Page.user_id == user.id)
        .first()
    )
    if not page:
        raise HTTPException(status_code=404, detail="笔记页不存在")
    return serialize_page(page, user.id)


@router.get("/{page_id}/export")
def export_page(
    page_id: int,
    format: str = "md",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出单页为 Markdown / 纯文本（T11-A1，新增接口，不改任何现有契约）

    取数顺序：`structured_text`（AI 整理稿）→ `ocr_text`（原始识别稿）→ 都空 **400**（绝不返回空文件）。
    跨用户 / 不存在 → **404**（沿用 `require_page`，响应体与「不存在」逐字节相同）。
    响应带正确 Content-Type 与 RFC 5987 的 `Content-Disposition`（中文文件名不乱码）。
    """
    page = require_page(db, user.id, page_id)
    subject_name = page.subject.name if page.subject else ""

    # 无标题又未编号时，「第N页」用「本学科内序号」（按 id 升序）给一个确定含义
    ordinal = None
    if not (page.title or "").strip() and page.page_no is None:
        ordinal = 1 + (
            db.query(Page)
            .filter(Page.subject_id == page.subject_id, Page.id < page.id)
            .count()
        )

    try:
        fmt = export_service.normalize_format(format)
        content, filename = export_service.build_page_export(page, subject_name, fmt, ordinal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=export_service.CONTENT_TYPES[fmt],
        headers={"Content-Disposition": export_service.content_disposition(filename)},
    )


@router.patch("/{page_id}")
def update_page(
    page_id: int,
    req: PageUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """改标题 / 移动学科 / 归章或移出章 / 人工修正 OCR 文本（同步重建索引）"""
    page = require_page(db, user.id, page_id)
    fields = req.model_fields_set

    if "subject_id" in fields and req.subject_id != page.subject_id:
        require_subject(db, user.id, req.subject_id)
        page.subject_id = req.subject_id
        page.chapter_id = None  # 换学科后章归属作废，回到未分章

    if "chapter_id" in fields:
        if req.chapter_id is None:
            page.chapter_id = None
        else:
            chapter = require_chapter(db, user.id, page.subject_id, req.chapter_id)
            page.chapter_id = chapter.id

    if "title" in fields:
        page.title = (req.title or "").strip()

    changed_text = False
    if "ocr_text" in fields:
        page.ocr_text = req.ocr_text or ""
        page.ocr_state = "done"  # 人工修正后视为终稿
        page.ocr_error = None
        changed_text = True

    if "structured_text" in fields:
        page.structured_text = req.structured_text
        changed_text = True

    db.flush()
    if changed_text or "title" in fields:
        fts.upsert_page(db, page.id, page.title, page.ocr_text)
    db.commit()
    db.refresh(page)
    return serialize_page(page, user.id)


@router.post("/{page_id}/reocr")
def reocr_page(
    page_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    processor: OcrProcessor = Depends(get_ocr_processor),
):
    """重新识别：失败重试 / 拍糊重拍后使用"""
    page = require_page(db, user.id, page_id)
    page.ocr_state = "pending"
    page.ocr_error = None
    db.commit()
    processor.enqueue(page.id)
    return {"id": page.id, "ocr_state": "pending"}


@router.post("/{page_id}/organize")
def organize_page(
    page_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider=Depends(get_ai_provider_dep),
):
    """AI 整理单页笔记：纠错 + 结构化 Markdown"""
    page = require_page(db, user.id, page_id)
    if not page.ocr_text.strip():
        raise HTTPException(status_code=400, detail="OCR 文本为空，无法整理")
    try:
        result = organize_text(provider, page.ocr_text, "page")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI 整理失败：{exc}")
    page.structured_text = result
    db.commit()
    db.refresh(page)
    return serialize_page(page, user.id)


@router.delete("/{page_id}")
def delete_page(
    page_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page = require_page(db, user.id, page_id)
    fts.delete_page(db, page.id)
    storage_service.delete_keys([page.image_key, page.thumb_key])
    db.delete(page)
    db.commit()
    return {"ok": True}
