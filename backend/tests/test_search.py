"""搜索接口测试：FTS5 trigram（≥3 字）+ LIKE 短词兜底 + 修正写回索引"""
import tests.conftest as ctest
from tests.conftest import auth_headers, make_jpg_bytes

TEXT = "导数求极值的笔记内容 这里记录了判断方法\n配图一页"


def _upload(client, headers, subject_id, text=None, chapter_id=None, index=0):
    ctest.FAKE_TEXT = text or TEXT
    return client.post(
        "/pages",
        data={"subject_id": subject_id, **({"chapter_id": chapter_id} if chapter_id else {})},
        files={"file": (f"n{index}.jpg", make_jpg_bytes(), "image/jpeg")},
        headers=headers,
    ).json()


def test_search_long_phrase_via_fts(client):
    h = auth_headers(client)
    s = client.post("/subjects", json={"name": "数学"}, headers=h).json()
    _upload(client, h, s["id"], TEXT)
    client.post("/subjects", json={"name": "物理"}, headers=h)  # 干扰学科，无页

    resp = client.get("/search", params={"q": "导数求极值"}, headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["subject_name"] == "数学"
    assert "导数求极值" in item["snippet"]
    assert item["ocr_state"] == "done"
    assert item["thumb_url"]  # 有缩略图


def test_search_two_char_fallback_like(client):
    h = auth_headers(client)
    s = client.post("/subjects", json={"name": "数学"}, headers=h).json()
    _upload(client, h, s["id"], TEXT)

    # 2 字词 trigram 无法命中 → LIKE 兜底
    resp = client.get("/search", params={"q": "极值"}, headers=h)
    assert resp.json()["total"] == 1

    # 命中标题的关键词也可搜到
    resp = client.get("/search", params={"q": "导数"}, headers=h)
    assert resp.json()["total"] == 1


def test_search_subject_filter_and_empty(client):
    h = auth_headers(client)
    s1 = client.post("/subjects", json={"name": "数学"}, headers=h).json()
    s2 = client.post("/subjects", json={"name": "物理"}, headers=h).json()
    _upload(client, h, s1["id"], TEXT, index=1)
    _upload(client, h, s2["id"], "圆周运动 角速度 笔记", index=2)

    # 学科过滤
    resp = client.get("/search", params={"q": "导数求极值", "subject_id": s2["id"]}, headers=h)
    assert resp.json()["total"] == 0
    resp = client.get("/search", params={"q": "导数求极值", "subject_id": s1["id"]}, headers=h)
    assert resp.json()["total"] == 1

    # 无命中
    resp = client.get("/search", params={"q": "不存在的关键词xyz"}, headers=h)
    assert resp.json()["total"] == 0

    # 空关键词被拒
    assert client.get("/search", params={"q": "  "}, headers=h).status_code == 422


def test_search_user_isolation_and_edit_sync(client):
    h1 = auth_headers(client, openid="dev_searcher_1")
    s1 = client.post("/subjects", json={"name": "数学"}, headers=h1).json()
    page = _upload(client, h1, s1["id"], TEXT)

    # 其他用户搜不到
    h2 = auth_headers(client, openid="dev_searcher_2")
    s2 = client.post("/subjects", json={"name": "历史"}, headers=h2).json()
    _upload(client, h2, s2["id"], "近代史 事件 时间线", index=9)
    resp = client.get("/search", params={"q": "导数求极值"}, headers=h2)
    assert resp.json()["total"] == 0

    # 原文本命中后，人工修正（标题+文本都改）→ 索引同步，旧词消失新词命中
    assert client.get("/search", params={"q": "导数求极值"}, headers=h1).json()["total"] == 1
    client.patch(
        f"/pages/{page['id']}",
        json={"title": "数列极限", "ocr_text": "已经改成数列极限的文本"},
        headers=h1,
    )
    assert client.get("/search", params={"q": "导数求极值"}, headers=h1).json()["total"] == 0
    assert client.get("/search", params={"q": "数列极限"}, headers=h1).json()["total"] == 1

    # 删除页 → 搜索移除
    client.delete(f"/pages/{page['id']}", headers=h1)
    assert client.get("/search", params={"q": "数列极限"}, headers=h1).json()["total"] == 0
