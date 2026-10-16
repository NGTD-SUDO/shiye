"""AI 路由：学情报告（T5-2）+ 测评出题 / 判分（T9-4）

- 学情报告：同步生成 + 每用户 5 分钟限流
- 测评：`POST /ai/quiz/generate` 出题落库、`POST /ai/quiz/grade` 判分落库
  限流沿用「每用户冷却」模式（独立冷却常量），0 页 / 数据不足走真实空态
"""
import logging
import math
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.quiz import (
    ANSWER_HARD_MAX_CHARS,
    GRADE_FORMAT_ERROR,
    QUIZ_MIN_BODY_CHARS,
    QUIZ_MIN_PAGES,
    QUIZ_QUESTION_COUNT,
    build_grade_payload,
    build_quiz_payload,
)
from app.ai.service import (
    build_study_payload,
    collect_page_samples,
    generate_quiz_text,
    grade_quiz_text,
    study_report_text,
)
from app.config import QUIZ_COOLDOWN_SECONDS, STUDY_REPORT_COOLDOWN_SECONDS
from app.database import get_db
from app.models.quiz import SESSION_GRADED, SESSION_PENDING, QuizQuestion, QuizSession
from app.models.user import User
from app.routers.deps import get_current_user
from app.routers.pages import get_ai_provider_dep
from app.services.access import require_subject
from app.services.study_stats import compute_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])


class StudyReportRequest(BaseModel):
    subject_id: int | None = None


class QuizGenerateRequest(BaseModel):
    subject_id: int | None = None


class QuizAnswer(BaseModel):
    question_id: int
    # 接口层硬上限（超长直接 422，比一路送到 AI 更省成本、错误也更明确）；
    # payload 侧还会再按 ANSWER_MAX_CHARS 截断（见 build_grade_payload）
    answer_text: str = Field(default="", max_length=ANSWER_HARD_MAX_CHARS)


class QuizGradeRequest(BaseModel):
    session_id: int
    answers: list[QuizAnswer]


# 进程内限流表：{user_id: 上次成功生成的时间戳（epoch 秒）}
# 单进程部署足够（任务书约定）；重启后自然清零，不做持久化。
_last_report_at: dict[int, float] = {}
# 测评出题的独立冷却表（与学情报告互不影响）
_last_quiz_at: dict[int, float] = {}


def _prune_rate_table(table: dict[int, float], now: float, cooldown: int) -> None:
    """惰性清理限流表：移除已过冷却窗口的条目，避免表只增不减（进程长跑内存泄漏）"""
    stale = [uid for uid, ts in table.items() if now - ts >= cooldown]
    for uid in stale:
        table.pop(uid, None)


def _rate_limit_response(user_id: int, table: dict[int, float], cooldown: int) -> JSONResponse | None:
    """每用户冷却限流：命中返回 429 响应（含 retry_after_seconds，与 T7 契约一致），否则 None"""
    now = time.time()
    _prune_rate_table(table, now, cooldown)
    last = table.get(user_id)
    if last is not None and now - last < cooldown:
        remaining = max(1, int(cooldown - (now - last)))
        minutes = math.ceil(remaining / 60)
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"太频繁了，请 {minutes} 分钟后再试",
                "retry_after_seconds": remaining,
            },
        )
    return None


