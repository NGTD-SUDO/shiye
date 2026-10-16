"""测试夹具：独立临时 SQLite + 同步假 OCR + 临时存储目录"""
import io
import os
import tempfile
import time
from pathlib import Path

# 测试必须与环境无关：不读 .env 里的真实密钥（python-dotenv 默认 override=False，
# 显式设空值即能压过 .env）。T3-0 硬验收：真身有 .env 也必须全绿。
os.environ["SHIYE_DEV_MODE"] = "true"
os.environ["SHIYE_SECRET_KEY"] = "test-only-secret-key-do-not-use-in-prod-32chars+"
# 清空真实密钥：测试里 provider 本来就是注入的假实现
os.environ["SHIYE_DEEPSEEK_API_KEY"] = ""
os.environ["SHIYE_BAIDU_API_KEY"] = ""
os.environ["SHIYE_BAIDU_SECRET_KEY"] = ""
os.environ["SHIYE_OCR"] = "none"
# 清空内测邀请码：dev-login 免码（测试不依赖 .env 里的真实邀请码，T4 补漏）
os.environ["SHIYE_INVITE_CODE"] = ""

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import app.services.storage_service as storage_service
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.ocr.base import OcrProvider, OcrResult
from app.routers.pages import get_ocr_processor
from app.services import fts
from app.services.ocr_service import OcrProcessor


class FakeProvider(OcrProvider):
    """返回可配置文本的假 OCR"""

    def recognize(self, image_path: Path) -> OcrResult:
        return OcrResult(text=FAKE_TEXT, conf=0.95)


FAKE_TEXT = "默认识别文本 导数与极值\n复习笔记"


@pytest.fixture(autouse=True)
def fake_text_reset():
    """每个用例重置假 OCR 文本"""
    global FAKE_TEXT
    FAKE_TEXT = "默认识别文本 导数与极值\n复习笔记"


@pytest.fixture(autouse=True)
def tmp_storage(tmp_path, monkeypatch):
    """每个用例使用独立临时存储目录"""
    monkeypatch.setattr(storage_service, "UPLOAD_DIR", tmp_path / "storage")


@pytest.fixture
def client():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _record):
        dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON").close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_ocr_processor():
        """同步假 OCR：enqueue 即完成，便于断言上传后的状态"""
        sync_processor = OcrProcessor(FakeProvider(), TestingSessionLocal)
        sync_processor.enqueue = sync_processor._process  # type: ignore[assignment]
        return sync_processor

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_ocr_processor] = override_ocr_processor
    Base.metadata.create_all(bind=engine)
    fts.ensure_fts(engine)

    with TestClient(fastapi_app) as test_client:
        yield test_client

    fastapi_app.dependency_overrides.clear()
    engine.dispose()
    time.sleep(0.1)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


def auth_headers(client: TestClient, openid: str = "dev_tester_1", nickname: str = "测试用户") -> dict:
    resp = client.post("/auth/dev-login", json={"openid": openid, "nickname": nickname})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_jpg_bytes(text_pixels: tuple[int, int, int] = (200, 220, 200)) -> bytes:
    """生成一张真实可被 PIL 解析的 JPEG 字节（白底灰字区域）"""
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), text_pixels).save(buf, "JPEG")
    return buf.getvalue()
