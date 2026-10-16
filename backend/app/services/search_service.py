"""搜索服务：FTS5 trigram（≥3 字符）为主，短词回退 LIKE 子串匹配"""
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.file_signing import sign_url

_SNIPPET_RADIUS = 24

# FTS 查询用：去除非中英文字符与空白，做连续短语
_NON_WORD_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def _fts_phrase(q: str) -> str:
    return _NON_WORD_RE.sub("", q)


def _like_pattern(q: str) -> str:
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _make_snippet(text_value: str, needle: str) -> str:
    if not text_value:
        return ""
    low = text_value.lower()
    idx = low.find(needle.lower())
    if idx == -1:
        return text_value[:_SNIPPET_RADIUS * 2]
    start = max(0, idx - _SNIPPET_RADIUS)
    end = min(len(text_value), idx + len(needle) + _SNIPPET_RADIUS)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text_value) else ""
    return f"{prefix}{text_value[start:end]}{suffix}"


_COLUMNS = (
    "f.rowid AS page_id, p.title, p.thumb_key, p.thumb_key IS NOT NULL AS has_thumb, "
    "p.ocr_state, p.subject_id, s.name AS subject_name, f.ocr_text"
)


def search(
    db: Session,
    user_id: int,
    q: str,
    subject_id: int | None = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    q = q.strip()
    size = min(max(size, 1), 100)
    offset = (max(page, 1) - 1) * size
    subject_clause = " AND p.subject_id = :sid" if subject_id else ""
    params = {"uid": user_id, "limit": size, "offset": offset}
    if subject_id:
        params["sid"] = subject_id

    clean = _fts_phrase(q)
    if not clean:
        return {"total": 0, "items": []}

    use_fts = len(clean) >= 3
    if use_fts:
        # trigram 需 ≥3 字符连续短语
        match = f'"{clean}"'
        params["match"] = match
        count_sql = text(
            "SELECT count(*) FROM pages_fts f JOIN pages p ON p.id = f.rowid "
            "WHERE p.user_id = :uid AND pages_fts MATCH :match" + subject_clause
        )
        rows_sql = text(
            "SELECT " + _COLUMNS + " FROM pages_fts f "
            "JOIN pages p ON p.id = f.rowid JOIN subjects s ON s.id = p.subject_id "
            "WHERE p.user_id = :uid AND pages_fts MATCH :match" + subject_clause +
            " ORDER BY bm25(pages_fts), p.id DESC LIMIT :limit OFFSET :offset"
        )
    else:
        params["like"] = _like_pattern(q)
        like_clause = "(p.title LIKE :like ESCAPE '\\' OR p.ocr_text LIKE :like ESCAPE '\\')"
        count_sql = text(
            "SELECT count(*) FROM pages p WHERE p.user_id = :uid AND " + like_clause + subject_clause
        )
        rows_sql = text(
            "SELECT p.id AS page_id, p.title, p.thumb_key, "
            "1 AS has_thumb, p.ocr_state, p.subject_id, s.name AS subject_name, p.ocr_text "
            "FROM pages p JOIN subjects s ON s.id = p.subject_id "
            "WHERE p.user_id = :uid AND " + like_clause + subject_clause +
            " ORDER BY p.id DESC LIMIT :limit OFFSET :offset"
        )

    total = db.execute(count_sql, params).scalar() or 0
    rows = db.execute(rows_sql, params).mappings().all()

    items = []
    for row in rows:
        snippet = _make_snippet(row["ocr_text"] or "", clean)
        items.append(
            {
                "page_id": row["page_id"],
                "title": row["title"],
                "subject_id": row["subject_id"],
                "subject_name": row["subject_name"],
                "thumb_key": row["thumb_key"],
                "thumb_url": sign_url(row["thumb_key"], user_id) if row["thumb_key"] else None,
                "ocr_state": row["ocr_state"],
                "snippet": snippet,
            }
        )
    return {"total": total, "items": items}
