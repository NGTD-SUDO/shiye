/// 拾页主题配置 — iOS 深色（T13-2）
library;

import 'package:flutter/material.dart';
import 'app_colors.dart';
import 'app_spacing.dart';

class AppTheme {
  AppTheme._();

  /// T13-2：App 整体切到 iOS 深色，原来的 `light()` 即本方法（dark）。
  static ThemeData dark() {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.primary,
      brightness: Brightness.dark,
      primary: AppColors.primary,
      surface: AppColors.surface,
      onPrimary: Colors.white,
      onSurface: AppColors.ink,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: AppColors.surfaceMuted,
      fontFamily: '.SF Pro Text',
      textTheme: const TextTheme(
        // 页面大标题：iOS large title = 30 / w700 / letterSpacing -0.4（§3.5）
        displayLarge: TextStyle(fontSize: 30, fontWeight: FontWeight.w700, color: AppColors.ink, letterSpacing: -0.4),
        titleLarge: TextStyle(fontSize: 22, fontWeight: FontWeight.w600, color: AppColors.ink),
        titleMedium: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: AppColors.ink),
        bodyLarge: TextStyle(fontSize: 16, color: AppColors.inkSecondary),
        bodyMedium: TextStyle(fontSize: 14, color: AppColors.inkSecondary),
        bodySmall: TextStyle(fontSize: 12, color: AppColors.inkTertiary),
        labelSmall: TextStyle(fontSize: 11, color: AppColors.inkTertiary),
      ),
      cardTheme: CardThemeData(
        // §3.2：深色下**去掉描边**，靠 cardBackground(比页面底亮一档) 做明度分层
        color: AppColors.cardBackground,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.card),
        ),
        margin: EdgeInsets.zero,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: AppColors.ink,
        centerTitle: false,
        // 导航栏标题：17 / w600；右侧操作图标用主色（§3.5）
        titleTextStyle: TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: AppColors.ink),
        actionsIconTheme: IconThemeData(color: AppColors.primary),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        // 深色下输入框填充 = 白 12%（对齐 demo 的 --fill；用页面底色会"看不见"）
        fillColor: AppColors.paperFold,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.button),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm + 2),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: AppColors.cardBackground,
        selectedItemColor: AppColors.primary,
        unselectedItemColor: AppColors.inkTertiary,
        type: BottomNavigationBarType.fixed,
        selectedLabelStyle: TextStyle(fontSize: 10, fontWeight: FontWeight.w600),
        unselectedLabelStyle: TextStyle(fontSize: 10),
      ),
    );
  }
}
