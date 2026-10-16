"""页数据模型：一页笔记 = 一张图 + 一段 OCR 文本"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# OCR 状态机：pending → processing → done / failed
OCR_PENDING = "pending"
OCR_PROCESSING = "processing"
OCR_DONE = "done"
OCR_FAILED = "failed"
OCR_STATES = (OCR_PENDING, OCR_PROCESSING, OCR_DONE, OCR_FAILED)


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    image_key: Mapped[str] = mapped_column(String(255), nullable=False)
    thumb_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ocr_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ocr_state: Mapped[str] = mapped_column(String(20), nullable=False, default=OCR_PENDING)
    ocr_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ocr_conf: Mapped[float | None] = mapped_column(Float, nullable=True)
    structured_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="pages")
    subject = relationship("Subject", back_populates="pages")
    chapter = relationship("Chapter", back_populates="pages")
