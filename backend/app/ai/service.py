"""AI 服务：封装 Provider 创建 + 错误处理 + 学情/测评 payload 组装

T9-1 改造（解决「AI 没内容可分析、只能复述统计数字」）：
- payload **补发**「近 30 天记录趋势」（统计里早有，之前漏发），以「日期: 页数」列出非零项；
  全为零时明确写「近 30 天无记录」，让 AI 不再说「未提供趋势数据」
- **新增**「页内容摘要」段：每页发 `ocr_text` 前 120 字（与标题成对），最多 60 页
- 成本与安全边界保持不变：**绝不包含**图片、签名图片 URL、完整 `ocr_text`、结构化文本
"""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.ai.base import AiProvider
from app.config import DEEPSEEK_API_KEY
from app.models.page import OCR_DONE, Page
from app.services.study_stats import TREND_DAYS

logger = logging.getLogger(__name__)

# 页标题在 payload 里的截断长度（字符）
TITLE_MAX_CHARS = 40
# 页标题最多发多少条
TITLE_MAX_COUNT = 200
# T9-1：每页正文摘要最多多少字（超出截断，不追加省略号）
BODY_MAX_CHARS = 120
# T9-1：正文摘要最多发多少页（超出在末尾注明省略数量）
BODY_MAX_PAGES = 60


def create_provider() -> AiProvider | None:
    """按配置创建 AI 实现；未配置 Key 时返回 None"""
    if not DEEPSEEK_API_KEY:
        logger.warning("DeepSeek API Key 未配置，AI 整理功能不可用")
        return None
    try:
        from app.ai.deepseek_impl import DeepSeekAiProvider
        return DeepSeekAiProvider()
    except Exception as exc:
        logger.warning("加载 DeepSeek AI 失败（%s）", exc)
        return None


def organize_text(provider: AiProvider | None, text: str, scope: str) -> str:
    """整理文本；provider 为 None 时抛异常"""
    if provider is None:
        raise RuntimeError("AI 服务未配置（SHIYE_DEEPSEEK_API_KEY 为空）")
    return provider.organize(text, scope)


def study_report_text(provider: AiProvider | None, payload: str) -> str:
    """生成学情报告；provider 为 None 时抛中文错误"""
    if provider is None:
        raise RuntimeError("AI 服务未配置（SHIYE_DEEPSEEK_API_KEY 为空）")
    return provider.study_report(payload)


def generate_quiz_text(provider: AiProvider | None, payload: str, count: int) -> list[dict]:
    """出题（T9-3）；provider 为 None 时抛中文错误，绝不返回编造题目"""
    if provider is None:
        raise RuntimeError("AI 服务未配置（SHIYE_DEEPSEEK_API_KEY 为空）")
    return provider.generate_quiz(payload, count)


def grade_quiz_text(provider: AiProvider | None, payload: str) -> dict:
    """判分（T9-3）；provider 为 None 时抛中文错误，绝不返回编造分数"""
    if provider is None:
        raise RuntimeError("AI 服务未配置（SHIYE_DEEPSEEK_API_KEY 为空）")
    return provider.grade_quiz(payload)


def collect_page_samples(
    db: Session,
    user_id: int,
    subject_id: int | None = None,
) -> list[dict]:
    """收集用于内容分析的页样本：「标题 + 正文」成对，按页 id 升序（稳定可测）。

    只取 OCR 完成（done）且正文非空的页；**绝不**返回图片、签名 URL、结构化文本。
    返回原始（未截断）正文，截断由 [build_study_payload] 统一做（保证成本控制集中一处）。
    """
    query = (
        db.query(Page)
        .filter(Page.user_id == user_id, Page.ocr_state == OCR_DONE)
        .order_by(Page.id)
    )
    if subject_id is not None:
        query = query.filter(Page.subject_id == subject_id)

    samples: list[dict] = []
    for page in query.all():
        body = (page.ocr_text or "").strip()
        if not body:
            continue
        samples.append({"title": (page.title or "").strip(), "body": body})
    return samples


def summarize_body(body: str) -> str:
    """正文摘要：换行/连续空白归一为单空格，再截断到 [BODY_MAX_CHARS]（不追加省略号）"""
    return " ".join((body or "").split())[:BODY_MAX_CHARS]


