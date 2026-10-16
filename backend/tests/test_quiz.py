"""T9-3 / T9-4 / T9-5 测评（出题 + 判分）测试

覆盖：
- 严格 JSON 解析（合法 / 非法 JSON / 题数不符 / 缺字段 / 掌握程度非法 / 代码块包裹）
- 出题：空态（0 页 / 不足 3 页 / 正文不足 300 字）不调 AI；成功返回 3 题且**不含参考答案**
- 判分：按真实作答给出每题 is_correct/mastery + summary + suggestions
- **安全（高）**：跨用户 session / subject 一律 404；重复判分 400；作答条数/归属不匹配 400
- AI 未配置 503；AI 失败 502；AI 返回非法 JSON 502（绝不返回半截数据）
- 限流：冷却内重复出题 429（含 retry_after_seconds，与 T7 契约一致）
- payload 复用 T9-1：出题 payload 必须含正文摘要
"""
import json

import pytest

from app.ai.base import AiProvider
from app.ai.quiz import (
    ANSWER_HARD_MAX_CHARS,
    ANSWER_MAX_CHARS,
    ANSWER_TRUNCATED_NOTE,
    QUESTION_MAX_CHARS,
    REFERENCE_ANSWER_MAX_CHARS,
    build_grade_payload,
    parse_grade_json,
    parse_quiz_json,
    strip_code_fence,
)
from app.routers.pages import get_ai_provider_dep
from tests.conftest import auth_headers, make_jpg_bytes

# 足够长（>300 字）的正文，满足出题阈值
LONG_BODY = "导数与极值：导数的定义是函数在某点处的瞬时变化率，极值点处导数为零。" * 12
SHORT_BODY = "短"


def _quiz_json(count: int) -> str:
    return json.dumps(
        {
            "questions": [
                {
                    "question": f"第{i}题：导数的定义是什么？",
                    "reference_answer": f"参考答案{i}",
                    "knowledge_point": f"考点{i}",
                }
                for i in range(1, count + 1)
            ]
        },
        ensure_ascii=False,
    )


def _grade_json(count: int = 3, knowledge_point: str | None = None) -> str:
    return json.dumps(
        {
            "results": [
                {
                    "is_correct": i != 2,
                    "comment": f"第{i}题：针对这次作答的点评",
                    "knowledge_point": knowledge_point or f"考点{i}",
                    "mastery": "good" if i != 2 else "weak",
                }
                for i in range(1, count + 1)
            ],
            "summary": "总体诊断：导数概念基本掌握，极值判断薄弱",
            "suggestions": ["针对考点2：重做极值判断的例题并整理错因"],
        },
        ensure_ascii=False,
    )


class _StubQuizProvider(AiProvider):
    """可配置出题 / 判分原始输出的假 provider（真解析路径，便于断言 502 分支）"""

    def __init__(
        self,
        generate_raw: str | None = None,
        grade_raw: str | None = None,
        fail: bool = False,
        grade_knowledge_point: str | None = None,
    ):
        self.generate_raw = generate_raw
        self.grade_raw = grade_raw
        self.fail = fail
        # 判分时 AI 返回的考点（用于验证「不覆盖出题期考点」）
        self.grade_knowledge_point = grade_knowledge_point
        self.generate_calls = 0
        self.grade_calls = 0
        self.quiz_payloads: list[str] = []
        self.grade_payloads: list[str] = []
        self.question_count = 0

    def organize(self, text: str, scope: str) -> str:
        return "# 整理"

    def study_report(self, payload: str) -> str:
        return "# 报告\n（仅供参考）"

    def generate_quiz(self, payload: str, count: int) -> list[dict]:
        self.generate_calls += 1
        self.quiz_payloads.append(payload)
        self.question_count = count
        if self.fail:
            raise RuntimeError("AI 服务返回错误（HTTP 500），请稍后重试")
        raw = self.generate_raw if self.generate_raw is not None else _quiz_json(count)
        return parse_quiz_json(raw, count)

    def grade_quiz(self, payload: str) -> dict:
        self.grade_calls += 1
        self.grade_payloads.append(payload)
        if self.fail:
            raise RuntimeError("AI 服务返回错误（HTTP 500），请稍后重试")
        if self.grade_raw is not None:
            return parse_grade_json(self.grade_raw)
        return parse_grade_json(_grade_json(self.question_count or 3, self.grade_knowledge_point))


