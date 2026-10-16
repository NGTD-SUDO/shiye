"""T3-2 OCR 启动配置校验：4 种配置各起一次进程的行为

覆盖 T3 验收标准端到端 4 种配置的启动校验逻辑（不真起进程，直接调 validate_runtime_config）。
"""
import importlib.util
import logging

import pytest

import app.config as cfg


# ==================== 1. OCR=none → 不抛，发 warning ====================

def test_01_ocr_none_warns_not_raises(monkeypatch, caplog):
    """OCR=none → 不抛错，logging.warning 提示「OCR 已禁用」"""
    monkeypatch.setattr(cfg, "OCR_PROVIDER", "none")
    # SECRET_KEY 用强值，避免 SECRET_KEY 分支干扰
    monkeypatch.setattr(cfg, "SECRET_KEY", "x" * 48)
    monkeypatch.setattr(cfg, "DEV_MODE", False)
    with caplog.at_level(logging.WARNING, logger="app.config"):
        cfg.validate_runtime_config()
    assert any("OCR 已禁用" in r.message or "SHIYE_OCR=none" in r.message for r in caplog.records), \
        "OCR=none 应发 warning 提示已禁用"


# ==================== 2. OCR=baidu + 空 key → 抛 RuntimeError ====================

def test_02a_ocr_baidu_missing_api_key_raises(monkeypatch):
    """OCR=baidu + BAIDU_API_KEY 空 → RuntimeError 含缺失变量名与申请指引"""
    monkeypatch.setattr(cfg, "OCR_PROVIDER", "baidu")
    monkeypatch.setattr(cfg, "SECRET_KEY", "x" * 48)
    monkeypatch.setattr(cfg, "DEV_MODE", False)
    monkeypatch.setattr(cfg, "BAIDU_API_KEY", "")
    monkeypatch.setattr(cfg, "BAIDU_SECRET_KEY", "fake-secret")
    with pytest.raises(RuntimeError, match="SHIYE_BAIDU_API_KEY"):
        cfg.validate_runtime_config()


def test_02b_ocr_baidu_missing_secret_key_raises(monkeypatch):
    """OCR=baidu + BAIDU_SECRET_KEY 空 → RuntimeError 含缺失变量名"""
    monkeypatch.setattr(cfg, "OCR_PROVIDER", "baidu")
    monkeypatch.setattr(cfg, "SECRET_KEY", "x" * 48)
    monkeypatch.setattr(cfg, "DEV_MODE", False)
    monkeypatch.setattr(cfg, "BAIDU_API_KEY", "fake-key")
    monkeypatch.setattr(cfg, "BAIDU_SECRET_KEY", "")
    with pytest.raises(RuntimeError, match="SHIYE_BAIDU_SECRET_KEY"):
        cfg.validate_runtime_config()


def test_02c_ocr_baidu_with_keys_ok(monkeypatch):
    """OCR=baidu + 两个 key 都有 → 不抛"""
    monkeypatch.setattr(cfg, "OCR_PROVIDER", "baidu")
    monkeypatch.setattr(cfg, "SECRET_KEY", "x" * 48)
    monkeypatch.setattr(cfg, "DEV_MODE", False)
    monkeypatch.setattr(cfg, "BAIDU_API_KEY", "fake-key")
    monkeypatch.setattr(cfg, "BAIDU_SECRET_KEY", "fake-secret")
    cfg.validate_runtime_config()  # 不抛即通过


# ==================== 3. OCR=rapidocr + 未装依赖 → 抛 RuntimeError ====================

def test_03_ocr_rapidocr_missing_dep_raises(monkeypatch):
    """OCR=rapidocr + 未装 rapidocr_onnxruntime → RuntimeError 含安装命令"""
    monkeypatch.setattr(cfg, "OCR_PROVIDER", "rapidocr")
    monkeypatch.setattr(cfg, "SECRET_KEY", "x" * 48)
    monkeypatch.setattr(cfg, "DEV_MODE", False)
    # mock find_spec 返回 None（依赖未安装）
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None if name == "rapidocr_onnxruntime" else importlib.util.find_spec.__wrapped__(name) if hasattr(importlib.util.find_spec, "__wrapped__") else None)
    with pytest.raises(RuntimeError, match="requirements-rapidocr.txt"):
        cfg.validate_runtime_config()


def test_03b_ocr_rapidocr_with_dep_ok(monkeypatch):
    """OCR=rapidocr + 已装依赖 → 不抛"""
    monkeypatch.setattr(cfg, "OCR_PROVIDER", "rapidocr")
    monkeypatch.setattr(cfg, "SECRET_KEY", "x" * 48)
    monkeypatch.setattr(cfg, "DEV_MODE", False)
    # mock find_spec 返回非 None（依赖已安装）
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "rapidocr_onnxruntime" else None)
    cfg.validate_runtime_config()  # 不抛即通过


# ==================== 4. OCR=非法值 → 抛 RuntimeError 列出合法取值 ====================

def test_04_ocr_typo_raises_with_legal_values(monkeypatch):
    """OCR=typo（非法值）→ RuntimeError 列出 baidu|rapidocr|none"""
    monkeypatch.setattr(cfg, "OCR_PROVIDER", "typo")
    monkeypatch.setattr(cfg, "SECRET_KEY", "x" * 48)
    monkeypatch.setattr(cfg, "DEV_MODE", False)
    with pytest.raises(RuntimeError) as exc_info:
        cfg.validate_runtime_config()
    msg = str(exc_info.value)
    assert "baidu" in msg and "rapidocr" in msg and "none" in msg, \
        f"应列出合法取值，实际：{msg}"
