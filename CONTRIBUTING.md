# 贡献指南

先说结论：**这个项目目前以「个人自用 + 可自部署」为主，暂不承诺接收 PR**。
Issue 里报 Bug 与提需求是欢迎的；想改代码，建议先开 Issue 对一下方向，避免白做。

## 开发环境

```bash
# 后端
cd backend
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
pytest tests/ -q

# 前端
cd frontend
flutter pub get
flutter analyze
flutter test
```

## 提交代码的硬约束

1. **不写假数据、不写假功能**：宁可空态或报错，也不许硬编码示例数据、不许只弹提示不干活
2. **不降级构建链**：SDK / AGP / Kotlin / Flutter 版本只升不降，不许为过编译而退版本
3. **改动要有真实证据**：贴出真实命令与输出（测试通过数、真机步骤），不接受「应该没问题」
4. **密钥永不入库**：`.env` 已被忽略；新增配置一律先进 `.env.example` 并写注释
5. **UI 改动先提案再动手**：设计类改动请先给方案（截图/文字），对齐后再写
6. 不引入大依赖来解决小问题（本项目刻意保持零外部服务依赖，除 OCR/AI 的可选云 API）

## 提交信息

中文简述即可，说明「做了什么 + 为什么」，例如：

```
fix: 修复搜索框在空结果时点击无反应
feat: 整章 AI 整理结果落库，消除同章重复调用
```

## 测试要求

- 后端：新增能力必须带 `pytest` 用例（含边界与安全用例），`pytest tests/` 全绿
- 前端：`flutter analyze` 无新增告警；交互改动附真机/桌面端验证步骤
- 涉及数据库结构变更：贴出「变更前后表结构 diff」
