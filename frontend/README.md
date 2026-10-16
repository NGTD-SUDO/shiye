# 拾页 · 前端（Flutter）

手机端与 Windows 桌面端共用一套业务代码。项目总览见仓库根 `README.md`，架构说明见 `docs/architecture.md`。

## 本地开发

```bash
flutter pub get
flutter analyze
flutter test

# 跑在 Windows 桌面（调试最快）
flutter run -d windows --dart-define=API_BASE_URL=http://127.0.0.1:8000

# 打 Android 包（真机连局域网后端）
flutter build apk --debug --dart-define=API_BASE_URL=http://192.168.x.x:8000
```

## 约定

- **不硬编码服务地址**：一切走 `--dart-define=API_BASE_URL=...`，默认值 `http://127.0.0.1:8000`（见 `lib/core/api/api_client.dart`）
- 主题与设计令牌集中管理，禁止在页面里散落硬编码色值
- 触控目标 ≥44px；三级文字要满足可读性对比度
- 跑完测试/构建后清理产物（`build/`、`.dart_tool/`、`local.properties`、`.flutter-plugins-dependencies`、`windows/flutter/ephemeral/`），别提交进仓库
- 字体 `assets/fonts/MaShanZheng-Regular.ttf` 为 SIL OFL 1.1 授权，许可证随仓库分发（`assets/fonts/OFL.txt`）

## 目录

```
lib/
  core/      API 客户端、数据模型、主题、通用组件
  features/  auth / subjects / pages / search / review / study / legal …
```