@router.post("/study-report")
def study_report(
    payload: StudyReportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider=Depends(get_ai_provider_dep),
):
    """同步生成 AI 学情报告（约 5~15s）。

    0 页不调 AI；AI 未配置 503；AI 失败 502；限流命中 429。
    """
    # 1. 校验 subject_id 归属（不属于 → 404，不泄露存在性）
    if payload.subject_id is not None:
        require_subject(db, user.id, payload.subject_id)

    # 2. 计算统计
    stats = compute_stats(db, user.id, payload.subject_id)

    # 3. 0 页 → 不调 AI，返回空态（前端走真实空态）
    if stats["total_pages"] == 0:
        return {"report_md": None, "stats": stats, "empty": True}

    # 4. 限流（只有真正要调 AI 才消耗冷却；0 页在上面已返回）
    now = time.time()
    limited = _rate_limit_response(user.id, _last_report_at, STUDY_REPORT_COOLDOWN_SECONDS)
    if limited is not None:
        return limited

    # 5. AI 未配置 → 503（不返回假报告）
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail="AI 服务未配置（SHIYE_DEEPSEEK_API_KEY 为空），无法生成学情报告",
        )

    # 6. 组装 payload（统计 + 趋势 + 标题 + 正文摘要，T9-1）+ 调 AI
    samples = collect_page_samples(db, user.id, payload.subject_id)
    prompt_payload = build_study_payload(stats, samples=samples)
    try:
        report_md = study_report_text(provider, prompt_payload)
    except RuntimeError as exc:
        # AI 调用失败 → 502 + 中文文案（绝不返回编造内容）
        raise HTTPException(status_code=502, detail=str(exc))

    # 成功才记录限流时间（失败不消耗冷却，允许用户立刻重试）
    _last_report_at[user.id] = now

    return {
        "report_md": report_md,
        "stats": stats,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/quiz/generate")
def quiz_generate(
    payload: QuizGenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider=Depends(get_ai_provider_dep),
):
    """基于笔记内容出题（T9-4）：真调 AI，落库 session + 题目；不返回参考答案。

    数据不足走真实空态（不调 AI、不落库）；AI 未配置 503；AI 失败 / 格式异常 502；限流 429。
    """
    # 1. 校验 subject_id 归属（不属于 → 404，不泄露存在性）
    if payload.subject_id is not None:
        require_subject(db, user.id, payload.subject_id)

    # 2. 收集可用内容样本（done 且正文非空），用于空态判定与 payload
    samples = collect_page_samples(db, user.id, payload.subject_id)
    total_chars = sum(len(s["body"]) for s in samples)
    scope_name = "该学科" if payload.subject_id is not None else "当前"

    # 3. 数据不足 → 如实空态（不调 AI、不落库、不消耗冷却）
    if len(samples) < QUIZ_MIN_PAGES:
        return {
            "empty": True,
            "reason": f"{scope_name}可用笔记仅 {len(samples)} 页，至少 {QUIZ_MIN_PAGES} 页才能出题",
        }
    if total_chars < QUIZ_MIN_BODY_CHARS:
        return {
            "empty": True,
            "reason": (
                f"{scope_name}笔记正文过少（合计 {total_chars} 字），"
                f"至少 {QUIZ_MIN_BODY_CHARS} 字才能出题"
            ),
        }

    # 4. 限流（真正要调 AI 时才检查；空态在上面已返回）
    limited = _rate_limit_response(user.id, _last_quiz_at, QUIZ_COOLDOWN_SECONDS)
    if limited is not None:
        return limited

    # 5. AI 未配置 → 503（绝不返回编造的题目）
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail="AI 服务未配置（SHIYE_DEEPSEEK_API_KEY 为空），无法出题",
        )

    # 6. 组装 payload（复用 T9-1：含统计、趋势、标题与正文摘要）+ 出题
    stats = compute_stats(db, user.id, payload.subject_id)
    prompt_payload = build_quiz_payload(stats, samples=samples)
    try:
        questions = generate_quiz_text(provider, prompt_payload, QUIZ_QUESTION_COUNT)
    except RuntimeError as exc:
        # AI 调用失败或输出无法解析为严格 JSON → 502（绝不落库半截数据）
        raise HTTPException(status_code=502, detail=str(exc))

    # 7. 落库：session + 题目（参考答案仅存后端，不返回）
    session = QuizSession(
        user_id=user.id,
        subject_id=payload.subject_id,
        status=SESSION_PENDING,
        payload_snapshot=prompt_payload,
    )
    db.add(session)
    db.flush()
    rows: list[QuizQuestion] = []
    for seq, item in enumerate(questions, start=1):
        row = QuizQuestion(
            session_id=session.id,
            seq=seq,
            question=item["question"],
            reference_answer=item["reference_answer"],
            knowledge_point=item["knowledge_point"],
        )
        db.add(row)
        rows.append(row)
    db.commit()
    session_id = session.id

    # 成功才记录限流时间
    _last_quiz_at[user.id] = time.time()

    return {
        "session_id": session_id,
        "questions": [
            {
                "question_id": row.id,
                "seq": row.seq,
                "question": row.question,
                "knowledge_point": row.knowledge_point,
            }
            for row in rows
        ],
    }


