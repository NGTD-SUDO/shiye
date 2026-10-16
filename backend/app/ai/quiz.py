"""出题 / 判分（T9-3）：payload 组装 + 严格 JSON 解析

设计原则（本批铁律）：
- **纯函数优先**（除拼接字符串外无副作用），便于单测
- AI 输出**必须**能解析为严格 JSON；解析失败一律抛中文 `RuntimeError`，
  **绝不返回半截 / 猜测的题目或分数**（宁可 502 也不给假数据）
- 出题 / 判分的 payload **必须含正文摘要**：直接复用 T9-1 的 `build_study_payload`
"""
import json

# 出题数量（本批固定 3，仍由参数传入便于后续调整）
QUIZ_QUESTION_COUNT = 3
# T9-5 空态阈值：可用（OCR 完成且正文非空）页数下限
QUIZ_MIN_PAGES = 3
# T9-5 空态阈值：可用正文合计字数的下限
QUIZ_MIN_BODY_CHARS = 300

# 每题必需字段（出题）
QUESTION_FIELDS = ("question", "reference_answer", "knowledge_point")
# 掌握程度合法取值（判分）
MASTERY_LEVELS = ("good", "partial", "weak")

# 判分 payload 的成本控制（与出题侧 BODY_MAX_CHARS 对称：出题有上限，判分也必须有）
# 单个「用户作答」进入 payload 的最大字数：超出截断，并在 payload 末尾标注已截断
ANSWER_MAX_CHARS = 800
# 接口层硬上限：超过直接 422（比一路送到 AI 更省成本、错误也更明确）
ANSWER_HARD_MAX_CHARS = 2000
# 题干 / 参考答案进入 payload 的最大字数（题目由 AI 生成通常较短，但参考答案可能很长）
QUESTION_MAX_CHARS = 2000
REFERENCE_ANSWER_MAX_CHARS = 2000
# 截断标注（让 AI 知道作答内容不完整，避免把「内容被截断」误判为「作答缺漏」）
ANSWER_TRUNCATED_NOTE = "（作答过长已截断）"

# 统一的中文错误文案（对外可操作、不含堆栈）
QUIZ_FORMAT_ERROR = "AI 返回的题目格式异常，请稍后重试"
GRADE_FORMAT_ERROR = "AI 返回的判分格式异常，请稍后重试"


def strip_code_fence(raw: str) -> str:
    """从模型输出里提取出「待解析的 JSON 文本」。

    只做**确定性的定位**，不做任何猜测或补全：
    1. 若存在 Markdown 代码块 ``` --- ```，取其中内容（**允许代码块前有解释文字**，如「好的，以下是题目：\\n```json」）；
    2. 否则若文中有成对的 `{ ... }`，取第一个 `{` 到最后一个 `}` 之间（仍要求整体是**完整合法 JSON**）；
    3. 其它情况原样返回，交由 `json.loads` 判定失败。

    无论走哪条路径，最终都必须能被解析为完整 JSON 对象，**绝不猜测/拼补半截数据**。
    """
    text = (raw or "").strip()
    if not text:
        return text

    # 1) 代码块（允许前置解释文字）
    fence = text.find("```")
    if fence != -1:
        after = text[fence + 3:]
        newline = after.find("\n")
        if newline != -1:
            body = after[newline + 1:]
            end = body.find("```")
            if end != -1:
                body = body[:end]
            inner = body.strip()
            if inner.lower().startswith("json"):
                inner = inner[4:].strip()
            return inner
        # 单行 ```...```：去掉语言标识与反引号
        inner = after.strip().strip("`").strip()
        if inner.lower().startswith("json"):
            inner = inner[4:].strip()
        return inner

    # 2) 无代码块：截取最外层 { ... }（前后可以有解释文字）
    left = text.find("{")
    right = text.rfind("}")
    if left != -1 and right > left:
        return text[left:right + 1]

    return text


def _extract_json_object(raw: str) -> dict:
    """提取 JSON 对象；失败抛 ValueError（由调用方转中文 RuntimeError）。"""
    data = json.loads(strip_code_fence(raw))
    if not isinstance(data, dict):
        raise ValueError("顶层不是 JSON 对象")
    return data


def _is_non_empty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_quiz_json(raw: str, count: int = QUIZ_QUESTION_COUNT) -> list[dict]:
    """解析 AI 出题结果（严格）：返回 `count` 道题，每项含题干 / 参考答案 / 知识点。

    任何不符合（非法 JSON、题数不符、缺字段、字段非字符串）→ 抛中文 RuntimeError。
    """
    try:
        data = _extract_json_object(raw)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(QUIZ_FORMAT_ERROR) from exc

    questions = data.get("questions")
    if not isinstance(questions, list) or len(questions) != count:
        raise RuntimeError(QUIZ_FORMAT_ERROR)

    parsed: list[dict] = []
    for item in questions:
        if not isinstance(item, dict):
            raise RuntimeError(QUIZ_FORMAT_ERROR)
        if not all(_is_non_empty_str(item.get(field)) for field in QUESTION_FIELDS):
            raise RuntimeError(QUIZ_FORMAT_ERROR)
        parsed.append({
            "question": item["question"].strip(),
            "reference_answer": item["reference_answer"].strip(),
            "knowledge_point": item["knowledge_point"].strip(),
        })
    return parsed


