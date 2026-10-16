/// 拾页设计令牌 — 色板（iOS 深色）
///
/// T13-2：全 App 换 iOS systemDark 色板 —— 清新绿 → systemBlue，浅底 → 深底。
/// 取值来自设计稿 `拾页-iOS深色-demo.html`（iOS HIG 官方值），**勿自创**。
library;

import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  // 主色（systemBlue）
  static const Color primary = Color(0xFF007AFF);
  static const Color primaryLight = Color(0xFF3D9BFF);
  static const Color primaryDark = Color(0xFF0062CC);
  static const Color primaryBg = Color(0x1F007AFF);

  // 纸质卡片 —— 深色下"纸感"失效，改用 systemGray 明度层级
  static const Color paperWarm = Color(0xFF2C2C2E); // systemGray5：卡片
  static const Color paperCream = Color(0xFF3A3A3C); // systemGray4：更高层
  static const Color paperLine = Color(0x3DFFFFFF); // 白 24% 分隔
  static const Color paperFold = Color(0x1FFFFFFF); // 白 12%

  // 墨色文字 —— 深色下三档白
  static const Color ink = Color(0xFFFFFFFF); // 主文字
  static const Color inkSecondary = Color(0x99EBEBF5); // 白 60%
  // T13-3：白 30% 是 iOS tertiaryLabel（给图标/装饰的），我们拿它承载了辅助正文
  // → 印刷/深底上对比度仅 2.07:1（vs 卡片底）不可读，提到白 50% 后 3.18:1。
  // ⚠️ 不再往上提到 60%（那会与 inkSecondary 混层，失去三档层级）。
  static const Color inkTertiary = Color(0x80EBEBF5); // 白 50%

  // 中性面
  static const Color surface = Color(0xFF1C1C1E); // systemGray6：页面底
  static const Color surfaceMuted = Color(0xFF1C1C1E); // 同页面底
  static const Color border = Color(0x3D545458); // iOS separator

  // 功能色
  static const Color blue = Color(0xFF007AFF);
  static const Color orange = Color(0xFFFF9F0A); // systemOrange：处理中/警告
  static const Color red = Color(0xFFFF453A); // systemRed：失败/删除

  // ── 语义令牌（T13-1 建立，T13-2 换深色取值）──

  /// 卡片/容器背景 = systemGray5（比页面底亮一档 → 靠明度分层，不再描边）
  static const Color cardBackground = Color(0xFF2C2C2E);

  /// 玻璃态填充（深色下"提亮"而非"压白"）：白 12%
  ///
  /// T13-2：调用处一律改用**令牌自带 alpha**（不再各自传 .6~.85 的浅色值），
  /// 因此全 App 玻璃填充统一为 12%，色盘是唯一真相源。
  static const Color glassFill = Color(0x1FFFFFFF);

  /// 玻璃态描边：白 16%（同上，调用处不再覆盖 alpha）
  static const Color glassBorder = Color(0x29FFFFFF);

  /// 阴影 / 压暗蒙层（深色下取值不变）
  static const Color shadow = Color(0x73000000);
}
