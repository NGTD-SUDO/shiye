"""导出服务（T11-A）：把笔记导出为 Markdown / 纯文本

设计要点：
- **纯字符串拼接，零新依赖**（任务书硬约束 5）
- 业务逻辑集中在此，路由保持薄；核心函数为纯函数，可脱离 DB 单测
- 取数顺序：`structured_text`（AI 整理稿）→ `ocr_text`（原始识别稿）→ 都空报错
- 整章导出**必须标注混合来源**（任务书硬性要求）：
  绝不让用户误以为导出稿 = App 内那份统一整理的稿
- 中文文件名按 **RFC 5987**（`filename*=UTF-8''`）编码，避免乱码
"""
from __future__ import annotations

from urllib.parse import quote

# 支持的导出格式
FORMATS = ("md", "txt")
DEFAULT_FORMAT = "md"

# 格式 → 响应 Content-Type（charset 显式写出，避免被二次拼接）
CONTENT_TYPES = {
    "md": "text/markdown; charset=utf-8",
    "txt": "text/plain; charset=utf-8",
}
# 格式 → 文件扩展名
FILE_EXT = {"md": "md", "txt": "txt"}

# 文件名里非法/易出问题的字符（Windows/Android 通用）
_ILLEGAL_CHARS = set('/\\:*?"<>|\r\n\t\0')
# 文件名长度上限（按字符）
MAX_FILENAME_CHARS = 80
# 每页之间的分隔线（txt）
_TXT_RULE = "-" * 40


def normalize_format(fmt: str | None) -> str:
    """校验并归一化导出格式；非法 → ValueError（中文）"""
    value = (fmt or DEFAULT_FORMAT).strip().lower()
    if value not in FORMATS:
        raise ValueError(f"不支持的导出格式：{fmt}（仅支持 md / txt）")
    return value


def sanitize_filename(name: str) -> str:
    """清理文件名：去掉非法字符/控制字符，压缩空白，截断长度。空 → 「导出」"""
    cleaned = "".join(
        "_" if (ch in _ILLEGAL_CHARS or ord(ch) < 32) else ch for ch in (name or "")
    )
    cleaned = " ".join(cleaned.split()).strip(" ._-")
    if not cleaned:
        cleaned = "导出"
    return cleaned[:MAX_FILENAME_CHARS]


def _ascii_fallback(filename: str) -> str:
    """`filename=` 的 ASCII 兜底（老客户端用）：保扩展名，主体保留 ASCII 可见字符"""
    if "." in filename:
        stem, ext = filename.rsplit(".", 1)
    else:
        stem, ext = filename, ""
    safe = "".join(
        ch for ch in stem if 32 <= ord(ch) < 127 and ch not in '"\\;'
    ).strip(" ._-")
    safe = safe or "export"
    return f"{safe}.{ext}" if ext else safe


def content_disposition(filename: str) -> str:
    """生成 Content-Disposition：RFC 5987 的 `filename*=UTF-8''<百分号编码>` + ASCII 兜底"""
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{_ascii_fallback(filename)}\"; filename*=UTF-8''{encoded}"


def page_export_source(page) -> tuple[str, str] | None:
    """取单页导出内容：返回 `(来源, 文本)`，来源 ∈ {"structured", "raw"}；都空 → None

    只读访问 page 的属性，不依赖 DB 会话。
    """
    structured = (getattr(page, "structured_text", None) or "").strip()
    if structured:
        return ("structured", structured)
    raw = (getattr(page, "ocr_text", None) or "").strip()
    if raw:
        return ("raw", raw)
    return None


def page_label(page, ordinal: int | None = None) -> str:
    """页的展示名：标题优先 → `第{page_no}页` → `第{序号}页` → `第{id}页`"""
    title = (getattr(page, "title", "") or "").strip()
    if title:
        return title
    page_no = getattr(page, "page_no", None)
    if page_no is not None:
        return f"第{page_no}页"
    if ordinal is not None:
        return f"第{ordinal}页"
    return f"第{getattr(page, 'id', 0)}页"


def _with_trailing_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def build_page_export(
    page,
    subject_name: str,
    fmt: str | None = DEFAULT_FORMAT,
    ordinal: int | None = None,
) -> tuple[str, str]:
    """单页导出：返回 `(内容, 文件名)`；无任何文本 → ValueError（中文）

    文件名规则：`{学科名}-{标题或第N页}.{md|txt}`
    """
    fmt = normalize_format(fmt)
    source = page_export_source(page)
    if source is None:
        raise ValueError("该页没有可导出的文本")
    filename = (
        f"{sanitize_filename(subject_name)}-"
        f"{sanitize_filename(page_label(page, ordinal))}.{FILE_EXT[fmt]}"
    )
    return _with_trailing_newline(source[1]), filename


def chapter_source_note(organized: int, raw: int, skipped: int = 0) -> str:
    """整章导出的来源标注（任务书硬性要求，绝不含糊）

    - 混合来源必须给出**准确页数**
    - 有页因为「没有任何文本」被跳过时，额外注明跳过页数（避免用户以为整章都在稿里）
    """
    if organized and raw:
        note = f"本稿含 {organized} 页 AI 整理 + {raw} 页原始识别"
    elif organized:
        note = "本稿全部为 AI 整理稿"
    else:
        note = "本稿全部为原始识别文本，未经 AI 整理"
    if skipped:
        note += f"（另有 {skipped} 页无文本，未包含）"
    return note


def _page_block(ordinal: int, label: str, text: str, fmt: str) -> str:
    """单页区块：含页码与标题，便于阅读"""
    if fmt == "md":
        return f"## 第 {ordinal} 页 · {label}\n\n{text}"
    return f"第 {ordinal} 页 · {label}\n{_TXT_RULE}\n{text}"


def build_chapter_export(
    pages,
    subject_name: str,
    chapter_name: str,
    fmt: str | None = DEFAULT_FORMAT,
) -> tuple[str, str]:
    """整章导出（方案 A）：各页 `structured_text` 优先、空则回退 `ocr_text`

    - 两者都空的页**跳过但记数**
    - 开头**必须**写清来源（混合来源时给出准确页数），绝不含糊
    - 章下所有页都无文本 → ValueError（中文）
    """
    fmt = normalize_format(fmt)
    blocks: list[str] = []
    organized = raw = skipped = 0

    for ordinal, page in enumerate(pages, start=1):
        source = page_export_source(page)
        if source is None:
            skipped += 1
            continue
        if source[0] == "structured":
            organized += 1
        else:
            raw += 1
        blocks.append(_page_block(ordinal, page_label(page, ordinal), source[1], fmt))

    if not blocks:
        raise ValueError("该章下没有可导出的文本")

    note = chapter_source_note(organized, raw, skipped)
    header = f"> {note}" if fmt == "md" else note
    separator = "\n\n---\n\n" if fmt == "md" else "\n\n" + "=" * 40 + "\n\n"
    content = header + "\n\n" + separator.join(blocks)

    filename = (
        f"{sanitize_filename(subject_name)}-"
        f"{sanitize_filename(chapter_name)}.{FILE_EXT[fmt]}"
    )
    return _with_trailing_newline(content), filename