@pytest.fixture
def quiz_ai():
    """覆盖 AI provider 依赖；默认返回固定的假 provider（每个用例可自建覆盖）"""
    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_ai_provider_dep] = lambda: _StubQuizProvider()
    yield
    fastapi_app.dependency_overrides.pop(get_ai_provider_dep, None)


@pytest.fixture(autouse=True)
def _reset_quiz_rate_limit():
    """每个用例前清空出题限流表，避免跨用例污染"""
    from app.routers import ai as ai_router

    ai_router._last_quiz_at.clear()
    yield
    ai_router._last_quiz_at.clear()


def _use_provider(provider: AiProvider) -> None:
    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_ai_provider_dep] = lambda: provider


def _add_pages(client, headers, pages: list[tuple[str, str]], subject_name: str = "数学"):
    """建学科 + 逐页上传并改写标题/正文（OCR 结果由假 provider 立刻置 done）"""
    r = client.post("/subjects", json={"name": subject_name}, headers=headers)
    assert r.status_code == 201, r.text
    subject_id = r.json()["id"]
    page_ids: list[int] = []
    for title, body in pages:
        r = client.post(
            "/pages",
            headers=headers,
            data={"subject_id": str(subject_id)},
            files={"file": ("a.jpg", make_jpg_bytes(), "image/jpeg")},
        )
        assert r.status_code == 201, r.text
        page_id = r.json()["id"]
        r = client.patch(
            f"/pages/{page_id}",
            headers=headers,
            json={"title": title, "ocr_text": body},
        )
        assert r.status_code == 200, r.text
        page_ids.append(page_id)
    return subject_id, page_ids


def _three_pages():
    return [("导数定义", LONG_BODY), ("极值判断", LONG_BODY), ("错题整理", LONG_BODY)]


