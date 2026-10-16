"""章相关请求模型"""
from pydantic import BaseModel, Field


class ChapterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class ChapterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    sort_order: int | None = Field(default=None, ge=0)
