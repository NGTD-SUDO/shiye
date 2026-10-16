"""T5-2 AI 学情报告测试：payload 成本控制 / 限流 / 空态 / 503/502 / 「仅供参考」"""
import time
from unittest.mock import patch

import pytest

from app.ai.base import AiProvider
from app.ai.deepseek_impl import DeepSeekAiProvider
from app.ai.service import build_study_payload
from app.routers.pages import get_ai_provider_dep
from tests.conftest import auth_headers, make_jpg_bytes


class FakeAiProvider(AiProvider):
    """记录 study_report 调用次数的假 provider"""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[str] = []

    def organize(self, text: str, scope: str) -> str:
        return "# 整理"

    def study_report(self, payload: str) -> str:
        self.calls.append(payload)
        if self.fail:
            raise RuntimeError("DeepSeek 请求超时，请检查网络后重试")
        return "① 本阶段学习概况\n...\n（仅供参考）"

    # T9-3：AiProvider 新增抽象方法，桩需实现（否则无法实例化）
    def generate_quiz(self, payload: str, count: int) -> list[dict]:
        return [
            {"question": f"题{i + 1}", "reference_answer": "参考答案", "knowledge_point": "考点"}
            for i in range(count)
        ]

    def grade_quiz(self, payload: str) -> dict:
        return {
            "results": [
                {"is_correct": True, "comment": "点评", "knowledge_point": "考点", "mastery": "good"}
            ],
            "summary": "总评",
            "suggestions": [],
        }


@pytest.fixture
def ai_override():
    from app.main import app as fastapi_app

    fake = FakeAiProvider()
    fastapi_app.dependency_overrides[get_ai_provider_dep] = lambda: fake
    yield fake
    fastapi_app.dependency_overrides.pop(get_ai_provider_dep, None)


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """每个用例前清空限流表，避免跨用例污染（都用默认 dev_tester_1）"""
    from app.routers import ai as ai_router

    ai_router._last_report_at.clear()
    yield
    ai_router._last_report_at.clear()


def _create_page_with_data(client, headers) -> int:
    """建学科 + 上传一页（OCR done），返回 subject_id"""
    r = client.post("/subjects", json={"name": "测试学科"}, headers=headers)
    assert r.status_code == 201
    sid = r.json()["id"]
    r = client.post(
        "/pages",
        headers=headers,
        data={"subject_id": str(sid)},
        files={"file": ("a.jpg", make_jpg_bytes(), "image/jpeg")},
    )
    assert r.status_code == 201
    return sid


# ==================== payload 成本控制（纯函数） ====================

def _base_stats():
    return {
        "total_pages": 3,
        "ocr_done": 2,
        "ocr_failed": 1,
        "ocr_processing": 0,
        "done_ratio": 2 / 3,
        "subjects": [
            {"subject_id": 1, "name": "数学", "page_count": 3, "done_ratio": 2 / 3, "last_page_at": "2026-09-12T00:00:00+00:00"},
        ],
        "chapters": [
            {"chapter_id": None, "name": "未分章", "page_count": 3, "last_page_at": "2026-09-12T00:00:00+00:00"},
        ],
        "failed_pages": [{"page_id": 1, "title": "错题"}],
        "stale_subjects": [],
        "page_titles": ["导数定义", "立体几何", "错题"],
    }


def test_payload_only_stats_and_titles():
    payload = build_study_payload(_base_stats())
    # 含统计数字、学科名、章名、标题
    assert "3" in payload  # 总页数
    assert "数学" in payload
    assert "未分章" in payload
    assert "导数定义" in payload
    # 不含 OCR 正文、URL、http
    assert "正文内容" not in payload
    assert "ocr_text" not in payload
    assert "http" not in payload
    assert "/files/" not in payload


