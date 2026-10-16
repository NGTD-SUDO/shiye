"""认证接口测试"""
from tests.conftest import auth_headers


def test_dev_login_and_me(client):
    resp = client.post("/auth/dev-login", json={"openid": "dev_a1", "nickname": "小明"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["nickname"] == "小明"
    assert data["user_id"] > 0

    headers = {"Authorization": f"Bearer {data['access_token']}"}
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["nickname"] == "小明"


def test_same_openid_returns_same_user(client):
    h1 = auth_headers(client, openid="dev_same", nickname="甲")
    h2 = auth_headers(client, openid="dev_same", nickname="乙")
    id1 = client.get("/auth/me", headers=h1).json()["id"]
    id2 = client.get("/auth/me", headers=h2).json()["id"]
    assert id1 == id2
    # 已有昵称不覆盖
    assert client.get("/auth/me", headers=h2).json()["nickname"] == "甲"


def test_me_requires_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code in (401, 403)


def test_update_me_nickname(client):
    h = auth_headers(client)
    resp = client.patch("/auth/me", json={"nickname": "新昵称"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["nickname"] == "新昵称"


def test_wechat_requires_config(client):
    """未配置微信凭据时返回 503（本地/测试默认未配置）"""
    resp = client.post("/auth/wechat", json={"code": "wx_code_123"})
    assert resp.status_code == 503
