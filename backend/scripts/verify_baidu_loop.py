"""完整闭环验证：百度 OCR 端到端"""
import json
import time
import pathlib
import urllib.request
import urllib.parse

BASE = "http://127.0.0.1:8000"
import argparse, os
# 样例图由调用方提供（仓库不含任何个人笔记图片）
SAMPLE = pathlib.Path(os.environ.get("SHIYE_SAMPLE_IMAGE", "sample_note.jpg"))


def req(method, path, headers=None, data=None, json_body=None, files=None):
    url = f"{BASE}{path}"
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers = headers or {}
        headers["Content-Type"] = "application/json"
    elif files:
        boundary = "----boundary123456"
        body = b""
        for field, (fname, content, ctype) in files.items():
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{field}"; filename="{fname}"\r\n'.encode()
            body += f"Content-Type: {ctype}\r\n\r\n".encode()
            body += content
            body += b"\r\n"
        for field, val in (data or {}).items():
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{field}"\r\n\r\n'.encode()
            body += f"{val}\r\n".encode()
        body += f"--{boundary}--\r\n".encode()
        data = body
        headers = headers or {}
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif data and isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()
        headers = headers or {}
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    r = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode())


print("=" * 70)
print("拾页 · 百度 OCR 完整闭环验证")
print("=" * 70)

# 1. dev 登录
r = req("POST", "/auth/dev-login", json_body={"openid": "test_baidu_loop"})
token = r["access_token"]
h = {"Authorization": f"Bearer {token}"}
print(f"[1] dev 登录 ✓ user_id={r['user_id']}")

# 2. 建学科
import time as _t
subj_name = f"数学_{int(_t.time())}"
r = req("POST", "/subjects", headers=h, json_body={"name": subj_name})
subj_id = r["id"]
print(f"[2] 建学科 '{subj_name}' ✓ id={subj_id}")

# 3. 上传图片
with open(SAMPLE, "rb") as f:
    img_data = f.read()
r = req("POST", "/pages", headers=h, data={"subject_id": str(subj_id)},
        files={"file": ("sample.jpg", img_data, "image/jpeg")})
page = r
page_id = page["id"]
print(f"[3] 上传图片 ✓ page_id={page_id} 初始状态={page['ocr_state']}")

# 4. 轮询 OCR 状态
print(f"[4] 等待百度 OCR 完成...", end="", flush=True)
ocr_text = None
for i in range(30):
    time.sleep(1)
    p = req("GET", f"/pages/{page_id}", headers=h)
    if p["ocr_state"] == "done":
        ocr_text = p["ocr_text"]
        print(f"\n    ✓ 完成！置信度={p['ocr_conf']:.3f} 标题='{p['title']}'")
        break
    elif p["ocr_state"] == "failed":
        print(f"\n    ✗ 失败: {p.get('ocr_error')}")
        break
    print(".", end="", flush=True)
else:
    print("\n    ✗ 超时")

if ocr_text:
    print(f"    识别文本预览: {ocr_text[:120]}...")

    # 5. 搜索
    chars = [c for c in ocr_text if c.strip()]
    search_word = chars[0] + chars[1] if len(chars) >= 2 else (chars[0] if chars else "测")
    r = req("GET", f"/search?q={urllib.parse.quote(search_word)}", headers=h)
    print(f"[5] 搜索 '{search_word}' ✓ 命中 {len(r)} 条")

    # 6. 人工修正写回
    r = req("PATCH", f"/pages/{page_id}", headers=h,
            json_body={"ocr_text": "人工校对测试文本 abc123xyz"})
    print(f"[6] 人工修正 ✓ 新状态={r['ocr_state']}")

    # 验证修正写回索引
    r = req("GET", "/search?q=abc123xyz", headers=h)
    hit = len(r) > 0
    print(f"    修正词 'abc123xyz' 搜索命中: {'✓' if hit else '✗'}")

    r = req("GET", f"/search?q={urllib.parse.quote(search_word)}", headers=h)
    old_hit = len(r) > 0
    print(f"    旧词 '{search_word}' 搜索命中: {'✓(仍有)' if old_hit else '✗(已移除)'}")

print("=" * 70)
print("闭环验证完成")
