"""OCR 任务处理：内存队列 + 后台 worker 线程 + 状态机。

MVP 单用户量级不引入 Celery/Redis：上传 → 队列 → worker 线程消费；
服务器重启时扫描 pending/processing 的页自动重新投递（幂等）。
"""
import logging
import queue
import threading

from sqlalchemy.orm import Session

from app.config import OCR_PROVIDER
from app.database import SessionLocal
from app.models.page import (
    OCR_DONE,
    OCR_FAILED,
    OCR_PENDING,
    OCR_PROCESSING,
    Page,
)
from app.ocr.base import OcrProvider
from app.services import fts, storage_service
from app.services.title_extractor import extract_title

logger = logging.getLogger(__name__)


# 模块级 provider_error：create_provider 失败时记录原因，run_ocr 优先用它
provider_error: str | None = None


def create_provider() -> OcrProvider | None:
    """按配置创建 OCR 实现；失败时返回 None 并记录具体原因到 provider_error。

    T3-4：宽泛 except Exception 收窄为具体异常；失败用 logging.error（不再是 warning）。
    """
    global provider_error
    provider_error = None

    if OCR_PROVIDER == "rapidocr":
        try:
            from app.ocr.rapidocr_impl import RapidOcrProvider
            return RapidOcrProvider()
        except ImportError as exc:
            provider_error = f"RapidOCR 依赖未安装（{exc}），请运行 pip install -r requirements-rapidocr.txt"
            logger.error("%s", provider_error)
            return None
        except (RuntimeError, OSError) as exc:
            provider_error = f"加载 RapidOCR 失败：{exc}"
            logger.error("%s", provider_error)
            return None

    if OCR_PROVIDER == "baidu":
        try:
            from app.ocr.baidu_impl import BaiduOcrProvider
            return BaiduOcrProvider()
        except RuntimeError as exc:
            provider_error = str(exc)
            logger.error("加载百度 OCR 失败：%s", exc)
            return None
        except (ImportError, OSError) as exc:
            provider_error = f"加载百度 OCR 失败：{exc}"
            logger.error("%s", provider_error)
            return None

    # OCR=none 或其它：provider 为 None，provider_error 保持 None
    # （none 是合法配置，不应记成错误；启动校验已 warning）
    return None


def run_ocr(db: Session, page: Page, provider: OcrProvider | None) -> None:
    """对单页执行识别并落库（含 FTS 同步）。不提交事务，由调用方 commit。

    成功：写 ocr_text/conf、状态 done、标题为空时用 extract_title 取标题（跳噪 + 中文优先）；
    失败：抛异常由调用方置 failed。
    T3-4：provider 为 None 时优先用 provider_error 给出具体原因（不再只说"未配置"）。
    """
    if provider is None:
        if provider_error:
            raise RuntimeError(provider_error)
        raise RuntimeError("OCR 引擎未配置（SHIYE_OCR=none 或依赖未安装）")

    image_path = storage_service.path_for(page.image_key)
    result = provider.recognize(image_path)
    text = (result.text or "").strip()
    if not text:
        raise RuntimeError("未识别出文字，请换一张更清晰的图片后重试")

    page.ocr_text = text
    page.ocr_conf = result.conf
    page.ocr_state = OCR_DONE
    page.ocr_error = None
    # 仅当标题为空时才自动写（用户在 App 里手改过的标题在重新识别时不被覆盖）
    if not page.title:
        page.title = extract_title(text)
    fts.upsert_page(db, page.id, page.title, page.ocr_text)


class OcrProcessor:
    """内存队列 + 后台 worker；provider/session_factory 可注入以便测试"""

    def __init__(self, provider: OcrProvider | None, session_factory):
        self.provider = provider
        self.provider_error: str | None = provider_error  # 模块级 provider_error 的快照
        self.session_factory = session_factory
        self._queue: "queue.Queue[int]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, name="ocr-worker", daemon=True)
        self._thread.start()
        self._requeue_interrupted()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def enqueue(self, page_id: int) -> None:
        self._queue.put(page_id)

    def _requeue_interrupted(self) -> None:
        """服务重启后重新投递未完成的页"""
        try:
            with self.session_factory() as db:
                ids = (
                    db.query(Page.id)
                    .filter(Page.ocr_state.in_([OCR_PENDING, OCR_PROCESSING]))
                    .all()
                )
            for (page_id,) in ids:
                self.enqueue(page_id)
        except Exception as exc:  # 启动恢复失败不应阻塞服务
            logger.warning("恢复未完成 OCR 任务失败：%s", exc)

    def _worker(self) -> None:
        while self._running:
            try:
                page_id = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            try:
                self._process(page_id)
            except Exception:
                logger.exception("OCR 处理页 %s 时异常", page_id)
            finally:
                self._queue.task_done()

    def _process(self, page_id: int) -> None:
        with self.session_factory() as db:
            page = db.get(Page, page_id)
            if page is None:
                return
            try:
                page.ocr_state = OCR_PROCESSING
                db.commit()
                run_ocr(db, page, self.provider)
                db.commit()
            except Exception as exc:
                db.rollback()
                page = db.get(Page, page_id)
                if page is not None:
                    page.ocr_state = OCR_FAILED
                    page.ocr_error = str(exc)[:490]
                    db.commit()


ocr_processor = OcrProcessor(create_provider(), SessionLocal)


def get_ocr_processor() -> OcrProcessor:
    """FastAPI 依赖：返回全局 OCR 处理器（测试中可覆盖）"""
    return ocr_processor
