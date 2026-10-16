"""T12-6 注销账号（`DELETE /auth/me`）测试

覆盖任务书第三节的要求：
- 注销 → 用户 / 学科 / 章 / 页 / **FTS 索引**全删
- **图片文件物理删除**（`storage/` 下文件真的消失，不是只删库）
- 注销后原 token 失效（**401**）
- 注销后同标识重登 = **全新空账号**
- 额外：不影响其他用户；未登录不能注销

FTS 与库表用**直接读 SQLite 文件**断言（`db_file` fixture 捕获 conftest 里 client 建的临时库路径），
不依赖 API 的可见性过滤。
"""
import sqlite3

import pytest

from app.services import storage_service
from tests.conftest import auth_headers, make_jpg_bytes


@pytest.fixture
def db_file(monkeypatch):
    """捕获 conftest `client` fixture 创建的临时 SQLite 路径（用于直查 pages_fts 等表）"""
    import tempfile

    created: list[str] = []
    real_mkstemp = tempfile.mkstemp

    def fake_mkstemp(*args, **kwargs):
        fd, path = real_mkstemp(*args, **kwargs)
        created.append(path)
        return fd, path

    monkeypatch.setattr(tempfile, "mkstemp", fake_mkstemp)
    return created


def _fts_has_row(db_path: str, page_id: int) -> bool:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT count(*) FROM pages_fts WHERE rowid=?", (page_id,)).fetchone()
    return row[0] > 0


def _count(db_path: str, table: str, column: str, value: int) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(f"SELECT count(*) FROM {table} WHERE {column}=?", (value,)).fetchone()
    return row[0]


def _subject(client, headers, name="数学"):
    r = client.post("/subjects", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _chapter(client, headers, sid, name="第一章"):
    r = client.post(f"/subjects/{sid}/chapters", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _page(client, headers, sid, cid=None, title="笔记页"):
    data = {"subject_id": str(sid)}
    if cid is not None:
        data["chapter_id"] = str(cid)
    r = client.post(
        "/pages",
        headers=headers,
        data=data,
        files={"file": ("a.jpg", make_jpg_bytes(), "image/jpeg")},
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    r = client.patch(f"/pages/{pid}", headers=headers, json={"title": title})
    assert r.status_code == 200, r.text
    return r.json()


def test_delete_me_removes_user_subject_chapter_page_and_fts(db_file, client):
    h = auth_headers(client, "del_full")
    uid = client.get("/auth/me", headers=h).json()["id"]
    sid = _subject(client, h, "要删的学科")
    cid = _chapter(client, h, sid, "要删的章")
    page = _page(client, h, sid, cid, "导数笔记")
    db_path = db_file[0]

    # 前置：该页确实进了 FTS 索引
    assert _fts_has_row(db_path, page["id"]), "前置条件：该页应在 pages_fts 索引中"

    r = client.delete("/auth/me", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}

    # ① FTS 索引行已删除（直查虚拟表，不受 API 可见性过滤影响）
    assert not _fts_has_row(db_path, page["id"]), "注销后 FTS 索引行必须删除"
    # ② 四张表都没有该用户残留
    assert _count(db_path, "users", "id", uid) == 0
    assert _count(db_path, "subjects", "user_id", uid) == 0
    assert _count(db_path, "chapters", "subject_id", sid) == 0
    assert _count(db_path, "pages", "user_id", uid) == 0
    # ③ 旧 token 立刻失效
    assert client.get("/auth/me", headers=h).status_code == 401


def test_delete_me_physically_removes_image_files(client):
    h = auth_headers(client, "del_files")
    sid = _subject(client, h)
    page = _page(client, h, sid, None, "有图页")

    image_path = storage_service.path_for(page["image_key"])
    thumb_path = storage_service.path_for(page["thumb_key"])
    assert image_path.exists(), "上传后原图应已落盘"
    assert thumb_path.exists(), "上传后缩略图应已落盘"

    assert client.delete("/auth/me", headers=h).status_code == 200

    # **物理删除**：文件必须真的消失（不是只删数据库记录）
    assert not image_path.exists(), "注销后原图文件必须被物理删除"
    assert not thumb_path.exists(), "注销后缩略图必须被物理删除"


def test_token_invalid_401_after_deletion(client):
    h = auth_headers(client, "del_token")
    _subject(client, h)
    assert client.get("/auth/me", headers=h).status_code == 200

    assert client.delete("/auth/me", headers=h).status_code == 200

    # 原 token 对全部受保护接口都不再有效 —— 401（不是 404，也不是 200）
    for path in ("/auth/me", "/subjects", "/pages", "/search?q=abc"):
        assert client.get(path, headers=h).status_code == 401, path


def test_relogin_after_deletion_creates_brand_new_empty_account(client):
    h = auth_headers(client, "del_relogin", "老昵称")
    sid = _subject(client, h, "旧学科")
    _page(client, h, sid, None, "旧笔记")
    old = client.get("/auth/me", headers=h).json()

    assert client.delete("/auth/me", headers=h).status_code == 200

    h_new = auth_headers(client, "del_relogin", "新昵称")
    me = client.get("/auth/me", headers=h_new)
    assert me.status_code == 200
    assert me.json()["nickname"] == "新昵称"
    # 注意：SQLite 会复用已删除行的自增 id，所以「全新账号」的判据是**数据为空**，
    # 而不是 id 数字变大（id 可能相同，但绝不是同一个账号的数据）。
    assert me.json()["created_at"] >= old["created_at"]
    # 全新空账号：没有学科、没有笔记
    assert client.get("/subjects", headers=h_new).json() == []
    assert client.get("/pages", headers=h_new).json()["total"] == 0


def test_delete_me_does_not_touch_other_users(client):
    owner = auth_headers(client, "del_owner")
    other = auth_headers(client, "del_other")
    sid_owner = _subject(client, owner, "甲的学科")
    page_owner = _page(client, owner, sid_owner, None, "甲的笔记")
    sid_other = _subject(client, other, "乙的学科")
    page_other = _page(client, other, sid_other, None, "乙的笔记")

    other_image = storage_service.path_for(page_other["image_key"])
    assert client.delete("/auth/me", headers=owner).status_code == 200

    # 甲没了
    assert client.get("/auth/me", headers=owner).status_code == 401
    assert not storage_service.path_for(page_owner["image_key"]).exists()
    # 乙完好无损（数据 + 文件 + token）
    assert client.get("/auth/me", headers=other).status_code == 200
    other_subjects = client.get("/subjects", headers=other).json()
    assert any(s["id"] == sid_other for s in other_subjects), "乙的学科不得被删除"
    assert client.get(f"/pages/{page_other['id']}", headers=other).status_code == 200
    assert other_image.exists(), "别人的图片文件不得被删除"


def test_delete_me_requires_authentication(client):
    r = client.delete("/auth/me")
    assert r.status_code in (401, 403), r.text