def parse_grade_json(raw: str) -> dict:
    """解析 AI 判分结果（严格）：返回 `{results, summary, suggestions}`。

    每题须含 `is_correct`(bool) / `comment`(非空 str) / `knowledge_point`(非空 str) /
    `mastery`(good|partial|weak)；整体须含 `summary`(非空 str) 与 `suggestions`(str 列表)。
    任何不符合 → 抛中文 RuntimeError（绝不返回半截数据）。
    题数校验由调用方按本次题目数完成。
    """
    try:
        data = _extract_json_object(raw)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(GRADE_FORMAT_ERROR) from exc

    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise RuntimeError(GRADE_FORMAT_ERROR)

    parsed_results: list[dict] = []
    for item in results:
        if not isinstance(item, dict):
            raise RuntimeError(GRADE_FORMAT_ERROR)
        if not isinstance(item.get("is_correct"), bool):
            raise RuntimeError(GRADE_FORMAT_ERROR)
        if not _is_non_empty_str(item.get("comment")):
            raise RuntimeError(GRADE_FORMAT_ERROR)
        if not _is_non_empty_str(item.get("knowledge_point")):
            raise RuntimeError(GRADE_FORMAT_ERROR)
        if item.get("mastery") not in MASTERY_LEVELS:
            raise RuntimeError(GRADE_FORMAT_ERROR)
        parsed_results.append({
            "is_correct": item["is_correct"],
            "comment": item["comment"].strip(),
            "knowledge_point": item["knowledge_point"].strip(),
            "mastery": item["mastery"],
        })

    summary = data.get("summary")
    if not _is_non_empty_str(summary):
        raise RuntimeError(GRADE_FORMAT_ERROR)

    suggestions = data.get("suggestions")
    if not isinstance(suggestions, list) or not all(_is_non_empty_str(s) for s in suggestions):
        raise RuntimeError(GRADE_FORMAT_ERROR)

    return {
        "results": parsed_results,
        "summary": summary.strip(),
        "suggestions": [s.strip() for s in suggestions],
    }


def build_quiz_payload(stats: dict, samples: list[dict] | None = None, today=None) -> str:
    """出题 payload：**复用 T9-1 的组装逻辑**，保证 AI 看到正文摘要而非只有标题。"""
    from app.ai.service import build_study_payload

    return build_study_payload(stats, samples=samples, today=today)


def _clip(text: str, limit: int) -> str:
    """空白归一后按字数截断（不追加省略号）；供判分 payload 成本控制使用"""
    return " ".join((text or "").split())[:limit]


def build_grade_payload(questions: list[dict]) -> str:
    """判分 payload（纯函数）：按题目顺序给出题干、参考答案与用户真实作答。

    成本控制（与出题侧 `BODY_MAX_CHARS` 对称）：题干 / 参考答案 / 用户作答均按常量截断，
    任一处发生截断时在 payload 末尾标注 [ANSWER_TRUNCATED_NOTE]，让 AI 知道内容不完整。

    Args:
        questions: 每项含 `seq` / `question` / `reference_answer` / `knowledge_point` /
            `user_answer`
    """
    lines: list[str] = ["【题目与用户作答】"]
    lines.append(f"- 共 {len(questions)} 道题")
    any_truncated = False
    for q in questions:
        question = _clip(q["question"], QUESTION_MAX_CHARS)
        reference = _clip(q["reference_answer"], REFERENCE_ANSWER_MAX_CHARS)
        raw_answer = q.get("user_answer") or ""
        answer = _clip(raw_answer, ANSWER_MAX_CHARS)
        if len(" ".join(raw_answer.split())) > ANSWER_MAX_CHARS:
            any_truncated = True
        lines.append("")
        lines.append(f"{q['seq']}. 题目：{question}")
        lines.append(f"   考查知识点：{q.get('knowledge_point') or '(未标注)'}")
        lines.append(f"   参考答案：{reference}")
        lines.append(f"   用户作答：{answer or '(未作答)'}")
    lines.append("")
    lines.append("请仅依据上面「用户作答」的实际内容判分，不要用参考答案套话点评。")
    if any_truncated:
        lines.append(ANSWER_TRUNCATED_NOTE)
    return "\n".join(lines)
