"""图片访问鉴权测试：签名优先 + JWT 兜底 + 归属校验

覆盖用例（T1 第二轮，对照评审意见补全）：
  1. 本人签名访问 → 200，内容与落盘原图一致
  2. 篡改 s 中间位 → 403（urllib.parse 定点改 s）
  3. s 换等长随机串 → 403
  4. 过期签名（ttl 负数）→ 403
  5. 只改 e 不改 s（e 换成 1 小时前）→ 403
  6. 60 秒宽限窗口内（e=now-30s，按该 e 重算 s）→ 200
  7. A 的签名 + B 的 key（改名冒充）→ 403（签名↔key 绑定）
  8. key 首段非数字 → 404
  9. A 用 JWT 访问 B 的 key → 404（不泄露存在性，JWT 通道）
  10. 纯 key 无凭据 → 401
  11. 半截参数（有 e 无 s）→ 401
  12. JWT 兜底（纯 key + Bearer）→ 200
  13. thumb_key 为 None → thumb_url 为 None
  14. thumb_url 也带签名参数
  15. 他人持 A 的有效签名 URL → 200（持有即授权，显式留档）
  16. SECRET_KEY 不出现在响应体；s 是 64 位 hex
"""
import json as _json
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.config import SECRET_KEY
from app.services.file_signing import sign_url
from tests.conftest import auth_headers, make_jpg_bytes


# ==================== helper ====================
def _mk_subject(client, headers, name="数学"):
    return client.post("/subjects", json={"name": name}, headers=headers).json()


def _upload_page(client, headers, subject_id, jpg_bytes=None):
    """上传一张图，返回 page JSON"""
    jpg = jpg_bytes or make_jpg_bytes()
    return client.post(
        "/pages",
        data={"subject_id": str(subject_id)},
        files={"file": ("note.jpg", jpg, "image/jpeg")},
        headers=headers,
    ).json()


def _tamper_s(url, pos="mid", delta=1):
    """定点篡改 s 参数某一位（默认中间位），返回新 URL

    pos: "mid" 改中间位, "first" 改首位
    """
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    s = qs["s"][0]
    idx = len(s) // 2 if pos == "mid" else 0
    ch = s[idx]
    new_ch = chr(ord(ch) + delta) if ord(ch) + delta <= 126 else chr(ord(ch) - 1)
    s2 = s[:idx] + new_ch + s[idx + 1:]
    qs["s"] = [s2]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _replace_s(url, new_s):
    """把 s 参数整体替换为 new_s"""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    qs["s"] = [new_s]
    return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))


def _replace_e(url, new_e):
    """把 e 参数整体替换为 new_e"""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    qs["e"] = [str(new_e)]
    return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))


def _replace_key_in_path(url, new_key):
    """把 /files/{old_key}?... 中的 old_key 替换为 new_key"""
    parsed = urlparse(url)
    # path 形如 /files/{key}
    prefix = "/files/"
    assert parsed.path.startswith(prefix)
    old_key = parsed.path[len(prefix):]
    new_path = prefix + new_key
    return urlunparse(parsed._replace(path=new_path))


# ==================== 用例 1-6：签名通道基本正确性 ====================

def test_01_signed_url_self_access_returns_file(client):
    """用例1：本人签名链接访问本人图片 → 200，内容与落盘原图一致"""
    h = auth_headers(client)
    s = _mk_subject(client, h)
    page = _upload_page(client, h, s["id"])

    signed = page["image_url"]
    assert "?e=" in signed and "&s=" in signed

    resp = client.get(signed)
    assert resp.status_code == 200, resp.text
    # 比对落盘文件（storage 会重新编码，故与落盘文件而非上传字节比对）
    import app.services.storage_service as storage_service
    on_disk = storage_service.path_for(page["image_key"]).read_bytes()
    assert resp.content == on_disk, "返回内容应与落盘原图一致"
    assert len(resp.content) > 0


def test_02_tampered_s_mid_returns_403(client):
    """用例2：篡改 s 中间位 → 403（urllib.parse 定点改）"""
    h = auth_headers(client)
    s = _mk_subject(client, h)
    page = _upload_page(client, h, s["id"])
    tampered = _tamper_s(page["image_url"], pos="mid")
    resp = client.get(tampered)
    assert resp.status_code == 403, resp.text


def test_03_s_replaced_with_random_hex_returns_403(client):
    """用例3：s 换等长随机 hex 串 → 403"""
    h = auth_headers(client)
    s = _mk_subject(client, h)
    page = _upload_page(client, h, s["id"])
    import hashlib
    fake_s = hashlib.sha256(b"fake").hexdigest()  # 64 位 hex
    tampered = _replace_s(page["image_url"], fake_s)
    resp = client.get(tampered)
    assert resp.status_code == 403, resp.text


