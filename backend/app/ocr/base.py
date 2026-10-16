"""OCR 引擎抽象层：可切换 RapidOCR / 百度手写 API 等实现"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OcrResult:
    text: str
    conf: float | None = None


class OcrProvider(ABC):
    """识别一张图片，返回整页文本与平均置信度"""

    @abstractmethod
    def recognize(self, image_path: Path) -> OcrResult:
        raise NotImplementedError
