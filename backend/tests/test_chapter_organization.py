"""T12-0 整章 AI 整理结果落库 —— 集成测试

覆盖任务书第三节验收：
- 落库生效且**追加不覆盖**（连调两次 → 表里 2 条；接口返回后一条）
- `latest` 取最新一条；空态 **HTTP 200**（不是 404）
- 越权 404 且响应体与「章不存在」**逐字节一致**
- 向后兼容：既有 organize 接口的 `structured_text` 原样返回（只加不删）
- `source_page_count` / `model_name` 的取值口径
"""
import pytest

from app.ai.base import AiProvider
from app.database import get_db
from app.main import app as fastapi_app
from app.models.chapter_organization import ChapterOrganization
from app.routers.pages import get_ai_provider_dep
from tests.conftest import auth_headers, make_jpg_bytes


class _StubProvider(AiProvider):
    """假 AI：每次 organize 产出**不同**（便于验证「追加不覆盖」）。

    `model` 只在显式传入时才挂到实例上 —— 用来分别覆盖
    「provider 暴露模型名」与「provider 不暴露模型名」两条路径。
    """

    def __init__(self, model: str | None = None):
        if model is not None:
            self.model = model
        self.calls = 0

    def organize(self, text: str, scope: str) -> str:
        self.calls += 1
        return f"# 整章整理 第{self.calls}次\n- 范围：{scope}\n- 原文长度：{len(text)}"

    def study_report(self, payload: str) -> str:
        return "# 学情报告\n（仅供参考）"

    def generate_quiz(self, payload: str, count: int) -> list[dict]:
        return [
            {"question": f"题{i + 1}", "reference_answer": "参考答案", "knowledge_point": "考点"}
            for i in range(count)
        ]

    def grade_quiz(self, payload: str) -> dict:
        return {"results": [], "summary": "", "suggestions": []}


@pytest.fixture
def use_provider(client):
    """把 provider 依赖换成指定假实现（用例内可替换多次）。"""

    def _apply(provider: AiProvider) -> None:
        fastapi_app.dependency_overrides[get_ai_provider_dep] = lambda: provider

    yield _apply
    fastapi_app.dependency_overrides.pop(get_ai_provider_dep, None)


def _mk_subject_and_chapter(client, headers) -> tuple[int, int]:
    r = client.post("/subjects", json={"name": "数学"}, headers=headers)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    r = client.post(f"/subjects/{sid}/chapters", json={"name": "第一章"}, headers=headers)
    assert r.status_code == 201, r.text
    return sid, r.json()["id"]


