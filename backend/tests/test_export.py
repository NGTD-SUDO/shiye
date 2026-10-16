"""T11-A 导出测试（单页 / 整章，md + txt）

覆盖任务书 T11-A5 要求的全部场景：
- 取数两路（structured_text 优先 / 回退 ocr_text）
- 两者都空 → 400 + 中文原因（绝不返回空文件）
- 跨用户 → 404 且响应体与「不存在」逐字节一致
- 混合来源标注（数字必须对）/ 全部未整理 / 全部已整理
- 中文文件名 Content-Disposition（RFC 5987）编码正确
- md / txt 两种 format
- 纯函数层单测（取数、文件名、标注、排序与跳过）
"""
from urllib.parse import unquote

import pytest

from app.services import export_service as ex
from tests.conftest import auth_headers, make_jpg_bytes

# ==================== 纯函数层 ====================


class _P:
    """轻量页替身（纯函数层测试用，不依赖 DB）"""

    def __init__(self, id=1, title="", page_no=None, ocr_text="", structured_text=None):
        self.id = id
        self.title = title
        self.page_no = page_no
        self.ocr_text = ocr_text
        self.structured_text = structured_text


def test_normalize_format_ok_and_invalid():
    assert ex.normalize_format(None) == "md"
    assert ex.normalize_format("MD") == "md"
    assert ex.normalize_format("txt") == "txt"
    with pytest.raises(ValueError, match="不支持的导出格式"):
        ex.normalize_format("pdf")


def test_sanitize_filename_removes_illegal_chars():
    # 非法字符 → 下划线；首尾的下划线/点/空白会被去掉
    assert ex.sanitize_filename('数学/几何:第1页?"<>|') == "数学_几何_第1页"
    assert ex.sanitize_filename("  多余   空白  ") == "多余 空白"
    assert ex.sanitize_filename("") == "导出"


def test_content_disposition_rfc5987_encodes_chinese():
    cd = ex.content_disposition("数学-导数定义.md")
    assert cd.startswith("attachment;")
    assert "filename*=UTF-8''" in cd
    assert "filename=\"export.md\"" in cd  # ASCII 兜底
    encoded = cd.split("filename*=UTF-8''", 1)[1]
    assert encoded == "%E6%95%B0%E5%AD%A6-%E5%AF%BC%E6%95%B0%E5%AE%9A%E4%B9%89.md"
    assert unquote(encoded) == "数学-导数定义.md"
    assert "数学" not in cd  # 头部里不得出现未编码的中文


def test_page_export_prefers_structured_text():
    p = _P(title="导数定义", ocr_text="原始识别", structured_text="# 整理稿")
    content, filename = ex.build_page_export(p, "数学")
    assert content.strip() == "# 整理稿"
    assert filename == "数学-导数定义.md"


def test_page_export_falls_back_to_raw_text():
    p = _P(title="导数定义", ocr_text="原始识别文本", structured_text="   ")
    content, filename = ex.build_page_export(p, "数学", "txt")
    assert content.strip() == "原始识别文本"
    assert filename == "数学-导数定义.txt"


def test_page_export_both_empty_raises_chinese():
    with pytest.raises(ValueError, match="该页没有可导出的文本"):
        ex.build_page_export(_P(ocr_text="", structured_text=None), "数学")


def test_page_label_fallbacks():
    assert ex.page_label(_P(title="标题")) == "标题"
    assert ex.page_label(_P(title="", page_no=7)) == "第7页"
    assert ex.page_label(_P(title="", page_no=None), ordinal=3) == "第3页"
    assert ex.page_label(_P(id=42, title="", page_no=None)) == "第42页"


def test_chapter_source_note_three_cases():
    assert ex.chapter_source_note(4, 2) == "本稿含 4 页 AI 整理 + 2 页原始识别"
    assert ex.chapter_source_note(3, 0) == "本稿全部为 AI 整理稿"
    assert ex.chapter_source_note(0, 3) == "本稿全部为原始识别文本，未经 AI 整理"
    # 有页被跳过时必须额外注明，避免用户以为整章都在稿里
    assert ex.chapter_source_note(1, 0, 2) == "本稿全部为 AI 整理稿（另有 2 页无文本，未包含）"


def test_chapter_export_mixed_note_separators_and_counts():
    pages = [
        _P(id=1, title="第一页", ocr_text="原始一", structured_text="# 整理一"),
        _P(id=2, title="第二页", ocr_text="原始二", structured_text=None),
        _P(id=3, title="第三页", ocr_text="原始三", structured_text="  "),
    ]
    content, filename = ex.build_chapter_export(pages, "立体几何", "第一章")

    assert content.startswith("> 本稿含 1 页 AI 整理 + 2 页原始识别")
    assert "## 第 1 页 · 第一页" in content
    assert "# 整理一" in content
    assert "原始二" in content and "原始三" in content
    assert content.count("\n---\n") == 2  # 3 页之间有 2 条分隔
    assert filename == "立体几何-第一章.md"


