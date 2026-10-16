"""T5-1 学情统计纯函数测试（compute_stats）

覆盖：空数据结构完整 / 正常计数 / 30 天趋势补零升序 / subject 过滤 /
failed_pages 上限 / stale_subjects 逻辑。
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.chapter import Chapter
from app.models.page import OCR_DONE, OCR_FAILED, OCR_PROCESSING, Page
from app.models.subject import Subject
from app.models.user import User
from app.services.study_stats import compute_stats


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session
    engine.dispose()


def _mk_user(db, openid="u1") -> User:
    u = User(wechat_openid=openid, nickname="测试")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _mk_subject(db, user_id, name) -> Subject:
    s = Subject(user_id=user_id, name=name)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _mk_chapter(db, subject_id, name) -> Chapter:
    c = Chapter(subject_id=subject_id, name=name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _mk_page(db, user_id, subject_id, chapter_id=None, title="", ocr_state=OCR_DONE,
             created_at=None, ocr_text="正文内容"):
    p = Page(
        user_id=user_id,
        subject_id=subject_id,
        chapter_id=chapter_id,
        title=title,
        image_key=f"{user_id}/test.jpg",
        ocr_state=ocr_state,
        ocr_text=ocr_text,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


NOW = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


def test_empty_stats_structure_complete(db):
    u = _mk_user(db)
    stats = compute_stats(db, u.id, None, now=NOW)
    assert stats["total_pages"] == 0
    assert stats["ocr_done"] == 0
    assert stats["ocr_failed"] == 0
    assert stats["ocr_processing"] == 0
    assert stats["done_ratio"] == 0.0  # 不 NaN
    assert len(stats["days_30_trend"]) == 30
    assert all(v == 0 for v in stats["days_30_trend"])
    assert stats["subjects"] == []
    assert stats["chapters"] == []
    assert stats["failed_pages"] == []
    assert stats["stale_subjects"] == []


def test_stats_normal_counts(db):
    u = _mk_user(db)
    s1 = _mk_subject(db, u.id, "数学")
    s2 = _mk_subject(db, u.id, "物理")
    _mk_subject(db, u.id, "化学")  # 0 页学科
    c1 = _mk_chapter(db, s1.id, "导数")

    # 数学：1 页归章「导数」+ 2 页未分章（其中 1 页 failed）
    _mk_page(db, u.id, s1.id, c1.id, "导数定义", OCR_DONE, NOW)
    _mk_page(db, u.id, s1.id, None, "立体几何", OCR_DONE, NOW)
    _mk_page(db, u.id, s1.id, None, "错题", OCR_FAILED, NOW)
    # 物理：1 done + 1 processing
    _mk_page(db, u.id, s2.id, None, "力学", OCR_DONE, NOW)
    _mk_page(db, u.id, s2.id, None, "电学", OCR_PROCESSING, NOW)

    stats = compute_stats(db, u.id, None, now=NOW)
    assert stats["total_pages"] == 5
    assert stats["ocr_done"] == 3
    assert stats["ocr_failed"] == 1
    assert stats["ocr_processing"] == 1
    assert stats["done_ratio"] == pytest.approx(3 / 5)

    # subjects：3 个学科
    assert len(stats["subjects"]) == 3
    by_name = {s["name"]: s for s in stats["subjects"]}
    assert by_name["数学"]["page_count"] == 3
    assert by_name["物理"]["page_count"] == 2
    assert by_name["化学"]["page_count"] == 0
    assert by_name["数学"]["done_ratio"] == pytest.approx(2 / 3)

    # chapters：含「导数」与「未分章」桶
    ch_names = {c["name"] for c in stats["chapters"]}
    assert "导数" in ch_names
    assert "未分章" in ch_names
    # 未分章桶 = 数学 2 页 + 物理 2 页 = 4 页
    unassigned = next(c for c in stats["chapters"] if c["name"] == "未分章")
    assert unassigned["page_count"] == 4

    # failed_pages
    assert len(stats["failed_pages"]) == 1
    assert stats["failed_pages"][0]["title"] == "错题"


def test_stats_30day_trend_padding_and_order(db):
    u = _mk_user(db)
    s1 = _mk_subject(db, u.id, "数学")
    # 今天 2 页 + 29 天前 1 页，中间 28 天补 0
    _mk_page(db, u.id, s1.id, None, "今天1", OCR_DONE, NOW)
    _mk_page(db, u.id, s1.id, None, "今天2", OCR_DONE, NOW)
    _mk_page(db, u.id, s1.id, None, "29天前", OCR_DONE, NOW - timedelta(days=29))

    trend = compute_stats(db, u.id, None, now=NOW)["days_30_trend"]
    assert len(trend) == 30
    assert trend[0] == 1  # 29 天前
    assert trend[29] == 2  # 今天
    assert sum(trend) == 3
    assert all(v == 0 for v in trend[1:29])  # 中间补 0


def test_stats_subject_filter(db):
    u = _mk_user(db)
    s1 = _mk_subject(db, u.id, "数学")
    s2 = _mk_subject(db, u.id, "物理")
    _mk_page(db, u.id, s1.id, None, "数学页", OCR_DONE, NOW)
    _mk_page(db, u.id, s2.id, None, "物理页", OCR_DONE, NOW)

    stats = compute_stats(db, u.id, s1.id, now=NOW)
    assert stats["total_pages"] == 1
    assert len(stats["subjects"]) == 1
    assert stats["subjects"][0]["name"] == "数学"


def test_failed_pages_capped_at_10(db):
    u = _mk_user(db)
    s1 = _mk_subject(db, u.id, "数学")
    for i in range(15):
        _mk_page(db, u.id, s1.id, None, f"失败{i}", OCR_FAILED, NOW)

    stats = compute_stats(db, u.id, None, now=NOW)
    assert stats["ocr_failed"] == 15  # 计数不受上限影响
    assert len(stats["failed_pages"]) == 10  # 列表上限 10


def test_stale_subjects_7_days(db):
    u = _mk_user(db)
    s1 = _mk_subject(db, u.id, "旧学科")
    s2 = _mk_subject(db, u.id, "新学科")
    _mk_subject(db, u.id, "空学科")  # 0 页，不算 stale
    _mk_page(db, u.id, s1.id, None, "旧页", OCR_DONE, NOW - timedelta(days=10))
    _mk_page(db, u.id, s2.id, None, "新页", OCR_DONE, NOW - timedelta(days=1))

    stale = compute_stats(db, u.id, None, now=NOW)["stale_subjects"]
    assert "旧学科" in stale
    assert "新学科" not in stale
    assert "空学科" not in stale  # 0 页不算 stale（没有学习记录可判断）
