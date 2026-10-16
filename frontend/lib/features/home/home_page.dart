/// 主页容器 — 4 tab（首页 / 搜索 / 学情 / 我的）
///
/// T13-3：导航由 5 Tab 改 4 Tab（index 连续 0-3）；原「中央凸出拍照按钮」已移除，
/// 拍照主入口迁到首页右上角「＋ 拍照」（见 `subjects_page.dart`）。
library;

import 'dart:ui' show ImageFilter;

import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../shared/widgets/motion.dart';
import 'profile_page.dart';
import 'search_page.dart';
import 'study_page.dart';
import 'subjects_page.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: const [
          SubjectsPage(), // 0 首页（科目列表）
          SearchPage(), // 1 搜索
          StudyPage(), // 2 学情
          ProfilePage(), // 3 我的
        ],
      ),
      bottomNavigationBar: _buildBottomBar(),
    );
  }

  /// §3.1：底部 Tab 栏改「毛玻璃悬浮」——
  /// 半透明 `surfaceMuted(.84)` + `BackdropFilter blur 22` + 0.5px 顶分隔线，高度 60 → 76。
  Widget _buildBottomBar() {
    return SafeArea(
      top: false,
      child: Container(
        height: 76,
        decoration: BoxDecoration(
          color: AppColors.surfaceMuted.withValues(alpha: .84),
          border: const Border(
            top: BorderSide(color: AppColors.border, width: 0.5),
          ),
        ),
        child: ClipRect(
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 22, sigmaY: 22),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
              // T13-3：4 个 Tab 由 Expanded 均分（不再依赖中央凸出按钮撑结构）
              child: Row(
                children: [
                  _buildItem(0, Icons.home_rounded, '首页'),
                  _buildItem(1, Icons.search_rounded, '搜索'),
                  _buildItem(2, Icons.insights_rounded, '学情'),
                  _buildItem(3, Icons.person_rounded, '我的'),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildItem(int i, IconData icon, String label) {
    final selected = _index == i;
    final color = selected ? AppColors.primary : AppColors.inkTertiary;
    return Expanded(
      // §3.7 按压缩放（demo `.tab:active` = .88）
      child: PressableScale(
        pressedScale: .88,
        child: InkWell(
          onTap: () => setState(() => _index = i),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // §3.7 Tab 图标 spring 弹跳（easeOutBack 过冲回弹；对齐 demo 切换 .35s）
              TweenAnimationBuilder<double>(
                tween: Tween<double>(begin: 1, end: selected ? 1.06 : 1),
                duration: const Duration(milliseconds: 350),
                curve: Curves.easeOutBack,
                builder: (_, scale, child) => Transform.scale(scale: scale, child: child),
                child: Icon(icon, size: 24, color: color),
              ),
              const SizedBox(height: 2),
              Text(
                label,
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
                  color: color,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