def _generate_session(client, headers, subject_id: int) -> dict:
    r = client.post("/ai/quiz/generate", json={"subject_id": subject_id}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ==================== 严格 JSON 解析（纯函数） ====================

def test_parse_quiz_json_valid():
    parsed = parse_quiz_json(_quiz_json(3), 3)
    assert len(parsed) == 3
    assert parsed[0]["question"].startswith("第1题")
    assert parsed[2]["knowledge_point"] == "考点3"
    assert set(parsed[0]) == {"question", "reference_answer", "knowledge_point"}


def test_parse_quiz_json_invalid_json_raises_chinese():
    with pytest.raises(RuntimeError) as exc:
        parse_quiz_json("这根本不是 JSON", 3)
    assert "题目格式异常" in str(exc.value)


def test_parse_quiz_json_wrong_count_raises():
    with pytest.raises(RuntimeError, match="题目格式异常"):
        parse_quiz_json(_quiz_json(2), 3)  # 只返回 2 题 → 不许当成功


def test_parse_quiz_json_missing_field_raises():
    raw = json.dumps({"questions": [{"question": "题", "reference_answer": "答"}]}, ensure_ascii=False)
    with pytest.raises(RuntimeError, match="题目格式异常"):
        parse_quiz_json(raw, 1)


def test_parse_quiz_json_code_fence_ok():
    raw = "```json\n" + _quiz_json(1) + "\n```"
    parsed = parse_quiz_json(raw, 1)
    assert len(parsed) == 1


def test_parse_quiz_json_non_object_raises():
    with pytest.raises(RuntimeError, match="题目格式异常"):
        parse_quiz_json("[1, 2, 3]", 1)


def test_parse_grade_json_valid():
    parsed = parse_grade_json(_grade_json(3))
    assert len(parsed["results"]) == 3
    assert parsed["results"][1]["mastery"] == "weak"
    assert parsed["results"][0]["is_correct"] is True
    assert "总体诊断" in parsed["summary"]
    assert parsed["suggestions"]


def test_parse_grade_json_invalid_mastery_raises():
    raw = json.dumps(
        {
            "results": [
                {"is_correct": True, "comment": "好", "knowledge_point": "考点", "mastery": "excellent"}
            ],
            "summary": "总评",
            "suggestions": [],
        },
        ensure_ascii=False,
    )
    with pytest.raises(RuntimeError, match="判分格式异常"):
        parse_grade_json(raw)


def test_parse_grade_json_invalid_json_raises_chinese():
    with pytest.raises(RuntimeError) as exc:
        parse_grade_json("不是 JSON")
    assert "判分格式异常" in str(exc.value)


# ==================== T9-5 空态（不调 AI、不落库） ====================

def test_generate_empty_zero_pages_no_ai_call(client, quiz_ai):
    from app.main import app as fastapi_app

    stub = _StubQuizProvider()
    fastapi_app.dependency_overrides[get_ai_provider_dep] = lambda: stub
    headers = auth_headers(client)
    client.post("/subjects", json={"name": "空学科"}, headers=headers)

    r = client.post("/ai/quiz/generate", json={}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["empty"] is True
    assert "至少 3 页" in data["reason"]
    assert stub.generate_calls == 0  # 未调 AI


def test_generate_empty_too_few_pages_no_ai_call(client, quiz_ai):
    from app.main import app as fastapi_app

    stub = _StubQuizProvider()
    fastapi_app.dependency_overrides[get_ai_provider_dep] = lambda: stub
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, [("页1", LONG_BODY), ("页2", LONG_BODY)])

    r = client.post("/ai/quiz/generate", json={"subject_id": subject_id}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["empty"] is True
    assert "仅 2 页" in data["reason"]
    assert stub.generate_calls == 0


def test_generate_empty_too_few_chars_no_ai_call(client, quiz_ai):
    from app.main import app as fastapi_app

    stub = _StubQuizProvider()
    fastapi_app.dependency_overrides[get_ai_provider_dep] = lambda: stub
    headers = auth_headers(client)
    subject_id, _ = _add_pages(
        client, headers, [("页1", SHORT_BODY), ("页2", SHORT_BODY), ("页3", SHORT_BODY)]
    )

    r = client.post("/ai/quiz/generate", json={"subject_id": subject_id}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["empty"] is True
    assert "正文过少" in data["reason"]
    assert "至少 300 字" in data["reason"]
    assert stub.generate_calls == 0


# ==================== 出题成功 / 失败 ====================

def test_generate_success_returns_three_questions_without_reference_answer(client, quiz_ai):
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())

    data = _generate_session(client, headers, subject_id)
    assert isinstance(data["session_id"], int)
    assert len(data["questions"]) == 3
    for q in data["questions"]:
        assert set(q) == {"question_id", "seq", "question", "knowledge_point"}
        assert "reference_answer" not in q  # 参考答案仅后端持有
    assert [q["seq"] for q in data["questions"]] == [1, 2, 3]


def test_generate_payload_contains_body_summary(client, quiz_ai):
    """T9-3：出题 payload 必须复用 T9-1 组装（含正文摘要），否则题目会脱离笔记内容"""
    from app.main import app as fastapi_app

    stub = _StubQuizProvider()
    fastapi_app.dependency_overrides[get_ai_provider_dep] = lambda: stub
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())

    _generate_session(client, headers, subject_id)
    payload = stub.quiz_payloads[0]
    assert "【页内容摘要】" in payload
    assert "导数的定义是函数在某点处的瞬时变化率" in payload
    assert "【近 30 天记录趋势】" in payload


def test_generate_subject_not_owned_404(client, quiz_ai):
    owner = auth_headers(client, "quiz_owner")
    other = auth_headers(client, "quiz_other")
    subject_id, _ = _add_pages(client, owner, _three_pages())

    r = client.post("/ai/quiz/generate", json={"subject_id": subject_id}, headers=other)
    assert r.status_code == 404


def test_generate_rate_limit_429(client, quiz_ai):
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())

    assert _generate_session(client, headers, subject_id)["session_id"] > 0

    r = client.post("/ai/quiz/generate", json={"subject_id": subject_id}, headers=headers)
    assert r.status_code == 429
    body = r.json()
    assert "retry_after_seconds" in body  # 与 T7 契约一致
    assert body["retry_after_seconds"] > 0