@router.post("/quiz/grade")
def quiz_grade(
    payload: QuizGradeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider=Depends(get_ai_provider_dep),
):
    """按用户真实作答判分（T9-4）：跨用户 404；重复判分 400；作答不匹配 400。

    AI 未配置 503；AI 失败 / 格式异常 / 题数不符 502（绝不返回编造分数）。
    """
    # 1. 归属校验：不属于当前用户一律 404（不泄露存在性）
    session = db.get(QuizSession, payload.session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="测评不存在")

    # 2. 已判分 → 明确报错，不重复判分
    if session.status == SESSION_GRADED:
        raise HTTPException(status_code=400, detail="该测评已完成判分，不能重复判分")

    rows = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.session_id == session.id)
        .order_by(QuizQuestion.seq)
        .all()
    )

    # 3. 作答条数必须与题目数一致
    if len(payload.answers) != len(rows):
        raise HTTPException(
            status_code=400,
            detail=f"作答数量与题目数量不一致（题目 {len(rows)} 道，作答 {len(payload.answers)} 条）",
        )
    # 4. 题目必须属于该 session，且不允许重复作答同一题
    row_by_id = {row.id: row for row in rows}
    answer_ids = [a.question_id for a in payload.answers]
    if len(set(answer_ids)) != len(answer_ids):
        raise HTTPException(status_code=400, detail="作答中存在重复题目")
    if any(qid not in row_by_id for qid in answer_ids):
        raise HTTPException(status_code=400, detail="作答中存在不属于该测评的题目")

    # 5. AI 未配置 → 503（判分必须真调 AI，绝不本地编分数）
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail="AI 服务未配置（SHIYE_DEEPSEEK_API_KEY 为空），无法判分",
        )

    answer_by_id = {a.question_id: (a.answer_text or "") for a in payload.answers}
    ordered = [
        {
            "seq": row.seq,
            "question": row.question,
            "reference_answer": row.reference_answer,
            "knowledge_point": row.knowledge_point,
            "user_answer": answer_by_id[row.id],
        }
        for row in rows
    ]
    grade_payload = build_grade_payload(ordered)
    try:
        result = grade_quiz_text(provider, grade_payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # 6. AI 返回的题数必须与题目数一致，否则视为 AI 输出异常：
    #    统一用 502 + 与其它 AI 格式异常相同的文案（见 quiz.GRADE_FORMAT_ERROR）。
    #    与「作答条数不符 → 400」的区别：后者是**客户端输入错误**（可修正后重试），
    #    而本题数不符是**上游 AI 输出不可用**，不应归咎客户端，故走 502。
    if len(result["results"]) != len(rows):
        raise HTTPException(status_code=502, detail=GRADE_FORMAT_ERROR)

    # 7. 写回每题判分 + 会话总评（status → graded）
    #    ⚠️ **不**回写 knowledge_point：它是出题期确定的诊断主键（T9-4：用于后续诊断聚合），
    #    判分时 AI 的措辞漂移会污染聚合口径；接口返回值仍取库中原值（契约不变）。
    for row, res in zip(rows, result["results"]):
        row.is_correct = res["is_correct"]
        row.comment = res["comment"]
        row.mastery = res["mastery"]
        row.user_answer = answer_by_id[row.id]
    session.summary = result["summary"]
    session.status = SESSION_GRADED
    session.graded_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "session_id": session.id,
        "status": session.status,
        "results": [
            {
                "question_id": row.id,
                "seq": row.seq,
                "question": row.question,
                "knowledge_point": row.knowledge_point,
                "user_answer": row.user_answer,
                "is_correct": row.is_correct,
                "mastery": row.mastery,
                "comment": row.comment,
            }
            for row in rows
        ],
        "summary": session.summary,
        "suggestions": result["suggestions"],
    }
