"""学科数据模型（一级分组，用户自管理）"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# T13-3：新建学科默认色 旧绿 → 主题蓝（systemBlue），与前端调色板/兜底一致。
# ⚠️ 只影响"新建默认值"，**不迁移已有科目数据**（用户选过的颜色是用户数据）。
DEFAULT_COLOR = "#007AFF"
DEFAULT_ICON = "book"


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(9), nullable=False, default=DEFAULT_COLOR)
    icon: Mapped[str] = mapped_column(String(20), nullable=False, default=DEFAULT_ICON)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="subjects")
    chapters = relationship(
        "Chapter",
        back_populates="subject",
        cascade="all, delete-orphan",
        order_by="Chapter.sort_order",
    )
    pages = relationship("Page", back_populates="subject", cascade="all, delete-orphan")
