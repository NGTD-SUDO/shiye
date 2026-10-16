"""页相关请求模型"""
from pydantic import BaseModel, Field


class PageUpdate(BaseModel):
    """支持部分更新；仅当字段出现在请求体里才生效（见 model_fields_set）。

    chapter_id 显式传 null 表示「移出章」（归入学科下未分章）。
    """

    title: str | None = Field(default=None, max_length=200)
    subject_id: int | None = None
    chapter_id: int | None = None
    ocr_text: str | None = None
    structured_text: str | None = None
