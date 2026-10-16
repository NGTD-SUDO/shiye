"""用户数据模型（微信登录为主，本地开发经 dev-login）"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 微信 openid；dev-login 时填入形如 dev_xxx 的标识
    wechat_openid: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    wechat_unionid: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False, default="拾页用户")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    subjects = relationship("Subject", back_populates="user", cascade="all, delete-orphan")
    pages = relationship("Page", back_populates="user", cascade="all, delete-orphan")