def test_generate_no_provider_503(client):
    """不覆盖 provider → create_provider() 返回 None（测试环境无 Key）"""
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())

    r = client.post("/ai/quiz/generate", json={"subject_id": subject_id}, headers=headers)
    assert r.status_code == 503
    assert "无法出题" in r.json()["detail"]


def test_generate_ai_failure_502_no_stacktrace(client, quiz_ai):
    _use_provider(_StubQuizProvider(fail=True))
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())

    r = client.post("/ai/quiz/generate", json={"subject_id": subject_id}, headers=headers)
    assert r.status_code == 502
    assert "Traceback" not in r.text
    assert "File " not in r.text


def test_generate_invalid_json_502_not_persisted(client, quiz_ai):
    """AI 返回非法 JSON → 502，且**不落库**（绝不返回半截题目）"""
    _use_provider(_StubQuizProvider(generate_raw="这不是合法 JSON"))
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())

    r = client.post("/ai/quiz/generate", json={"subject_id": subject_id}, headers=headers)
    assert r.status_code == 502
    assert "题目格式异常" in r.json()["detail"]

    # 未落库：用猜的 session_id 判分应为 404（说明没有产生脏 session）
    r2 = client.post(
        "/ai/quiz/grade",
        json={"session_id": 1, "answers": []},
        headers=headers,
    )
    assert r2.status_code == 404


# ==================== 判分 ====================

def test_grade_success_returns_diagnosis(client, quiz_ai):
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())
    generated = _generate_session(client, headers, subject_id)
    qids = [q["question_id"] for q in generated["questions"]]

    r = client.post(
        "/ai/quiz/grade",
        json={
            "session_id": generated["session_id"],
            "answers": [
                {"question_id": qids[0], "answer_text": "导数是瞬时变化率"},
                {"question_id": qids[1], "answer_text": "不知道"},
                {"question_id": qids[2], "answer_text": "极值点导数为零"},
            ],
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "graded"
    assert len(data["results"]) == 3
    for item in data["results"]:
        assert isinstance(item["is_correct"], bool)
        assert item["mastery"] in ("good", "partial", "weak")
        assert item["comment"]
    assert data["results"][1]["is_correct"] is False  # 第 2 题（"不知道"）判错
    assert data["summary"]
    assert data["suggestions"]


def test_grade_session_not_owned_404(client, quiz_ai):
    """安全（高）：跨用户用别人的 session_id 判分 → 404，不泄露存在性"""
    owner = auth_headers(client, "grade_owner")
    other = auth_headers(client, "grade_other")
    subject_id, _ = _add_pages(client, owner, _three_pages())
    generated = _generate_session(client, owner, subject_id)
    qids = [q["question_id"] for q in generated["questions"]]

    r = client.post(
        "/ai/quiz/grade",
        json={
            "session_id": generated["session_id"],
            "answers": [{"question_id": q, "answer_text": "x"} for q in qids],
        },
        headers=other,
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "测评不存在"


def test_grade_already_graded_400(client, quiz_ai):
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())
    generated = _generate_session(client, headers, subject_id)
    qids = [q["question_id"] for q in generated["questions"]]
    body = {
        "session_id": generated["session_id"],
        "answers": [{"question_id": q, "answer_text": "答案"} for q in qids],
    }
    assert client.post("/ai/quiz/grade", json=body, headers=headers).status_code == 200

    # 重复判分 → 400
    r = client.post("/ai/quiz/grade", json=body, headers=headers)
    assert r.status_code == 400
    assert "重复判分" in r.json()["detail"]


def test_grade_answer_count_mismatch_400(client, quiz_ai):
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())
    generated = _generate_session(client, headers, subject_id)

    r = client.post(
        "/ai/quiz/grade",
        json={"session_id": generated["session_id"], "answers": []},
        headers=headers,
    )
    assert r.status_code == 400
    assert "不一致" in r.json()["detail"]


def test_grade_question_not_in_session_400(client, quiz_ai):
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())
    generated = _generate_session(client, headers, subject_id)
    qids = [q["question_id"] for q in generated["questions"]]

    r = client.post(
        "/ai/quiz/grade",
        json={
            "session_id": generated["session_id"],
            "answers": [
                {"question_id": qids[0], "answer_text": "a"},
                {"question_id": qids[1], "answer_text": "b"},
                {"question_id": 999999, "answer_text": "c"},
            ],
        },
        headers=headers,
    )
    assert r.status_code == 400
    assert "不属于该测评" in r.json()["detail"]


