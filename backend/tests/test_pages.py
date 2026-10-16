"""页接口测试：上传/批量/列表/详情/修改/删除/重识别 + 文件访问"""
import tests.conftest as ctest
from tests.conftest import auth_headers, make_jpg_bytes


def _mk_subject(client, headers, name="数学"):
    return client.post("/subjects", json={"name": name}, headers=headers).json()


def test_upload_single_page_ocr_done(client):
    h = auth_headers(client)
    s = _mk_subject(client, h)
    resp = client.post(
        "/pages", data={"subject_id": s["id"]}, files={"file": ("note.jpg", make_jpg_bytes(), "image/jpeg")}, headers=h
    )
    assert resp.status_code == 201, resp.text
    page = resp.json()
    assert page["ocr_state"] == "done"
    assert page["ocr_conf"] == 0.95
    # 标题自动取 OCR 首行
    assert page["title"] == "默认识别文本 导数与极值"
    assert "_thumb.jpg" in page["thumb_url"]
    assert page["width"] == 60 and page["height"] == 40


def test_upload_without_subject_rejected(client):
    h = auth_headers(client)
    resp = client.post("/pages", files={"file": ("a.jpg", make_jpg_bytes(), "image/jpeg")}, headers=h)
    assert resp.status_code == 422


def test_batch_upload(client):
    h = auth_headers(client)
    s = _mk_subject(client, h)
    files = [("files", ("a.jpg", make_jpg_bytes((190, 210, 190)), "image/jpeg")),
             ("files", ("b.png", make_jpg_bytes((210, 200, 210)), "image/png"))]
    resp = client.post("/pages/batch", data={"subject_id": s["id"]}, files=files, headers=h)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["created"] == 2
    assert all(p["ocr_state"] == "done" for p in data["pages"])

    lst = client.get("/pages", params={"subject_id": s["id"]}, headers=h).json()
    assert lst["total"] == 2


def test_list_filters_and_pagination(client):
    h = auth_headers(client)
    s1 = _mk_subject(client, h, "数学")
    s2 = _mk_subject(client, h, "物理")
    for i in range(3):
        client.post(
            "/pages", data={"subject_id": s1["id"]}, files={"file": (f"{i}.jpg", make_jpg_bytes(), "image/jpeg")}, headers=h
        )
    client.post(
        "/pages", data={"subject_id": s2["id"]}, files={"file": ("p.jpg", make_jpg_bytes(), "image/jpeg")}, headers=h
    )

    resp = client.get("/pages", params={"subject_id": s1["id"], "page": 1, "size": 2}, headers=h).json()
    assert resp["total"] == 3 and len(resp["items"]) == 2
    # 新上传在前
    assert resp["items"][0]["id"] > resp["items"][1]["id"]
    # 按学科过滤后第二页剩余 1 条
    resp2 = client.get("/pages", params={"subject_id": s1["id"], "page": 2, "size": 2}, headers=h).json()
    assert len(resp2["items"]) == 1

    # 非法状态
    assert client.get("/pages", params={"state": "bogus"}, headers=h).status_code == 422
    # done 状态过滤跨学科
    resp3 = client.get("/pages", params={"state": "done"}, headers=h).json()
    assert resp3["total"] == 4


def test_update_page_move_and_correct_text(client):
    h = auth_headers(client)
    s1 = _mk_subject(client, h, "数学")
    s2 = _mk_subject(client, h, "物理")
    chapter = client.post(f"/subjects/{s1['id']}/chapters", json={"name": "导数"}, headers=h).json()

    page = client.post(
        "/pages", data={"subject_id": s1["id"], "chapter_id": chapter["id"]},
        files={"file": ("a.jpg", make_jpg_bytes(), "image/jpeg")}, headers=h
    ).json()

    # 人工修正 OCR（写回索引），并改名
    resp = client.patch(
        f"/pages/{page['id']}",
        json={"title": "导数定义", "ocr_text": "导数定义的修正文本\n第二行"},
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json()["ocr_state"] == "done"
    assert resp.json()["title"] == "导数定义"

    # 跨学科章归属校验：把页移到物理，却传数学的章 → 422/404
    bad = client.patch(
        f"/pages/{page['id']}", json={"subject_id": s2["id"], "chapter_id": chapter["id"]}, headers=h
    )
    assert bad.status_code == 404

    # 正常移动学科（章自动清空）
    resp = client.patch(f"/pages/{page['id']}", json={"subject_id": s2["id"]}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["subject_id"] == s2["id"]
    assert resp.json()["chapter_id"] is None

    # 修正后的文本可被搜索到（见 test_search 里覆盖 FTS 同步，此处验证部分更新提交无 500）
    assert page["id"] > 0


def test_page_delete_and_files_access(client):
    import app.services.storage_service as storage_service

    h = auth_headers(client)
    s = _mk_subject(client, h)
    page = client.post(
        "/pages", data={"subject_id": s["id"]}, files={"file": ("a.jpg", make_jpg_bytes(), "image/jpeg")}, headers=h
    ).json()
    key = page["image_key"]
    assert (storage_service.UPLOAD_DIR / key).exists()

    # 图片可鉴权访问
    resp = client.get(page["image_url"], headers=h)
    assert resp.status_code == 200
    # 无 token 不可访问（用纯 key 路径，避免签名 URL 自带凭据）
    assert client.get(f"/files/{page['image_key']}").status_code in (401, 403)

    # 他人不可访问
    others = auth_headers(client, openid="dev_other_pages")
    # 他人用 JWT 访问本人 key（纯路径，不带签名）→ 归属校验失败 404
    assert client.get(f"/files/{page['image_key']}", headers=others).status_code == 404

    # 删除页：文件与索引同步清理
    resp = client.delete(f"/pages/{page['id']}", headers=h)
    assert resp.status_code == 200
    assert not (storage_service.UPLOAD_DIR / key).exists()
    assert client.get(f"/pages/{page['id']}", headers=h).status_code == 404


def test_reocr(client):
    h = auth_headers(client)
    s = _mk_subject(client, h)
    page = client.post(
        "/pages", data={"subject_id": s["id"]}, files={"file": ("a.jpg", make_jpg_bytes(), "image/jpeg")}, headers=h
    ).json()
    resp = client.post(f"/pages/{page['id']}/reocr", headers=h)
    assert resp.status_code == 200
    assert resp.json()["ocr_state"] == "pending"
    # 同步假处理器已再次跑完
    detail = client.get(f"/pages/{page['id']}", headers=h).json()
    assert detail["ocr_state"] == "done"


def test_ocr_failure_visible(client):
    ctest.FAKE_TEXT = ""  # 假引擎返回空文本 → run_ocr 判定失败
    h = auth_headers(client)
    s = _mk_subject(client, h)
    page = client.post(
        "/pages", data={"subject_id": s["id"]}, files={"file": ("a.jpg", make_jpg_bytes(), "image/jpeg")}, headers=h
    ).json()
    assert page["ocr_state"] == "failed"
    assert "未识别出文字" in (page["ocr_error"] or "")
    # 失败页可重试（假文本恢复后成功）
    ctest.FAKE_TEXT = "重试成功文本"
    resp = client.post(f"/pages/{page['id']}/reocr", headers=h)
    assert resp.status_code == 200
    detail = client.get(f"/pages/{page['id']}", headers=h).json()
    assert detail["ocr_state"] == "done"
    assert detail["title"] == "重试成功文本"
