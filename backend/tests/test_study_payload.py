"""T9-1 学情 / 测评 payload 补全测试（纯函数，不碰网络与数据库）

覆盖：
- `days_30_trend` 补发：非零项以「日期: 页数」列出；全零时明确写「近 30 天无记录」
- 正文摘要：与标题成对出现；每页截断到 120 字（不追加省略号）；最多 60 页（超出注明数量）
- 负向断言：不含图片、签名 URL、完整 ocr_text
"""
from datetime import date, timedelta
import logging

from app.ai.service import (
    BODY_MAX_CHARS,
    BODY_MAX_PAGES,
    TITLE_MAX_CHARS,
    TITLE_MAX_COUNT,
    build_study_payload,
)

TODAY = date(2026, 9, 12)


def _stats(trend: list[int] | None = None) -> dict:
    return {
        "total_pages": 3,
        "ocr_done": 2,
        "ocr_failed": 1,
        "ocr_processing": 0,
        "done_ratio": 2 / 3,
        "days_30_trend": trend if trend is not None else [0] * 30,
        "subjects": [
            {
                "subject_id": 1,
                "name": "数学",
                "page_count": 3,
                "done_ratio": 2 / 3,
                "last_page_at": "2026-09-12T00:00:00+00:00",
            },
        ],
        "chapters": [
            {
                "chapter_id": None,
                "name": "未分章",
                "page_count": 3,
                "last_page_at": "2026-09-12T00:00:00+00:00",
            },
        ],
        "failed_pages": [{"page_id": 1, "title": "错题"}],
        "stale_subjects": [],
        "page_titles": ["导数定义", "立体几何", "错题"],
    }


def _samples(count: int, body: str = "求导公式与极值判断") -> list[dict]:
    return [{"title": f"页{i}", "body": body} for i in range(count)]


# ==================== days_30_trend（此前漏发，AI 才说「未提供趋势数据」） ====================

def test_payload_includes_trend_dates():
    trend = [0] * 30
    trend[0] = 1  # 29 天前
    trend[29] = 2  # 今天
    payload = build_study_payload(_stats(trend), samples=_samples(2), today=TODAY)

    assert "【近 30 天记录趋势】" in payload
    assert f"- {TODAY.isoformat()}: 2 页" in payload
    assert f"- {(TODAY - timedelta(days=29)).isoformat()}: 1 页" in payload
    # 非零项才列出，中间的 0 不出现
    assert f"- {(TODAY - timedelta(days=1)).isoformat()}" not in payload
    assert "近 30 天无记录" not in payload


def test_payload_all_zero_trend_says_no_record():
    payload = build_study_payload(_stats(), samples=_samples(1), today=TODAY)
    assert "近 30 天无记录" in payload


def test_payload_missing_trend_key_degrades_to_no_record():
    """兼容旧 stats（无 days_30_trend 键）：不得抛异常，退化为「无记录」。"""
    stats = _stats()
    stats.pop("days_30_trend")
    payload = build_study_payload(stats, samples=_samples(1), today=TODAY)
    assert "近 30 天无记录" in payload


def test_trend_days_constant_matches_stats_contract(caplog):
    """趋势天数提为常量 TREND_DAYS，payload 侧按它校验长度契约（不再写死 30）"""
    from app.services.study_stats import TREND_DAYS

    assert TREND_DAYS == 30  # 与 compute_stats 产出的天数一致
    with caplog.at_level(logging.WARNING, logger="app.ai.service"):
        build_study_payload(_stats([0] * TREND_DAYS), today=TODAY)
    assert not [r for r in caplog.records if "记录趋势长度" in r.getMessage()]


def test_payload_trend_length_mismatch_warns_and_maps_by_actual_length(caplog):
    """长度不符时记 warning，且日期映射按实际长度（不越界、不错位）"""
    trend = [0] * 10
    trend[9] = 3  # 末尾即「今天」
    with caplog.at_level(logging.WARNING, logger="app.ai.service"):
        payload = build_study_payload(_stats(trend), today=TODAY)

    assert f"- {TODAY.isoformat()}: 3 页" in payload
    assert [r for r in caplog.records if "记录趋势长度" in r.getMessage()]


# ==================== 正文摘要（解决「AI 看不到内容」） ====================

def test_payload_body_summary_pairs_with_title():
    samples = [{"title": "导数定义", "body": "导数的定义是函数在某点处的瞬时变化率"}]
    payload = build_study_payload(_stats(), samples=samples, today=TODAY)
    assert "【页内容摘要】" in payload
    assert "- [导数定义] 导数的定义是函数在某点处的瞬时变化率" in payload


def test_payload_body_truncated_to_120_no_ellipsis():
    body = "字" * (BODY_MAX_CHARS + 80)
    payload = build_study_payload(_stats(), samples=[{"title": "长页", "body": body}], today=TODAY)

    assert f"[长页] {'字' * BODY_MAX_CHARS}" in payload
    assert body not in payload  # 完整正文不进 payload
    assert f"{'字' * BODY_MAX_CHARS}…" not in payload  # 截断处不追加省略号


def test_payload_body_normalizes_whitespace():
    samples = [{"title": "排版", "body": "第一行\n第二行   多余   空白"}]
    payload = build_study_payload(_stats(), samples=samples, today=TODAY)
    assert "[排版] 第一行 第二行 多余 空白" in payload


def test_payload_body_caps_60_pages():
    samples = _samples(BODY_MAX_PAGES + 5, body="内容")
    payload = build_study_payload(_stats(), samples=samples, today=TODAY)

    assert "其余 5 页正文摘要省略" in payload
    assert f"[{samples[BODY_MAX_PAGES - 1]['title']}]" in payload  # 第 60 页在
    assert f"[{samples[BODY_MAX_PAGES]['title']}]" not in payload  # 第 61 页不在


def test_payload_without_samples_states_no_body():
    payload = build_study_payload(_stats(), today=TODAY)
    assert "（未提供正文摘要）" in payload


# ==================== 负向断言：不越界发数据 ====================

def test_payload_negative_no_images_urls_or_full_text():
    long_body = "完" * 500
    payload = build_study_payload(
        _stats(),
        samples=[{"title": "页A", "body": long_body}],
        today=TODAY,
    )
    for forbidden in ("http", "/files/", "image_key", "image_url", "thumb", "ocr_text", "structured_text"):
        assert forbidden not in payload, f"payload 不应包含 {forbidden}"
    assert long_body not in payload  # 完整正文（500 字）绝不进 payload


def test_payload_keeps_title_caps_unchanged():
    """T5 既有成本控制不得回归：标题 40 字 / 200 条。"""
    long_title = "标" * 100
    stats = _stats()
    stats["page_titles"] = [long_title] + [f"标题{i}" for i in range(TITLE_MAX_COUNT + 4)]
    payload = build_study_payload(stats, samples=_samples(1), today=TODAY)

    assert long_title not in payload
    assert f"- {'标' * TITLE_MAX_CHARS}" in payload
    assert "其余 5 条页标题省略" in payload
