"""T3-4 OCR provider 错误码映射、超时文案、create_provider 失败日志

不真实调用百度 API，用 mock httpx 返回错误码 / 抛异常，断言中文文案可操作。
"""
import io
import logging
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch, MagicMock

import httpx
import pytest

from app.ocr.baidu_impl import BaiduOcrProvider
from app.ocr.base import OcrProvider, OcrResult
from app.services import ocr_service


@contextmanager
def _fake_image_file():
    """让 Path.open 返回假字节流，避免百度 provider 读真实文件。

    百度 recognize 首行 `with image_path.open("rb") as f:` 读文件做 base64，
    测试用 Path("fake.jpg") 不存在会 FileNotFoundError，这里统一打补丁。
    """
    fake = io.BytesIO(b"fake-image-bytes")
    with patch("pathlib.Path.open", return_value=fake):
        yield


# ==================== 1. 百度错误码 → 可操作中文文案 ====================

def _make_baidu_provider():
    """构造一个已注入假 token 的百度 provider（绕过 _get_token 网络调用）"""
    p = BaiduOcrProvider.__new__(BaiduOcrProvider)
    p._token = "fake-token"
    p._token_expire_at = float("inf")
    return p


def test_01a_error_code_110_auth_failed():
    """error_code=110（token 无效）→ 文案含「鉴权失败」+ 变量名指引"""
    provider = _make_baidu_provider()
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"error_code": 110, "error_msg": "Access token invalid"}
    fake_resp.raise_for_status = MagicMock()
    with _fake_image_file(), patch("app.ocr.baidu_impl.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post = MagicMock(return_value=fake_resp)
        mock_client_cls.return_value = mock_client
        with pytest.raises(RuntimeError) as exc_info:
            provider.recognize(Path("fake.jpg"))
        msg = str(exc_info.value)
        assert "鉴权失败" in msg, f"应含「鉴权失败」，实际：{msg}"
        assert "SHIYE_BAIDU_API_KEY" in msg or "SHIYE_BAIDU_SECRET_KEY" in msg


def test_01b_error_code_111_auth_failed():
    """error_code=111（Access token 失效）→ 文案含「鉴权失败」"""
    provider = _make_baidu_provider()
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"error_code": 111, "error_msg": "Access token expired"}
    fake_resp.raise_for_status = MagicMock()
    with _fake_image_file(), patch("app.ocr.baidu_impl.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post = MagicMock(return_value=fake_resp)
        mock_client_cls.return_value = mock_client
        with pytest.raises(RuntimeError, match="鉴权失败"):
            provider.recognize(Path("fake.jpg"))


def test_01c_error_code_18_quota_exceeded():
    """error_code=18（月配额超限）→ 文案含「配额或并发超限」"""
    provider = _make_baidu_provider()
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"error_code": 18, "error_msg": "Open api monthly request limit reached"}
    fake_resp.raise_for_status = MagicMock()
    with _fake_image_file(), patch("app.ocr.baidu_impl.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post = MagicMock(return_value=fake_resp)
        mock_client_cls.return_value = mock_client
        with pytest.raises(RuntimeError, match="配额或并发超限"):
            provider.recognize(Path("fake.jpg"))


def test_01d_error_code_17_concurrent_limit():
    """error_code=17（并发超限）→ 文案含「配额或并发超限」"""
    provider = _make_baidu_provider()
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"error_code": 17, "error_msg": "Open api daily request limit reached"}
    fake_resp.raise_for_status = MagicMock()
    with _fake_image_file(), patch("app.ocr.baidu_impl.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post = MagicMock(return_value=fake_resp)
        mock_client_cls.return_value = mock_client
        with pytest.raises(RuntimeError, match="配额或并发超限"):
            provider.recognize(Path("fake.jpg"))


def test_01e_other_error_code_keeps_raw():
    """其它 error_code → 保留 error_code + error_msg"""
    provider = _make_baidu_provider()
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"error_code": 999, "error_msg": "Unknown error"}
    fake_resp.raise_for_status = MagicMock()
    with _fake_image_file(), patch("app.ocr.baidu_impl.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post = MagicMock(return_value=fake_resp)
        mock_client_cls.return_value = mock_client
        with pytest.raises(RuntimeError) as exc_info:
            provider.recognize(Path("fake.jpg"))
        msg = str(exc_info.value)
        assert "999" in msg and "Unknown error" in msg


# ==================== 2. 超时/连接异常 → 可操作中文文案 ====================

def test_02a_timeout_returns_chinese_message():
    """httpx.TimeoutException → 文案含「超时」+ 超时秒数"""
    provider = _make_baidu_provider()
    with _fake_image_file(), patch("app.ocr.baidu_impl.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post = MagicMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client_cls.return_value = mock_client
        with pytest.raises(RuntimeError) as exc_info:
            provider.recognize(Path("fake.jpg"))
        msg = str(exc_info.value)
        assert "超时" in msg
        # 应含超时秒数（OCR_TIMEOUT_SECONDS 默认 30）
        assert "30" in msg


def test_02b_connect_error_returns_chinese_message():
    """httpx.ConnectError → 文案含「连接百度 OCR 失败」"""
    provider = _make_baidu_provider()
    with _fake_image_file(), patch("app.ocr.baidu_impl.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post = MagicMock(side_effect=httpx.ConnectError("refused"))
        mock_client_cls.return_value = mock_client
        with pytest.raises(RuntimeError, match="连接百度 OCR 失败"):
            provider.recognize(Path("fake.jpg"))


# ==================== 3. create_provider 失败 → logging.error + 原因可传达 ====================

def test_03a_create_provider_baidu_missing_key_logs_error(monkeypatch, caplog):
    """create_provider 百度缺 key → 返回 None + logging.error 记录原因"""
    monkeypatch.setattr(ocr_service, "OCR_PROVIDER", "baidu")
    # 百度 provider 构造会抛 RuntimeError（缺 key）
    with caplog.at_level(logging.ERROR, logger=ocr_service.__name__):
        provider = ocr_service.create_provider()
    assert provider is None, "缺 key 时应返回 None"
    assert any("百度" in r.message or "OCR" in r.message for r in caplog.records), \
        "应 logging.error 记录原因"


def test_03c_run_ocr_none_provider_with_error_message():
    """run_ocr provider=None + 有 provider_error → RuntimeError 含具体原因

    直接调模块级 run_ocr，模拟 ocr_service.provider_error 有值。
    """
    from app.models.page import Page
    page = Page(id=1, image_key="1/test.jpg", title="")
    # 临时给 ocr_service 模块加 provider_error
    original = getattr(ocr_service, "provider_error", None)
    ocr_service.provider_error = "百度 OCR 鉴权失败：请检查 SHIYE_BAIDU_API_KEY/SECRET_KEY"
    try:
        with pytest.raises(RuntimeError) as exc_info:
            ocr_service.run_ocr(MagicMock(), page, None)
        msg = str(exc_info.value)
        assert "鉴权失败" in msg or "SHIYE_BAIDU" in msg, \
            f"应含具体原因，实际：{msg}"
    finally:
        if original is None:
            delattr(ocr_service, "provider_error")
        else:
            ocr_service.provider_error = original


def test_03d_create_provider_none_returns_none_no_error(monkeypatch, caplog):
    """create_provider OCR=none → 返回 None 且不记 ERROR 日志

    none 是合法配置（启动校验已 warning），create_provider 不应把它当成错误。
    RapidOCR 缺依赖由启动校验（_validate_ocr_config 用 find_spec）拦截，
    create_provider 不会返回 None——RapidOcrProvider 构造是懒加载，不触发 import。
    """
    monkeypatch.setattr(ocr_service, "OCR_PROVIDER", "none")
    with caplog.at_level(logging.ERROR, logger=ocr_service.__name__):
        provider = ocr_service.create_provider()
    assert provider is None, "OCR=none 时应返回 None"
    assert not any(r.levelno == logging.ERROR for r in caplog.records), \
        "OCR=none 是合法配置，不应记 ERROR 日志"
