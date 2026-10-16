# 拾页 ShiYe · 手写学科笔记数字化整理

> **拍一下，一搜就到。** 把纸质手写学科笔记拍照 → OCR 成文字 → 按学科归档 → 关键词全文搜索。
> Flutter（Android / Windows）+ FastAPI + SQLite，**可完全自部署**，笔记数据不出你自己的服务器。

[English TL;DR](#english-tldr) · [快速开始](#快速开始) · [数据与隐私](#数据与隐私重要) · [部署文档](docs/deployment.md)

---

## 它解决什么问题

纸质笔记的三个老毛病：**找不到**（想搜「导数求极值」只能一页页翻）、**带不走**（期末想整理成电子档）、**丢过就不在了**。

拾页的定位是**「学科笔记库」而不是「扫描仪」**：

1. **随手收**：下课把今天写的几页拍下来 → 选学科 → 归档（一页 30 秒内）
2. **找得到**：考前搜关键词 → 命中页码缩略图 + OCR 文本片段 → 点开看原图
3. **批量整**（电脑端）：批量导入 / 左右分栏校对识别错误 / 导出备份

**与非目标的边界**：不做 App 内手写（对手是 GoodNotes，我们整理的是**纸质**笔记）、不做协作、不做笔记社交、不做复杂格式导入。

## 功能现状（截至 2026-09）

**已实现**

- 拍照 / 相册多选 → 手动 4 角裁剪 + 增强滤镜 → 选学科归档，支持连拍
- 学科 → 章 → 页 三级结构；网格 / 列表浏览、图片缩放
- **异步 OCR**：`pending → processing → done/failed` 状态机、失败可重试、重启自动补投
- **OCR 引擎可切换**：百度手写识别 API（默认，识别率更高）/ RapidOCR 自部署（数据不出服务器）
- **全文搜索**：SQLite FTS5 + trigram；校对修正后的文本**直接写回索引**（这是「接受识别不完美」的落点）
- **校对闭环**：识别结果可改，改完搜索立刻准
- **整章 AI 整理结果落库**：同一章不重复调用 AI，省 token
- **AI 学情分析**：真实统计 + DeepSeek 单次轻请求（只发统计与标题，不发图片/全文），数据太少时出真实空态而不是编造
- 出题 → 作答 → 判分 → 学情诊断闭环
- 导出 Markdown / 纯文本
- 隐私合规：首次启动弹窗（**同意前零采集**，有测试钉住）、4 份法律文档、注销账号

**规划中**：自动边缘裁剪、OCR 词坐标高亮、离线队列、深色模式、导出整库 ZIP

## 技术栈

| 层 | 选型 |
|---|---|
| 移动 / 桌面端 | Flutter（同一仓库多 target：Android、Windows 桌面） |
| 后端 | FastAPI + SQLAlchemy + SQLite + JWT |
| 搜索 | SQLite FTS5 + trigram 分词（中文子串匹配友好） |
| OCR | 抽象接口 `OcrProvider`：百度手写 API / RapidOCR（PaddleOCR ONNX，CPU 可跑） |
| AI | DeepSeek（单次轻请求，按次计费；接口预留可换其他 OpenAI 兼容服务） |
| 图片 | 客户端裁剪压缩；服务端 Pillow 增强 + 磁盘存储 |

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate      # Windows；Linux/macOS 用 source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                 # 按注释填 key
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

需要的最小配置（`.env`）：

- `SHIYE_SECRET_KEY` —— **≥32 位随机字符串**（生产不填会直接拒绝启动）
- `SHIYE_OCR=baidu` + `SHIYE_BAIDU_API_KEY` / `SHIYE_BAIDU_SECRET_KEY`（[百度智能云](https://console.bce.baidu.com/ai/) 创建「文字识别」应用即可拿）
  或 `SHIYE_OCR=rapidocr` + `pip install -r requirements-rapidocr.txt`（首次会下 ~300MB 模型，离线可用）
- `SHIYE_DEEPSEEK_API_KEY` —— AI 整理 / 学情分析用（[DeepSeek 开放平台](https://platform.deepseek.com/)）
- `SHIYE_DEV_MODE=false` —— **生产必须 false**（true 会开放免密开发登录）

```bash
pytest tests/          # 全量后端测试（257 项）
```

### 2. 前端

```bash
cd frontend
flutter pub get
flutter build apk --debug --dart-define=API_BASE_URL=http://<你的服务器IP>:8000
```

> 手机连局域网后端时：后端要 `--host 0.0.0.0`，且 Android 9+ 需要允许明文 HTTP（内测版已开 `usesCleartextTraffic`）。
> 生产建议上 HTTPS（反代或隧道），再改 `API_BASE_URL` 重新打包。

### 3. 部署

自己服务器（systemd / Docker / 反代）见 **[docs/deployment.md](docs/deployment.md)**。

## 数据与隐私（重要）

- **默认自部署**：笔记图片与文本存在你自己的服务器上，本仓库不含任何用户数据，也不含任何在线服务地址。
- 仓库内 `frontend/assets/legal/` 与 `backend/app/legal_content.py` 里的隐私政策 / 用户协议是**示例模板**，联系方式已占位为 `contact@example.com`。
  **它不构成法律意见**：正式对外提供服务前，请替换成你所在司法辖区要求的真实条款与联系方式，并自行完成合规评估（在中国大陆对外提供服务通常还涉及备案等要求）。
- 若你对外开放服务，务必：`SHIYE_DEV_MODE=false`、设置强 `SHIYE_SECRET_KEY`、按需配置 `SHIYE_CORS_ORIGINS`、用独立的上游 API key。

## 目录结构

```
frontend/     Flutter 应用（Android + Windows），业务代码全在这里
backend/      FastAPI 服务：API、OCR 任务、搜索索引、AI 调用
docs/         架构说明、OCR 选型实测、部署指南、产品需求文档
```

## 第三方资源与许可

| 资源 | 用途 | 许可 |
|---|---|---|
| [MaShanZheng](https://github.com/googlefonts/mashanzheng) 字体 | 标题字体 | SIL OFL 1.1（见 `frontend/assets/fonts/OFL.txt`） |
| 百度智能云 手写文字识别 | OCR（可选） | 商用需遵守其服务条款 |
| DeepSeek API | AI 整理 / 学情分析（可选） | 商用需遵守其服务条款 |
| RapidOCR / PP-OCR 模型 | 离线 OCR（可选） | Apache-2.0（模型另见其仓库声明） |

## License

[MIT](LICENSE)

## English TL;DR

ShiYe (拾页) turns **handwritten paper study notes** into a searchable digital library: shoot a page → OCR → filed by subject → full-text search in Chinese. Flutter (Android/Windows) + FastAPI + SQLite, fully self-hostable — your notes stay on your own server. Legal documents bundled in the app are **sample templates** with placeholder contact info, not legal advice.