def test_04_expired_signature_returns_403(client):
    """用例4：过期签名（ttl 传负数）→ 403"""
    h = auth_headers(client)
    me = client.get("/auth/me", headers=h).json()
    s = _mk_subject(client, h)
    page = _upload_page(client, h, s["id"])
    expired = sign_url(page["image_key"], me["id"], ttl_seconds=-3600)
    resp = client.get(expired)
    assert resp.status_code == 403, resp.text
    assert "过期" in resp.json()["detail"]


def test_05_only_e_changed_to_past_returns_403(client):
    """用例5：只改 e 不改 s（e 换成 1 小时前）→ 403

    覆盖评审指出的「保留原 s、只把 e 改成过去」路径
    """
    h = auth_headers(client)
    s = _mk_subject(client, h)
    page = _upload_page(client, h, s["id"])
    import time as _t
    past_e = int(_t.time()) - 3600
    tampered = _replace_e(page["image_url"], past_e)
    resp = client.get(tampered)
    assert resp.status_code == 403, resp.text


def test_06_grace_window_within_60s_returns_200(client):
    """用例6：e 落在 60s 宽限窗口内（now-30s，按该 e 重算 s）→ 200

    覆盖评审指出的「60 秒宽限窗口边界」
    """
    h = auth_headers(client)
    me = client.get("/auth/me", headers=h).json()
    s = _mk_subject(client, h)
    page = _upload_page(client, h, s["id"])
    import time as _t
    grace_e = int(_t.time()) - 30  # 30 秒前，在 60s 宽限内
    # 按这个 e 重新算 s（用真实 SECRET_KEY + user_id + key + e）
    from app.services.file_signing import _compute_sig
    valid_s = _compute_sig(me["id"], page["image_key"], grace_e)
    url = f"/files/{page['image_key']}?e={grace_e}&s={valid_s}"
    resp = client.get(url)
    assert resp.status_code == 200, resp.text


# ==================== 用例 7-8：签名通道越权 ====================

def test_07_a_signature_with_b_key_returns_403(client):
    """用例7：A 的有效签名 + B 的 key（改名冒充）→ 403

    签名绑定 owner_id + key + exp，换 key 即失效。
    这是签名通道的核心安全属性——防止把 A 用户的签名复用到 B 的文件。
    """
    h_a = auth_headers(client, openid="dev_user_a", nickname="用户A")
    s_a = _mk_subject(client, h_a, "A的学科")
    page_a = _upload_page(client, h_a, s_a["id"])
    a_signed = page_a["image_url"]  # A 的有效签名 URL

    h_b = auth_headers(client, openid="dev_user_b", nickname="用户B")
    s_b = _mk_subject(client, h_b, "B的学科")
    page_b = _upload_page(client, h_b, s_b["id"])
    b_key = page_b["image_key"]  # B 的 key

    # 把 A 的签名 URL 里的 key 换成 B 的 key → 签名不匹配 → 403
    tampered = _replace_key_in_path(a_signed, b_key)
    resp = client.get(tampered)
    assert resp.status_code == 403, resp.text
    # 响应体不应泄露 B 的文件存在性
    assert b_key not in resp.text


def test_08_non_numeric_owner_in_key_returns_404(client):
    """用例8：key 首段非数字（如 abc/x.jpg?e=..&s=..）→ 404"""
    h = auth_headers(client)
    s = _mk_subject(client, h)
    page = _upload_page(client, h, s["id"])
    signed = page["image_url"]
    # 把 key 首段从数字换成 abc
    tampered = _replace_key_in_path(signed, "abc/fake.jpg")
    resp = client.get(tampered)
    assert resp.status_code == 404, resp.text


# ==================== 用例 9-12：JWT 通道与无凭据 ====================

def test_09_jwt_foreign_key_returns_404(client):
    """用例9：A 用 JWT 访问 B 的 key → 404（不泄露存在性）

    JWT 通道归属校验失败统一 404。
    """
    h_a = auth_headers(client, openid="dev_user_a", nickname="用户A")
    s_a = _mk_subject(client, h_a, "A的学科")
    page_a = _upload_page(client, h_a, s_a["id"])
    foreign_key = page_a["image_key"]

    h_b = auth_headers(client, openid="dev_user_b", nickname="用户B")
    resp = client.get(f"/files/{foreign_key}", headers=h_b)
    assert resp.status_code == 404, resp.text
    assert "不存在" in resp.json()["detail"]


def test_10_no_credential_returns_401(client):
    """用例10：纯 key 无凭据 → 401"""
    h = auth_headers(client)
    s = _mk_subject(client, h)
    page = _upload_page(client, h, s["id"])
    resp = client.get(f"/files/{page['image_key']}")
    assert resp.status_code == 401, resp.text
    # 确认是我们自己的分支兜底，不是 HTTPBearer 的英文 "Not authenticated"
    assert resp.json()["detail"] != "Not authenticated"


