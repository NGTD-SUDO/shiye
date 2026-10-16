"""测评（出题 + 判分）数据模型（T9-4）

新增两张表，**不改动任何现有表结构**：
- `quiz_sessions`：一次「出题 → 判分」会话；`payload_snapshot` 保存出题时的内容摘要便于追溯，
  参考答案不在此表。
- `quiz_questions`：会话下的题目与判分结果；**参考答案仅后端持有**，绝不返回前端。

建表沿用现有做法（`Base.metadata.create_all`，见 `app/main.py`），不引入迁移工具。
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 会话状态机：pending（已出题待作答/待判分）→ graded（已判分）
SESSION_PENDING = "pending"
SESSION_GRADED = "graded"
SESSION_STATES = (SESSION_PENDING, SESSION_GRADED)


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 可空：不限定学科时对该用户全库出题
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SESSION_PENDING)
    # 出题时的内容摘要快照（便于追溯「当时基于哪些内容出的题」）
    payload_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 判分后的总体诊断（pending 时为 None）
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    questions = relationship(
        "QuizQuestion",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="QuizQuestion.seq",
    )


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 题号，从 1 开始（判分结果按此顺序对齐）
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    # 参考答案：仅后端持有，接口绝不返回
    reference_answer: Mapped[str] = mapped_column(Text, nullable=False)
    # 考查的知识点，用于后续诊断聚合
    knowledge_point: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # 判分前为空
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    mastery: Mapped[str | None] = mapped_column(String(20), nullable=True)
    user_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    session = relationship("QuizSession", back_populates="questions")
