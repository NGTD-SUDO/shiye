"""T6-2 backfill_titles 测试：dry-run / apply+FTS / 幂等 / 不碰正常标题 / 空串案例"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.page import OCR_DONE, OCR_PENDING, Page
from app.models.subject import Subject
from app.models.user import User
from app.services import fts
from scripts.backfill_titles import backfill


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    fts.ensure_fts(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session
    engine.dispose()


def _mk_user(db):
    u = User(wechat_openid="u1", nickname="测试")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _mk_subject(db, uid):
    s = Subject(user_id=uid, name="数学")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _mk_page(db, uid, sid, title, ocr_text, state=OCR_DONE):
    p = Page(
        user_id=uid, subject_id=sid, title=title,
        image_key=f"{uid}/x.jpg", ocr_text=ocr_text, ocr_state=state,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


OCR_NOISE = "10:49:24\n280\n5G\n96%\n如果两个角的和等于90°(直角),就说其中每一个角是另一个角的余角."
OCR_EMPTY = "10:49:24\n280\n5G\n96%"  # 无可用行
OCR_NORMAL = "余角的性质\n同角的余角相等"


def test_dry_run_does_not_write(db):
    u = _mk_user(db)
    s = _mk_subject(db, u.id)
    p = _mk_page(db, u.id, s.id, "10:49:24", OCR_NOISE)

    result = backfill(db, apply=False)
    assert result["scanned"] == 1
    assert result["changed"] == 1
    db.refresh(p)
    assert p.title == "10:49:24"  # dry-run 未改库


def test_apply_writes_and_syncs_fts(db):
    u = _mk_user(db)
    s = _mk_subject(db, u.id)
    p = _mk_page(db, u.id, s.id, "10:49:24", OCR_NOISE)

    result = backfill(db, apply=True)
    assert result["changed"] == 1
    db.refresh(p)
    assert p.title.startswith("如果两个角的和等于90°")
    # FTS 同步：pages_fts 里该页 title 已更新为新标题
    rows = db.execute(text("SELECT title FROM pages_fts WHERE rowid=:id"), {"id": p.id}).fetchall()
    assert rows and rows[0][0].startswith("如果两个角")


def test_idempotent_second_run_no_change(db):
    u = _mk_user(db)
    s = _mk_subject(db, u.id)
    _mk_page(db, u.id, s.id, "10:49:24", OCR_NOISE)

    r1 = backfill(db, apply=True)
    assert r1["changed"] == 1
    r2 = backfill(db, apply=True)
    assert r2["changed"] == 0  # 幂等：第二次无需要修改
    assert r2["skipped"]["title_ok"] == 1


def test_keeps_normal_title(db):
    u = _mk_user(db)
    s = _mk_subject(db, u.id)
    p = _mk_page(db, u.id, s.id, "用户手改的标题", OCR_NORMAL)

    result = backfill(db, apply=True)
    assert result["changed"] == 0
    db.refresh(p)
    assert p.title == "用户手改的标题"  # 不碰正常标题


def test_noise_title_with_no_usable_line_becomes_empty(db):
    u = _mk_user(db)
    s = _mk_subject(db, u.id)
    p = _mk_page(db, u.id, s.id, "10:49:24", OCR_EMPTY)

    result = backfill(db, apply=True)
    assert result["changed"] == 1
    db.refresh(p)
    assert p.title == ""  # 无可用行 → 空串，不用文件名/时间戳兜底


def test_skips_not_done_and_no_text(db):
    u = _mk_user(db)
    s = _mk_subject(db, u.id)
    # 未完成的页（pending）
    _mk_page(db, u.id, s.id, "10:49:24", OCR_NOISE, state=OCR_PENDING)
    # done 但无文本
    _mk_page(db, u.id, s.id, "10:49:24", "")

    result = backfill(db, apply=True)
    assert result["scanned"] == 2
    assert result["changed"] == 0
    assert result["skipped"]["not_done"] == 1
    assert result["skipped"]["no_text"] == 1
