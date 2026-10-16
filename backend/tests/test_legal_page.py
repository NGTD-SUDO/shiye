"""`GET /legal` 法律文档合页测试（T12 收尾）

覆盖任务书要求：
1. 公开可访问：**不带 token** → 200
2. `Content-Type` 是 `text/html` + `charset=utf-8`
3. 含 4 份文档标题
4. 邮箱实体化：含 `contact&#64;example.com`，**不含裸邮箱**（防 Cloudflare 中间层改写）
5. 回归：`/health`、`/` 仍 200；`/auth/me` 仍需鉴权（新增公开路由没有误开鉴权）
6. F1/F2 修正生效：含「识别文本全文」、不含「基础功能仍可正常使用」
7. `include_in_schema=False`：`/legal` 不进 OpenAPI
8. 响应体与内容常量一致（证明没被二次编码/截断）
"""
from app.legal_content import LEGAL_HTML

FOUR_TITLES = ("隐私政策", "用户协议", "第三方信息共享清单", "个人信息收集清单")


def test_legal_public_without_token_returns_200(client):
    r = client.get("/legal")  # 刻意不带 Authorization
    assert r.status_code == 200, r.text


def test_legal_content_type_is_html_utf8(client):
    ct = client.get("/legal").headers["content-type"].lower()
    assert "text/html" in ct
    assert "charset=utf-8" in ct


def test_legal_contains_four_document_titles(client):
    body = client.get("/legal").text
    for title in FOUR_TITLES:
        assert title in body, f"合页缺少文档标题：{title}"


def test_legal_email_is_entity_and_no_bare_email(client):
    body = client.get("/legal").text
    assert "contact&#64;example.com" in body, "邮箱必须是 HTML 实体 &#64;"
    assert "contact@example.com" not in body, "不得出现裸邮箱（会被隧道中间层改写）"


def test_legal_reflects_f1_f2_fixes(client):
    body = client.get("/legal").text
    # F2：AI 整理会发送「识别文本全文」——已在政策里披露
    assert "识别文本全文" in body
    # F1：与路线 A 矛盾的旧句已删除
    assert "基础功能仍可正常使用" not in body


def test_legal_not_in_openapi_schema(client):
    schema = client.get("/openapi.json").json()
    assert "/legal" not in schema.get("paths", {})


def test_existing_routes_unaffected(client):
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200
    # 业务接口仍然要鉴权：没有因为新增公开路由而误开
    assert client.get("/auth/me").status_code in (401, 403)


def test_legal_body_equals_content_constant(client):
    # 响应体与常量逐字一致（排除二次编码 / 截断 / 转义问题）
    assert client.get("/legal").text == LEGAL_HTML


def test_legal_constant_shape():
    """常量本身的形状约束（便于后续更新时自检）"""
    assert len(LEGAL_HTML) == 32149, "内容长度应与生成脚本产出一致（公开版已把联系方式占位化）"
    assert '"""' not in LEGAL_HTML, "不得含连续三个双引号（否则破坏三引号承载）"
    assert "\r" not in LEGAL_HTML, "行尾已统一为 LF"
    assert LEGAL_HTML.lstrip().startswith("<!DOCTYPE html>") or LEGAL_HTML.lstrip().startswith("<!doctype html>")
