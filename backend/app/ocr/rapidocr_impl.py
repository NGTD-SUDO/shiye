"""RapidOCR（PaddleOCR 模型 ONNX 版，CPU）实现 —— M0 实测对象"""
from pathlib import Path

from app.ocr.base import OcrProvider, OcrResult


class RapidOcrProvider(OcrProvider):
    """懒加载 RapidOCR 引擎（首次调用时才载入模型）"""

    _engine = None

    def _get_engine(self):
        if RapidOcrProvider._engine is None:
            from rapidocr_onnxruntime import RapidOCR

            RapidOcrProvider._engine = RapidOCR()
        return RapidOcrProvider._engine

    def recognize(self, image_path: Path) -> OcrResult:
        engine = self._get_engine()
        result, _elapse = engine(str(image_path))
        if not result:
            return OcrResult(text="", conf=None)

        lines = [item[1] for item in result if len(item) >= 2]
        confs = [float(item[2]) for item in result if len(item) >= 3 and item[2]]
        avg_conf = (sum(confs) / len(confs)) if confs else None
        return OcrResult(text="\n".join(lines), conf=avg_conf)