def test_chapter_export_skips_empty_pages_but_counts():
    pages = [
        _P(id=1, title="有整理", ocr_text="原始一", structured_text="# 整理一"),
        _P(id=2, title="有原文", ocr_text="原始二", structured_text=None),
        _P(id=3, title="全空页", ocr_text="", structured_text=None),
    ]
    content, _ = ex.build_chapter_export(pages, "数学", "第一章")

    assert "本稿含 1 页 AI 整理 + 1 页原始识别" in content  # 空页不计入两类来源
    assert "全空页" not in content  # 被跳过的页不出现在导出稿里
    assert "## 第 3 页" not in content  # 页码沿用章内原始序号：第 3 页被跳过
    assert "## 第 1 页 · 有整理" in content
    assert "## 第 2 页 · 有原文" in content


def test_chapter_export_all_pages_empty_raises():
    pages = [_P(ocr_text="", structured_text=None), _P(ocr_text="   ", structured_text="")]
    with pytest.raises(ValueError, match="该章下没有可导出的文本"):
        ex.build_chapter_export(pages, "数学", "空章")


def test_chapter_export_txt_has_plain_note():
    pages = [_P(id=1, title="甲", ocr_text="原文甲", structured_text=None)]
    content, filename = ex.build_chapter_export(pages, "数学", "第一章", "txt")
    assert content.startswith("本稿全部为原始识别文本，未经 AI 整理")
    assert not content.startswith("> ")
    assert filename == "数学-第一章.txt"


# ==================== 接口层 ====================