def _add_page(client, headers, sid: int, cid: int) -> int:
    r = client.post(
        "/pages",
        headers=headers,
        data={"subject_id": str(sid), "chapter_id": str(cid)},
        files={"file": ("a.jpg", make_jpg_bytes(), "image/jpeg")},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _org_rows(chapter_id: int) -> list[tuple]:
    """读 API 用的**同一个测试库**里该章的整理记录（按 id 升序）。

    测试库的引擎不对外暴露，因此借 conftest 覆盖进去的 `get_db` 生成器取一个会话；
    先把字段物化成元组，避免会话关闭后再访问 ORM 属性。
    """
    gen = fastapi_app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        rows = (
            db.query(ChapterOrganization)
            .filter(ChapterOrganization.chapter_id == chapter_id)
            .order_by(ChapterOrganization.id)
            .all()
        )
        return [
            (r.id, r.structured_text, r.source_page_count, r.model_name, r.user_id)
            for r in rows
        ]
    finally:
        gen.close()


# ==================== 模型 ====================


def test_model_declares_7_columns():
    """模型声明的 7 列（与任务书 §2.1 一一对应）。真实建表的 PRAGMA 输出见变更说明。"""
    assert list(ChapterOrganization.__table__.columns.keys()) == [
        "id",
        "chapter_id",
        "user_id",
        "structured_text",
        "source_page_count",
        "model_name",
        "created_at",
    ]


# ==================== 落库 + 追加不覆盖 + latest ====================


def test_organize_persists_appends_and_keeps_legacy_fields(client, use_provider):
    use_provider(_StubProvider())
    h = auth_headers(client)
    sid, cid = _mk_subject_and_chapter(client, h)
    _add_page(client, h, sid, cid)

    r1 = client.post(f"/subjects/{sid}/chapters/{cid}/organize", headers=h)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    # 向后兼容：原有三个字段原样在（老前端不破）
    assert d1["chapter_id"] == cid
    assert d1["chapter_name"] == "第一章"
    assert "第1次" in d1["structured_text"]
    # 新增字段
    assert isinstance(d1["organization_id"], int)
    assert isinstance(d1["created_at"], str) and d1["created_at"]

    r2 = client.post(f"/subjects/{sid}/chapters/{cid}/organize", headers=h)
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    assert d2["organization_id"] > d1["organization_id"], "应是新插一行，而不是覆盖旧行"

    rows = _org_rows(cid)
    assert len(rows) == 2, "连调两次应落两条（追加不覆盖）"
    assert "第1次" in rows[0][1], "第一条不能被第二条覆盖"
    assert "第2次" in rows[1][1]

    rl = client.get(f"/subjects/{sid}/chapters/{cid}/organization/latest", headers=h)
    assert rl.status_code == 200, rl.text
    dl = rl.json()
    assert "empty" not in dl
    assert dl["structured_text"] == d2["structured_text"], "latest 应返回最新一条"
    assert dl["created_at"] == d2["created_at"]
    assert dl["source_page_count"] == 1
    assert dl["chapter_id"] == cid


def test_latest_empty_returns_200_not_404(client):
    """从未整理过的章 → 空态 200 + {empty, reason}（不是 404）。"""
    h = auth_headers(client)
    sid, cid = _mk_subject_and_chapter(client, h)

    r = client.get(f"/subjects/{sid}/chapters/{cid}/organization/latest", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["empty"] is True
    assert isinstance(body["reason"], str) and body["reason"]


# ==================== 越权（复用 require_chapter，响应体不可区分）====================


def test_latest_cross_user_404_same_body_as_missing(client):
    """别人用户请求 owner 的章 → 404，且与「章不存在」逐字节一致（不泄露存在性）。"""
    owner = auth_headers(client, "org_owner")
    other = auth_headers(client, "org_other")
    sid, cid = _mk_subject_and_chapter(client, owner)

    r_cross = client.get(f"/subjects/{sid}/chapters/{cid}/organization/latest", headers=other)
    r_missing = client.get("/subjects/999999/chapters/999999/organization/latest", headers=other)
    assert r_cross.status_code == 404
    assert r_missing.status_code == 404
    assert r_cross.text == r_missing.text, "不能通过响应体差异反推「章是否存在 / 属于谁」"


def test_latest_foreign_chapter_under_own_subject_404_same_body(client):
    """别人的 chapter_id 配自己的 subject_id → 与「章不存在」逐字节一致。"""
    owner = auth_headers(client, "org_owner2")
    other = auth_headers(client, "org_other2")
    _sid_owner, cid_owner = _mk_subject_and_chapter(client, owner)
    sid_other, _cid_other = _mk_subject_and_chapter(client, other)

    r = client.get(
        f"/subjects/{sid_other}/chapters/{cid_owner}/organization/latest", headers=other
    )
    r_missing = client.get(
        f"/subjects/{sid_other}/chapters/999999/organization/latest", headers=other
    )
    assert r.status_code == 404
    assert r_missing.status_code == 404
    assert r.text == r_missing.text


# ==================== 字段口径 ====================


def test_source_page_count_counts_only_pages_with_text(client, use_provider):
    """只统计真正参与整理的页（OCR 正文非空）→ 清空一页后应为 1。"""
    use_provider(_StubProvider())
    h = auth_headers(client)
    sid, cid = _mk_subject_and_chapter(client, h)
    _add_page(client, h, sid, cid)
    p2 = _add_page(client, h, sid, cid)

    r = client.patch(f"/pages/{p2}", headers=h, json={"ocr_text": ""})
    assert r.status_code == 200, r.text

    r = client.post(f"/subjects/{sid}/chapters/{cid}/organize", headers=h)
    assert r.status_code == 200, r.text
    rl = client.get(f"/subjects/{sid}/chapters/{cid}/organization/latest", headers=h)
    assert rl.json()["source_page_count"] == 1


def test_model_name_stored_when_provider_exposes_it(client, use_provider):
    use_provider(_StubProvider(model="stub-model-x"))
    h = auth_headers(client)
    sid, cid = _mk_subject_and_chapter(client, h)
    _add_page(client, h, sid, cid)

    client.post(f"/subjects/{sid}/chapters/{cid}/organize", headers=h)
    assert _org_rows(cid)[0][3] == "stub-model-x"


def test_model_name_empty_when_provider_hides_it(client, use_provider):
    """provider 未暴露模型名 → 存空串（**不硬编**一个模型名）。"""
    use_provider(_StubProvider())
    h = auth_headers(client)
    sid, cid = _mk_subject_and_chapter(client, h)
    _add_page(client, h, sid, cid)

    client.post(f"/subjects/{sid}/chapters/{cid}/organize", headers=h)
    assert _org_rows(cid)[0][3] == ""
