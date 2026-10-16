"""AI 服务层测试：用 mock 验证 prompt 构造与错误处理"""
from unittest.mock import patch, MagicMock

import pytest

from app.ai.base import AiProvider
from app.ai.service import create_provider, organize_text
from app.ai.deepseek_impl import DeepSeekAiProvider


class FakeAiProvider(AiProvider):
    def __init__(self, return_text: str = "# 整理后标题\n- 要点1"):
        self.return_text = return_text
        self.calls: list[tuple[str, str]] = []

    def organize(self, text: str, scope: str) -> str:
        self.calls.append((text, scope))
        return self.return_text

    def study_report(self, payload: str) -> str:
        return "# 学情报告\n（仅供参考）"

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


def test_organize_text_calls_provider():
    provider = FakeAiProvider()
    result = organize_text(provider, "原始文本", "page")
    assert result == "# 整理后标题\n- 要点1"
    assert provider.calls == [("原始文本", "page")]


def test_organize_text_no_provider_raises():
    with pytest.raises(RuntimeError, match="AI 服务未配置"):
        organize_text(None, "text", "page")


def test_organize_text_empty_text_returns_empty():
    result = DeepSeekAiProvider(api_key="fake").organize("", "page")
    assert result == ""


def test_deepseek_provider_constructs_correct_request():
    provider = DeepSeekAiProvider(api_key="test-key", base_url="https://fake", model="test-model")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": "# 结果"}}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ai.deepseek_impl.httpx.post", return_value=mock_resp) as mock_post:
        result = provider.organize("导数公式", "page")
        assert result == "# 结果"
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://fake/chat/completions"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-key"
        messages = call_args[1]["json"]["messages"]
        assert messages[0]["role"] == "system"
        assert "纠错" in messages[0]["content"]
        assert "导数公式" in messages[1]["content"]
        assert "单页" in messages[1]["content"]


def test_deepseek_provider_no_api_key_raises():
    provider = DeepSeekAiProvider(api_key="")
    with pytest.raises(RuntimeError, match="API Key 未配置"):
        provider.organize("text", "page")