def test_payload_truncates_title_40():
    long_title = "这是一个非常非常非常非常非常非常非常长的笔记标题用来测试截断行为" * 3  # >40 字
    stats = _base_stats()
    stats["page_titles"] = [long_title]
    payload = build_study_payload(stats)
    assert long_title not in payload  # 完整长标题不在
    assert long_title[:40] in payload  # 截断后 40 字在


def test_payload_caps_200_titles():
    stats = _base_stats()
    stats["page_titles"] = [f"标题{i}" for i in range(250)]
    payload = build_study_payload(stats)
    assert "其余 50 条" in payload  # 报数量
    assert "标题249" not in payload  # 超出 200 的不在
    assert "标题199" in payload  # 第 200 条在


# ==================== 「仅供参考」约束（system prompt） ====================

def test_study_report_system_prompt_has_disclaimer():
    provider = DeepSeekAiProvider(api_key="test-key", base_url="https://fake", model="m")
    mock_resp = type("R", (), {"json": lambda self: {"choices": [{"message": {"content": "报告"}}]}, "status_code": 200})()
    with patch("app.ai.deepseek_impl.httpx.post", return_value=mock_resp) as mock_post:
        provider.study_report("统计 payload")
    messages = mock_post.call_args[1]["json"]["messages"]
    system = messages[0]["content"]
    assert "仅供参考" in system


# ==================== 接口：空态 / 限流 / 503 / 502 ====================

def test_study_report_empty_no_ai_call(client, ai_override):
    h = auth_headers(client)
    # 不建任何页 → 0 页
    r = client.post("/ai/study-report", json={}, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["empty"] is True
    assert data["report_md"] is None
    assert ai_override.calls == []  # AI 未被调用


def test_study_report_success_calls_ai(client, ai_override):
    h = auth_headers(client)
    _create_page_with_data(client, h)
    r = client.post("/ai/study-report", json={}, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["report_md"] is not None
    assert "仅供参考" in data["report_md"]
    assert len(ai_override.calls) == 1


def test_study_report_rate_limit(client, ai_override, monkeypatch):
    h = auth_headers(client)
    _create_page_with_data(client, h)

    r1 = client.post("/ai/study-report", json={}, headers=h)
    assert r1.status_code == 200

    # 第二次立即调 → 429
    r2 = client.post("/ai/study-report", json={}, headers=h)
    assert r2.status_code == 429
    body = r2.json()
    assert "retry_after_seconds" in body
    assert body["retry_after_seconds"] > 0

    # 越过冷却期后可再次成功
    from app.routers import ai as ai_router

    real_time = time.time
    monkeypatch.setattr(ai_router.time, "time", lambda: real_time() + 301)
    r3 = client.post("/ai/study-report", json={}, headers=h)
    assert r3.status_code == 200


def test_study_report_subject_not_owned_404(client, ai_override):
    h1 = auth_headers(client, "owner")
    h2 = auth_headers(client, "other")
    sid = _create_page_with_data(client, h1)
    # other 用户传 owner 的 subject_id → 404
    r = client.post("/ai/study-report", json={"subject_id": sid}, headers=h2)
    assert r.status_code == 404


def test_study_report_no_provider_503(client):
    # 不覆盖 provider 依赖 → create_provider 返回 None（测试环境无 API Key）
    h = auth_headers(client)
    _create_page_with_data(client, h)
    r = client.post("/ai/study-report", json={}, headers=h)
    assert r.status_code == 503


def test_study_report_ai_error_502_no_stacktrace(client):
    from app.main import app as fastapi_app

    failing = FakeAiProvider(fail=True)
    fastapi_app.dependency_overrides[get_ai_provider_dep] = lambda: failing
    try:
        h = auth_headers(client)
        _create_page_with_data(client, h)
        r = client.post("/ai/study-report", json={}, headers=h)
        assert r.status_code == 502
        text = r.text
        assert "Traceback" not in text  # 响应体不含堆栈
        assert "File " not in text
    finally:
        fastapi_app.dependency_overrides.pop(get_ai_provider_dep, None)
