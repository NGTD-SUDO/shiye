"""整章 AI 整理结果数据模型（T12-0）

新增**一张表**，不改动任何现有表结构：
- `chapter_organizations`：整章 AI 整理的历史记录。**每次整理插一条新记录、不删旧**，
  接口只返回最新一条 —— 便于事后追溯「上次整理成什么样」，且实现最简单。

与「单页整理」的差别：单页结果写在 `pages.structured_text`（原地覆盖，一行只留一份）；
整章会被反复整理，需要留痕，所以用**追加**而不是覆盖。

建表沿用现有做法（`Base.metadata.create_all`，见 `app/main.py`），**不引入迁移工具**。
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChapterOrganization(Base):
    __tablename__ = "chapter_organizations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 归属章；章被删除时记录一并级联删除
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 归属用户；越权校验仍走 require_chapter，这里存一份便于追溯/排障
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # AI 整理后的 Markdown 全文
    structured_text: Mapped[str] = mapped_column(Text, nullable=False)
    # 本次整理实际聚合了几页（只算 OCR 正文非空、真正参与整理的页）
    source_page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 用的哪个模型；provider 未暴露模型名时留空字符串（不硬编）
    model_name: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