def _trend_lines(trend: list[int], today: date) -> list[str]:
    """近 30 天趋势：以「日期: 页数」列出非零项；全零时明确告知无记录。

    trend 为按日期升序、末尾为「今天」的 [TREND_DAYS] 个计数（见 study_stats.compute_stats）。
    日期映射按 `len(trend)` 计算（不写死 30）；长度不符时记 warning，便于尽早发现契约被破坏。
    """
    if len(trend) != TREND_DAYS:
        logger.warning(
            "记录趋势长度异常：期望 %d 天，实际 %d 天（日期映射按实际长度计算）",
            TREND_DAYS,
            len(trend),
        )
    lines: list[str] = ["", "【近 30 天记录趋势】"]
    if not trend or all(v == 0 for v in trend):
        lines.append("- 近 30 天无记录")
        return lines
    total = len(trend)
    for i, value in enumerate(trend):
        if value:
            day = today - timedelta(days=(total - 1 - i))
            lines.append(f"- {day.isoformat()}: {value} 页")
    return lines


def build_study_payload(
    stats: dict,
    samples: list[dict] | None = None,
    today: date | None = None,
) -> str:
    """组装学情报告 / 测评的 prompt payload（纯函数，可单测）

    含：统计数字、近 30 天趋势、学科名、章名、页标题（40 字 / 200 条）、
    页内容摘要（正文 120 字 / 60 页）。
    绝不包含：图片、签名图片 URL、完整 ocr_text。

    Args:
        stats: `compute_stats` 的结果
        samples: `collect_page_samples` 的结果（[{title, body}]）；缺省则不发正文摘要
        today: 趋势日期锚点（测试传固定值；默认当前 UTC 日期）
    """
    if today is None:
        today = datetime.now(timezone.utc).date()

    lines: list[str] = []
    lines.append("【学习统计】")
    lines.append(f"- 总页数：{stats['total_pages']}")
    lines.append(
        f"- 已识别：{stats['ocr_done']}，失败：{stats['ocr_failed']}，"
        f"处理中：{stats['ocr_processing']}"
    )
    lines.append(f"- 识别完成率：{stats['done_ratio'] * 100:.1f}%")

    # T9-1：补发近 30 天趋势（此前漏发，导致 AI 说「未提供趋势数据」）
    lines.extend(_trend_lines(list(stats.get("days_30_trend") or []), today))

    if stats.get("subjects"):
        lines.append("")
        lines.append("【学科分布】")
        for s in stats["subjects"]:
            lines.append(f"- {s['name']}（{s['page_count']} 页）")

    if stats.get("chapters"):
        lines.append("")
        lines.append("【章节】")
        for c in stats["chapters"]:
            lines.append(f"- {c['name']}（{c['page_count']} 页）")

    # 页标题（成本控制：截断 + 上限）
    titles = stats.get("page_titles", [])
    lines.append("")
    lines.append("【页标题】")
    for t in titles[:TITLE_MAX_COUNT]:
        t = (t or "").strip() or "(无标题)"
        lines.append(f"- {t[:TITLE_MAX_CHARS]}")
    if len(titles) > TITLE_MAX_COUNT:
        lines.append(f"- （其余 {len(titles) - TITLE_MAX_COUNT} 条页标题省略）")

    # T9-1：页内容摘要（正文摘要 + 标题成对；成本控制：每页 120 字 / 最多 60 页）
    all_samples = list(samples or [])
    lines.append("")
    lines.append("【页内容摘要】")
    if not all_samples:
        lines.append("- （未提供正文摘要）")
    else:
        for s in all_samples[:BODY_MAX_PAGES]:
            title = (s.get("title") or "").strip() or "(无标题)"
            body = summarize_body(s.get("body") or "")
            lines.append(f"- [{title}] {body}")
        if len(all_samples) > BODY_MAX_PAGES:
            lines.append(f"- （其余 {len(all_samples) - BODY_MAX_PAGES} 页正文摘要省略）")

    if stats.get("failed_pages"):
        lines.append("")
        lines.append("【识别失败页】")
        for fp in stats["failed_pages"]:
            lines.append(f"- {fp['title'] or '(无标题)'}")

    if stats.get("stale_subjects"):
        lines.append("")
        lines.append("【很久没更新的学科】")
        for name in stats["stale_subjects"]:
            lines.append(f"- {name}")

    return "\n".join(lines)
