"""AI 整理端点集成测试"""
import pytest

from app.ai.base import AiProvider
from app.routers.pages import get_ai_provider_dep
from tests.conftest import auth_headers, make_jpg_bytes


class FakeAiProvider(AiProvider):
    def organize(self, text: str, scope: str) -> str:
        return f"# 整理结果\n- 原文长度：{len(text)}\n- 范围：{scope}"

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


@pytest.fixture
def ai_override(client):
    """用假 AI Provider 覆盖依赖"""
    from app.main import app as fastapi_app
    fastapi_app.dependency_overrides[get_ai_provider_dep] = lambda: FakeAiProvider()
    yield
    fastapi_app.dependency_overrides.pop(get_ai_provider_dep, None)


def _create_page(client, headers) -> int:
    """创建一个 OCR 已完成的页"""
    r = client.post("/subjects", json={"name": "测试"}, headers=headers)
    assert r.status_code == 201
    sid = r.json()["id"]
    r = client.post(
        "/pages",
        headers=headers,
        data={"subject_id": str(sid)},
        files={"file": ("test.jpg", make_jpg_bytes(), "image/jpeg")},
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_organize_page_success(client, ai_override):
    h = auth_headers(client)
    pid = _create_page(client, h)
    r = client.post(f"/pages/{pid}/organize", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["structured_text"] is not None
    assert "整理结果" in data["structured_text"]
    assert "page" in data["structured_text"]


def test_organize_page_empty_text_400(client, ai_override):
    h = auth_headers(client)
    pid = _create_page(client, h)
    client.patch(f"/pages/{pid}", headers=h, json={"ocr_text": ""})
    r = client.post(f"/pages/{pid}/organize", headers=h)
    assert r.status_code == 400


def test_organize_page_no_permission(client, ai_override):
    h1 = auth_headers(client, "user1")
    h2 = auth_headers(client, "user2")
    pid = _create_page(client, h1)
    r = client.post(f"/pages/{pid}/organize", headers=h2)
    assert r.status_code == 404


def test_organize_page_no_provider_503(client):
    """未配置 AI 时返回 503"""
    from app.main import app as fastapi_app
    # 不覆盖依赖，create_provider 返回 None（测试环境无 API Key）
    h = auth_headers(client)
    pid = _create_page(client, h)
    r = client.post(f"/pages/{pid}/organize", headers=h)
    assert r.status_code == 503


def test_organize_chapter_success(client, ai_override):
    h = auth_headers(client)
    # 建学科
    r = client.post("/subjects", json={"name": "测试"}, headers=h)
    sid = r.json()["id"]
    # 建章
    r = client.post(f"/subjects/{sid}/chapters", json={"name": "第一章"}, headers=h)
    cid = r.json()["id"]
    # 上传页并归入章
    r = client.post(
        "/pages",
        headers=h,
        data={"subject_id": str(sid), "chapter_id": str(cid)},
        files={"file": ("test.jpg", make_jpg_bytes(), "image/jpeg")},
    )
    assert r.status_code == 201
    # 整理章
    r = client.post(f"/subjects/{sid}/chapters/{cid}/organize", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "structured_text" in data
    assert "chapter" in data["structured_text"]


def test_organize_chapter_empty_400(client, ai_override):
    h = auth_headers(client)
    r = client.post("/subjects", json={"name": "测试"}, headers=h)
    sid = r.json()["id"]
    r = client.post(f"/subjects/{sid}/chapters", json={"name": "空章"}, headers=h)
    cid = r.json()["id"]
    r = client.post(f"/subjects/{sid}/chapters/{cid}/organize", headers=h)
    assert r.status_code == 400
