"""学科 + 章（两级结构）接口测试"""
from tests.conftest import auth_headers, make_jpg_bytes


def _mk_subject(client, headers, name="数学", color="#007AFF"):
    """T13-3：测试构造值同步换成主题蓝（仅构造用，断言不依赖具体色值）。"""
    resp = client.post("/subjects", json={"name": name, "color": color}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_subject_default_color_is_theme_blue(client):
    """T13-3：新建科目**不传 color** 时默认色 = 主题蓝 #007AFF（旧的品牌绿已废弃）。"""
    h = auth_headers(client)
    resp = client.post("/subjects", json={"name": "默认色"}, headers=h)
    assert resp.status_code == 201, resp.text
    assert resp.json()["color"] == "#007AFF"


def test_subject_crud_and_counts(client):
    h = auth_headers(client)
    s = _mk_subject(client, h)
    assert s["name"] == "数学"
    assert s["page_count"] == 0 and s["done_count"] == 0

    # 上传一页触发假 OCR 完成后统计应更新
    img = make_jpg_bytes()
    resp = client.post(
        "/pages", data={"subject_id": s["id"]}, files={"file": ("a.jpg", img, "image/jpeg")}, headers=h
    )
    assert resp.status_code == 201
    page = resp.json()
    assert page["ocr_state"] == "done"

    # 列表含计数；对另一个用户隔离
    others = auth_headers(client, openid="other_user")
    lst = client.get("/subjects", headers=others).json()
    assert lst == []

    lst = client.get("/subjects", headers=h).json()
    assert len(lst) == 1
    assert lst[0]["page_count"] == 1 and lst[0]["done_count"] == 1

    # 改名 / 改色 / 排序
    resp = client.patch(f"/subjects/{s['id']}", json={"name": "高等数学", "color": "#2D6A9F", "sort_order": 5}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["name"] == "高等数学"
    assert resp.json()["color"] == "#2D6A9F"
    assert resp.json()["sort_order"] == 5

    # 同名冲突
    dup = client.post("/subjects", json={"name": "高等数学"}, headers=h)
    assert dup.status_code == 409

    # 他人无权改
    forbid = client.patch(f"/subjects/{s['id']}", json={"name": "入侵"}, headers=others)
    assert forbid.status_code == 404

    # 删除学科级联清理
    resp = client.delete(f"/subjects/{s['id']}", headers=h)
    assert resp.status_code == 200
    assert client.get("/subjects", headers=h).json() == []
    # 页也被清理
    resp = client.get("/pages", headers=h)
    assert resp.json()["total"] == 0


def test_subject_delete_removes_images_and_fts(client):
    import app.services.storage_service as storage_service

    h = auth_headers(client)
    s = _mk_subject(client, h)
    img = make_jpg_bytes()
    resp = client.post(
        "/pages", data={"subject_id": s["id"]}, files={"file": ("a.jpg", img, "image/jpeg")}, headers=h
    )
    page = resp.json()
    key = page["image_key"]

    storage_dir = storage_service.UPLOAD_DIR
    assert (storage_dir / key).exists()

    client.delete(f"/subjects/{s['id']}", headers=h)
    assert not (storage_dir / key).exists()


def test_chapter_two_level_flow(client):
    h = auth_headers(client)
    s = _mk_subject(client, h)

    # 建章
    c = client.post(f"/subjects/{s['id']}/chapters", json={"name": "导数"}, headers=h)
    assert c.status_code == 201
    chapter = c.json()
    assert chapter["page_count"] == 0

    # 同名章冲突（学科内）
    assert client.post(f"/subjects/{s['id']}/chapters", json={"name": "导数"}, headers=h).status_code == 409

    # 页归入章
    img = make_jpg_bytes()
    page = client.post(
        "/pages",
        data={"subject_id": s["id"], "chapter_id": chapter["id"]},
        files={"file": ("a.jpg", img, "image/jpeg")},
        headers=h,
    ).json()
    assert page["chapter_id"] == chapter["id"]
    assert page["chapter_name"] == "导数"

    # 章列表带页数
    chapters = client.get(f"/subjects/{s['id']}/chapters", headers=h).json()
    assert len(chapters) == 1 and chapters[0]["page_count"] == 1

    # 删章：页保留、chapter 置空
    resp = client.delete(f"/subjects/{s['id']}/chapters/{chapter['id']}", headers=h)
    assert resp.status_code == 200
    detail = client.get(f"/pages/{page['id']}", headers=h).json()
    assert detail["chapter_id"] is None

    # 章不存在/跨学科章 404
    other = _mk_subject(client, h, name="英语")
    assert client.post(f"/subjects/{other['id']}/chapters", json={"name": "x"}, headers=h).status_code == 201
    assert client.get(f"/subjects/{s['id']}/chapters", headers=h).json() == []