def test_grade_ai_failure_502(client, quiz_ai):
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())
    generated = _generate_session(client, headers, subject_id)
    qids = [q["question_id"] for q in generated["questions"]]

    _use_provider(_StubQuizProvider(fail=True))
    r = client.post(
        "/ai/quiz/grade",
        json={
            "session_id": generated["session_id"],
            "answers": [{"question_id": q, "answer_text": "答案"} for q in qids],
        },
        headers=headers,
    )
    assert r.status_code == 502
    assert "Traceback" not in r.text

    # 判分失败不得把 session 置为 graded（允许重试）
    _use_provider(_StubQuizProvider())
    r2 = client.post(
        "/ai/quiz/grade",
        json={
            "session_id": generated["session_id"],
            "answers": [{"question_id": q, "answer_text": "答案"} for q in qids],
        },
        headers=headers,
    )
    assert r2.status_code == 200


def test_grade_invalid_json_502(client, quiz_ai):
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())
    generated = _generate_session(client, headers, subject_id)
    qids = [q["question_id"] for q in generated["questions"]]

    _use_provider(_StubQuizProvider(grade_raw="不是 JSON"))
    r = client.post(
        "/ai/quiz/grade",
        json={
            "session_id": generated["session_id"],
            "answers": [{"question_id": q, "answer_text": "答案"} for q in qids],
        },
        headers=headers,
    )
    assert r.status_code == 502
    assert "判分格式异常" in r.json()["detail"]


def test_grade_no_provider_503(client, quiz_ai):
    """AI 未配置 → 503（判分必须真调 AI，绝不本地编分数）"""
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())
    generated = _generate_session(client, headers, subject_id)
    qids = [q["question_id"] for q in generated["questions"]]

    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides.pop(get_ai_provider_dep, None)
    r = client.post(
        "/ai/quiz/grade",
        json={
            "session_id": generated["session_id"],
            "answers": [{"question_id": q, "answer_text": "答案"} for q in qids],
        },
        headers=headers,
    )
    assert r.status_code == 503
    assert "无法判分" in r.json()["detail"]


# ==================== 评审修复：判分输入长度上限（成本控制对称） ====================

def test_build_grade_payload_truncates_long_answer():
    """超长作答必须被截断且有标注（判分侧成本控制与出题侧对称）"""
    long_answer = "答" * 50000
    payload = build_grade_payload([
        {
            "seq": 1,
            "question": "题干",
            "reference_answer": "参考答案",
            "knowledge_point": "考点",
            "user_answer": long_answer,
        }
    ])
    assert ANSWER_TRUNCATED_NOTE in payload
    assert "答" * ANSWER_MAX_CHARS in payload
    assert "答" * (ANSWER_MAX_CHARS + 1) not in payload
    assert long_answer not in payload


def test_build_grade_payload_truncates_long_question_and_reference():
    """题干 / 参考答案同样必须有上限（它们也会进入 payload）"""
    payload = build_grade_payload([
        {
            "seq": 1,
            "question": "问" * 50000,
            "reference_answer": "参" * 50000,
            "knowledge_point": "考点",
            "user_answer": "答",
        }
    ])
    assert "问" * QUESTION_MAX_CHARS in payload
    assert "问" * (QUESTION_MAX_CHARS + 1) not in payload
    assert "参" * REFERENCE_ANSWER_MAX_CHARS in payload
    assert "参" * (REFERENCE_ANSWER_MAX_CHARS + 1) not in payload


def test_build_grade_payload_short_answer_has_no_note():
    payload = build_grade_payload([
        {"seq": 1, "question": "题干", "reference_answer": "参考答案", "knowledge_point": "考点", "user_answer": "短作答"}
    ])
    assert ANSWER_TRUNCATED_NOTE not in payload
    assert "短作答" in payload


