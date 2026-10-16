"""学科相关请求模型"""
from pydantic import BaseModel, Field, field_validator

from app.models.subject import DEFAULT_COLOR, DEFAULT_ICON


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = Field(default=DEFAULT_COLOR, max_length=9)
    icon: str = Field(default=DEFAULT_ICON, max_length=20)

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str) -> str:
        if not v.startswith("#") or len(v) not in (4, 7):
            raise ValueError("颜色需为 #RGB 或 #RRGGBB")
        return v


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(default=None, max_length=9)
    icon: str | None = Field(default=None, max_length=20)
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str | None) -> str | None:
        if v is not None and (not v.startswith("#") or len(v) not in (4, 7)):
            raise ValueError("颜色需为 #RGB 或 #RRGGBB")
        return v