def _subject(client, headers, name="数学") -> int:
    r = client.post("/subjects", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _chapter(client, headers, subject_id, name="第一章") -> int:
    r = client.post(f"/subjects/{subject_id}/chapters", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _page(client, headers, subject_id, chapter_id=None, title=None, structured=None, ocr=None) -> int:
    data = {"subject_id": str(subject_id)}
    if chapter_id is not None:
        data["chapter_id"] = str(chapter_id)
    r = client.post(
        "/pages",
        headers=headers,
        data=data,
        files={"file": ("a.jpg", make_jpg_bytes(), "image/jpeg")},
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    fields = {}
    if title is not None:
        fields["title"] = title
    if structured is not None:
        fields["structured_text"] = structured
    if ocr is not None:
        fields["ocr_text"] = ocr
    if fields:
        r = client.patch(f"/pages/{pid}", headers=headers, json=fields)
        assert r.status_code == 200, r.text
    return pid


def _filename_of(resp) -> str:
    cd = resp.headers["content-disposition"]
    assert "filename*=UTF-8''" in cd
    return unquote(cd.split("filename*=UTF-8''", 1)[1])


def test_export_page_md_uses_structured_and_headers(client):
    h = auth_headers(client)
    sid = _subject(client, h, "数学")
    pid = _page(client, h, sid, title="导数定义", structured="# 整理稿正文", ocr="原始识别文本")

    r = client.get(f"/pages/{pid}/export?format=md", headers=h)
    assert r.status_code == 200, r.text
    assert r.text.strip() == "# 整理稿正文"
    assert r.headers["content-type"] == "text/markdown; charset=utf-8"
    assert _filename_of(r) == "数学-导数定义.md"


def test_export_page_txt_and_fallback_to_ocr(client):
    h = auth_headers(client)
    sid = _subject(client, h, "数学")
    pid = _page(client, h, sid, title="导数定义", structured="", ocr="原始识别文本")

    r = client.get(f"/pages/{pid}/export?format=txt", headers=h)
    assert r.status_code == 200, r.text
    assert r.text.strip() == "原始识别文本"
    assert r.headers["content-type"] == "text/plain; charset=utf-8"
    assert _filename_of(r) == "数学-导数定义.txt"


def test_export_page_default_format_is_md(client):
    h = auth_headers(client)
    sid = _subject(client, h, "数学")
    pid = _page(client, h, sid, title="甲", structured="# 甲")
    r = client.get(f"/pages/{pid}/export", headers=h)
    assert r.status_code == 200
    assert "text/markdown" in r.headers["content-type"]


def test_export_page_both_empty_400(client):
    h = auth_headers(client)
    sid = _subject(client, h, "数学")
    pid = _page(client, h, sid, title="空页", structured="", ocr="")

    r = client.get(f"/pages/{pid}/export", headers=h)
    assert r.status_code == 400
    assert "该页没有可导出的文本" in r.json()["detail"]


def test_export_page_invalid_format_400(client):
    h = auth_headers(client)
    sid = _subject(client, h, "数学")
    pid = _page(client, h, sid, title="甲", structured="# 甲")
    r = client.get(f"/pages/{pid}/export?format=pdf", headers=h)
    assert r.status_code == 400
    assert "不支持的导出格式" in r.json()["detail"]


def test_export_page_cross_user_404_same_body_as_missing(client):
    owner = auth_headers(client, "exp_owner")
    other = auth_headers(client, "exp_other")
    sid = _subject(client, owner, "数学")
    pid = _page(client, owner, sid, title="甲", structured="# 甲")

    r_cross = client.get(f"/pages/{pid}/export", headers=other)
    r_missing = client.get("/pages/999999/export", headers=other)
    assert r_cross.status_code == 404
    assert r_missing.status_code == 404
    assert r_cross.text == r_missing.text  # 不泄露存在性


def test_export_page_no_title_uses_subject_ordinal(client):
    h = auth_headers(client)
    sid = _subject(client, h, "数学")
    # 注意：上传时 OCR 会把识别文本首行自动写成标题（T6），这里显式清空标题以验证「第N页」兜底
    _page(client, h, sid, title="", ocr="第一页原文")
    pid2 = _page(client, h, sid, title="", ocr="第二页原文")

    r = client.get(f"/pages/{pid2}/export", headers=h)
    assert r.status_code == 200
    assert _filename_of(r) == "数学-第2页.md"


def test_export_chapter_mixed_note_and_content(client):
    h = auth_headers(client)
    sid = _subject(client, h, "立体几何")
    cid = _chapter(client, h, sid, "第一章")
    _page(client, h, sid, chapter_id=cid, title="页一", structured="# 整理过的页一", ocr="原始一")
    _page(client, h, sid, chapter_id=cid, title="页二", ocr="原始二")
    _page(client, h, sid, chapter_id=cid, title="页三", ocr="原始三")

    r = client.get(f"/subjects/{sid}/chapters/{cid}/export?format=md", headers=h)
    assert r.status_code == 200, r.text
    assert r.text.startswith("> 本稿含 1 页 AI 整理 + 2 页原始识别")
    assert "# 整理过的页一" in r.text
    assert "原始二" in r.text and "原始三" in r.text
    assert "## 第 2 页 · 页二" in r.text
    assert _filename_of(r) == "立体几何-第一章.md"


def test_export_chapter_all_raw_note(client):
    h = auth_headers(client)
    sid = _subject(client, h, "数学")
    cid = _chapter(client, h, sid, "第二章")
    _page(client, h, sid, chapter_id=cid, title="甲", ocr="原文甲")
    _page(client, h, sid, chapter_id=cid, title="乙", ocr="原文乙")

    r = client.get(f"/subjects/{sid}/chapters/{cid}/export?format=txt", headers=h)
    assert r.status_code == 200, r.text
    assert r.text.startswith("本稿全部为原始识别文本，未经 AI 整理")
    assert r.headers["content-type"] == "text/plain; charset=utf-8"
    assert _filename_of(r) == "数学-第二章.txt"


def test_export_chapter_all_organized_note(client):
    h = auth_headers(client)
    sid = _subject(client, h, "数学")
    cid = _chapter(client, h, sid, "第三章")
    _page(client, h, sid, chapter_id=cid, title="甲", structured="# 甲整理", ocr="原文甲")

    r = client.get(f"/subjects/{sid}/chapters/{cid}/export", headers=h)
    assert r.status_code == 200, r.text
    assert r.text.startswith("> 本稿全部为 AI 整理稿")


def test_export_chapter_skips_empty_page_and_counts(client):
    h = auth_headers(client)
    sid = _subject(client, h, "数学")
    cid = _chapter(client, h, sid, "第四章")
    _page(client, h, sid, chapter_id=cid, title="有整理", structured="# 整理稿")
    _page(client, h, sid, chapter_id=cid, title="全空页", structured="", ocr="")

    r = client.get(f"/subjects/{sid}/chapters/{cid}/export", headers=h)
    assert r.status_code == 200, r.text
    # 非空页全是整理稿 → 「全部为 AI 整理稿」；但必须注明有 1 页被跳过
    assert r.text.startswith("> 本稿全部为 AI 整理稿（另有 1 页无文本，未包含）")
    assert "全空页" not in r.text  # 空页被跳过
    assert "# 整理稿" in r.text


def test_export_chapter_all_empty_400(client):
    h = auth_headers(client)
    sid = _subject(client, h, "数学")
    cid = _chapter(client, h, sid, "空章")
    _page(client, h, sid, chapter_id=cid, title="空页", structured="", ocr="")

    r = client.get(f"/subjects/{sid}/chapters/{cid}/export", headers=h)
    assert r.status_code == 400
    assert "该章下没有可导出的文本" in r.json()["detail"]


def test_export_chapter_cross_user_404_same_body_as_missing(client):
    owner = auth_headers(client, "ch_owner")
    other = auth_headers(client, "ch_other")
    sid = _subject(client, owner, "数学")
    cid = _chapter(client, owner, sid, "第一章")
    _page(client, owner, sid, chapter_id=cid, title="甲", structured="# 甲")

    r_cross = client.get(f"/subjects/{sid}/chapters/{cid}/export", headers=other)
    r_missing = client.get("/subjects/999999/chapters/999999/export", headers=other)
    assert r_cross.status_code == 404
    assert r_missing.status_code == 404
    assert r_cross.text == r_missing.text