def test_grade_answer_too_long_422(client, quiz_ai):
    """接口层硬上限：超长作答直接 422，不至于一路送到 AI"""
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())
    generated = _generate_session(client, headers, subject_id)
    qids = [q["question_id"] for q in generated["questions"]]

    r = client.post(
        "/ai/quiz/grade",
        json={
            "session_id": generated["session_id"],
            "answers": [
                {"question_id": qids[0], "answer_text": "答" * (ANSWER_HARD_MAX_CHARS + 1)},
                {"question_id": qids[1], "answer_text": "b"},
                {"question_id": qids[2], "answer_text": "c"},
            ],
        },
        headers=headers,
    )
    assert r.status_code == 422


def test_grade_long_answer_truncated_before_ai(client, quiz_ai):
    """介于 payload 上限与接口硬上限之间的作答：允许提交，但进 payload 前被截断并标注"""
    from app.main import app as fastapi_app

    stub = _StubQuizProvider()
    fastapi_app.dependency_overrides[get_ai_provider_dep] = lambda: stub
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())
    generated = _generate_session(client, headers, subject_id)
    qids = [q["question_id"] for q in generated["questions"]]

    long_but_allowed = "长" * (ANSWER_MAX_CHARS + 150)  # < ANSWER_HARD_MAX_CHARS
    r = client.post(
        "/ai/quiz/grade",
        json={
            "session_id": generated["session_id"],
            "answers": [
                {"question_id": qids[0], "answer_text": long_but_allowed},
                {"question_id": qids[1], "answer_text": "b"},
                {"question_id": qids[2], "answer_text": "c"},
            ],
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert ANSWER_TRUNCATED_NOTE in stub.grade_payloads[0]
    assert "长" * (ANSWER_MAX_CHARS + 1) not in stub.grade_payloads[0]


# ==================== 评审修复：不覆盖出题期 knowledge_point ====================

def test_grade_keeps_original_knowledge_point(client, quiz_ai):
    """判分不得用 AI 返回的考点覆盖出题时落库的考点（诊断聚合口径必须稳定）"""
    from app.main import app as fastapi_app

    stub = _StubQuizProvider(grade_knowledge_point="AI改过的考点")
    fastapi_app.dependency_overrides[get_ai_provider_dep] = lambda: stub
    headers = auth_headers(client)
    subject_id, _ = _add_pages(client, headers, _three_pages())
    generated = _generate_session(client, headers, subject_id)
    qids = [q["question_id"] for q in generated["questions"]]
    before = [q["knowledge_point"] for q in generated["questions"]]
    assert before == ["考点1", "考点2", "考点3"]

    r = client.post(
        "/ai/quiz/grade",
        json={
            "session_id": generated["session_id"],
            "answers": [{"question_id": q, "answer_text": "答案"} for q in qids],
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    after = [item["knowledge_point"] for item in r.json()["results"]]
    assert after == before, "判分后考点必须与出题时一致"
    assert "AI改过的考点" not in after


# ==================== 评审修复：解析鲁棒性（代码块前有解释文字） ====================

def test_strip_code_fence_with_leading_text():
    raw = "好的，以下是题目：\n```json\n" + _quiz_json(2) + "\n```"
    assert json.loads(strip_code_fence(raw))["questions"]


def test_parse_quiz_json_with_leading_text_and_fence():
    raw = "好的，以下是题目：\n```json\n" + _quiz_json(2) + "\n```\n希望有帮助。"
    assert len(parse_quiz_json(raw, 2)) == 2


def test_parse_quiz_json_with_leading_text_bare_object():
    raw = "好的，以下是题目：\n" + _quiz_json(3)
    assert len(parse_quiz_json(raw, 3)) == 3


def test_parse_grade_json_with_trailing_text():
    raw = _grade_json(2) + "\n以上就是判分结果。"
    assert len(parse_grade_json(raw)["results"]) == 2


def test_parse_quiz_json_prose_without_json_still_raises():
    """没有 JSON 时绝不猜测，仍抛中文错误"""
    with pytest.raises(RuntimeError, match="题目格式异常"):
        parse_quiz_json("好的，但是我忘了输出 JSON，抱歉。", 3)

