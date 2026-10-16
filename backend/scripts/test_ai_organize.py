"""端到端 AI 整理测试：上传素材库图片 → 等待 OCR → 调用 AI 整理 → 输出结果"""
import time
import httpx

BASE = "http://127.0.0.1:8000"
client = httpx.Client(timeout=60.0)

# 1. 登录
r = client.post(f"{BASE}/auth/dev-login", json={"openid": "ai_test"})
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

# 2. 建学科
r = client.post(f"{BASE}/subjects", json={"name": "AI整理测试"}, headers=h)
sid = r.json()["id"]
print(f"学科ID: {sid}")

# 3. 上传素材库图片
img_path = r"f:\笔记整理app\素材库\Screenshot_20260905_104911.jpg"
with open(img_path, "rb") as f:
    files = {"file": ("note.jpg", f, "image/jpeg")}
    data = {"subject_id": str(sid)}
    r = client.post(f"{BASE}/pages", headers=h, data=data, files=files)
pid = r.json()["id"]
print(f"页ID: {pid}")

# 4. 轮询等待 OCR 完成
for i in range(30):
    r = client.get(f"{BASE}/pages/{pid}", headers=h)
    state = r.json()["ocr_state"]
    print(f"  [{i+1}] ocr_state={state}")
    if state == "done":
        break
    if state == "failed":
        print("OCR 失败:", r.json().get("ocr_error"))
        exit(1)
    time.sleep(1)
else:
    print("OCR 超时")
    exit(1)

page = r.json()
print(f"\n=== OCR 原文（前300字）===")
print(page["ocr_text"][:300])

# 5. 调用 AI 整理
print(f"\n=== 调用 AI 整理 ===")
t0 = time.time()
r = client.post(f"{BASE}/pages/{pid}/organize", headers=h)
dt = time.time() - t0
print(f"耗时: {dt:.1f}s, HTTP {r.status_code}")
if r.status_code != 200:
    print("错误:", r.json())
    exit(1)

result = r.json()
print(f"\n=== AI 整理结果 ===")
print(result["structured_text"])
