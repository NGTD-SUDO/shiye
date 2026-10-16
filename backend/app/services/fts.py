"""FTS5 全文索引同步：pages_fts 虚拟表（trigram，可回退 LIKE）"""
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

_CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    title, ocr_text, page_id UNINDEXED, tokenize='trigram'
)
"""


def ensure_fts(engine: Engine) -> None:
    """确保 FTS 表存在"""
    with engine.begin() as conn:
        conn.execute(text(_CREATE_FTS))


def upsert_page(db: Session, page_id: int, title: str, ocr_text: str) -> None:
    """重建某页索引（trigram 虚拟表不支持 upsert，先删后插）"""
    db.execute(text("DELETE FROM pages_fts WHERE rowid = :page_id"), {"page_id": page_id})
    db.execute(
        text(
            "INSERT INTO pages_fts(rowid, page_id, title, ocr_text) "
            "VALUES (:page_id, :page_id, :title, :ocr_text)"
        ),
        {"page_id": page_id, "title": title or "", "ocr_text": ocr_text or ""},
    )


def delete_page(db: Session, page_id: int) -> None:
    db.execute(text("DELETE FROM pages_fts WHERE rowid = :page_id"), {"page_id": page_id})


def count_fts_rows(db: Session) -> int:
    return db.execute(text("SELECT count(*) FROM pages_fts")).scalar()