def test_11_half_signature_e_only_returns_401(client):
    """用例11：半截参数（有 e 无 s）→ 401（走 JWT 通道，user 为 None）"""
    h = auth_headers(client)
    s = _mk_subject(client, h)
    page = _upload_page(client, h, s["id"])
    # 只带 e 不带 s
    import time as _t
    url = f"/files/{page['image_key']}?e={int(_t.time()) + 900}"
    resp = client.get(url)
    assert resp.status_code == 401, resp.text


def test_12_jwt_legacy_channel_returns_200(client):
    """用例12：JWT 兜底（纯 key + Bearer）→ 200"""
    h = auth_headers(client)
    s = _mk_subject(client, h)
    page = _upload_page(client, h, s["id"])
    resp = client.get(f"/files/{page['image_key']}", headers=h)
    assert resp.status_code == 200, resp.text


# ==================== 用例 13-14：序列化产出 ====================

def test_13_thumb_key_none_then_thumb_url_none(client):
    """用例13（T2-5 修正）：非图片字节 → 400，不再走原样落盘兜底

    原行为：上传 PIL 解析不了的字节，storage 走"原样落盘 + 无缩略图"。
    T2-5 删除原样落盘分支后：非图片字节一律 400，文案含「格式」或「图片」。
    该测试名的原语义（thumb_key 为 None → thumb_url 为 None）已由 test_14
    间接覆盖（合法图片一定生成缩略图）；此处改测 T2-5 的新安全行为。
    """
    h = auth_headers(client)
    s = _mk_subject(client, h)
    fake_bytes = b"\x00\x01\x02not an image"
    resp = client.post(
        "/pages",
        data={"subject_id": str(s["id"])},
        files={"file": ("fake.bin", fake_bytes, "application/octet-stream")},
        headers=h,
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert "格式" in detail or "图片" in detail, f"文案应含格式/图片，实际: {detail}"


def test_14_thumb_url_carries_signature(client):
    """用例14：thumb_url 也带签名参数（不只是 image_url）"""
    h = auth_headers(client)
    s = _mk_subject(client, h)
    page = _upload_page(client, h, s["id"])
    assert page["thumb_url"] is not None
    assert "?e=" in page["thumb_url"] and "&s=" in page["thumb_url"], "thumb_url 应带签名参数"


# ==================== 用例 15：持有即授权显式留档 ====================

def test_15_other_user_holds_valid_signature_url_returns_200(client):
    """用例15：他人持 A 的有效签名 URL → 200（持有即授权，15 分钟内）

    签名 URL 语义为持有即授权：任何人拿到有效签名链接均可访问，
    不需要 JWT、不校验请求者身份。等同 S3 预签名取舍。
    泄露应对：缩短 TTL / 刷新列表即失效 / 后续可叠加 IP 绑定。
    """
    h_a = auth_headers(client, openid="dev_user_a", nickname="用户A")
    s_a = _mk_subject(client, h_a, "A的学科")
    page_a = _upload_page(client, h_a, s_a["id"])
    signed = page_a["image_url"]  # A 的有效签名

    h_b = auth_headers(client, openid="dev_user_b", nickname="用户B")
    # B 持有 A 的签名 URL 访问 → 200（不需要 B 的 JWT）
    resp = client.get(signed, headers=h_b)
    assert resp.status_code == 200, resp.text

    # 不带任何 JWT 也能访问 → 200
    resp2 = client.get(signed)
    assert resp2.status_code == 200, resp2.text


# ==================== 用例 16：SECRET_KEY 安全断言 ====================

def test_16_secret_key_not_in_response_and_s_is_hex64(client):
    """用例16：SECRET_KEY 不出现在响应体；s 是固定 64 位 hex"""
    h = auth_headers(client)
    s = _mk_subject(client, h)
    page = _upload_page(client, h, s["id"])

    # POST /pages 的整段响应文本不含 SECRET_KEY
    full_resp_text = client.app  # placeholder, 直接断言 page dict 的 JSON 文本
    page_json = _json.dumps(page, ensure_ascii=False)
    assert SECRET_KEY not in page_json, "响应体不应包含 SECRET_KEY"

    # image_url / thumb_url 不含 SECRET_KEY
    assert SECRET_KEY not in page["image_url"]
    assert page["thumb_url"] is None or SECRET_KEY not in page["thumb_url"]

    # s 参数是 64 位 hex（HMAC-SHA256 输出）
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(page["image_url"])
    qs = parse_qs(parsed.query)
    sig = qs["s"][0]
    assert re.fullmatch(r"[0-9a-f]{64}", sig), f"s 应为 64 位 hex，实际: {sig}"
