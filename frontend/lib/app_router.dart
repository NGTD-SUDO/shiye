/// 路由 — **最优先**判定隐私同意状态，其次才是登录态
///
/// T12-1：同意弹窗的判定顺序在登录态判断**之前**（未处理隐私前，连登录页都不进）。
/// T12（零采集）：认证初始化（`AuthProvider.init()` 可能发 `GET /auth/me` 网络请求）
/// 被**延后到同意之后** —— 这是"同意前零采集"的关键落点（见 `_startAuthOnce`）。
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/auth_provider.dart';
import 'core/privacy_service.dart';
import 'features/auth/login_page.dart';
import 'features/home/home_page.dart';
import 'features/legal/privacy_consent_dialog.dart';

class AppRouter extends StatefulWidget {
  const AppRouter({super.key});

  @override
  State<AppRouter> createState() => _AppRouterState();
}

class _AppRouterState extends State<AppRouter> {
  bool _authStarted = false;

  @override
  void initState() {
    super.initState();
    // 只读**本地**同意标记：不发网络请求、不读设备标识、不申请任何权限
    PrivacyService.instance.load();
  }

  /// 启动认证流程 —— **只在用户已同意后调用**
  ///
  /// 放在 postFrame 回调里，避免 build 期间 `notifyListeners()`。
  void _startAuthOnce() {
    if (_authStarted) return;
    _authStarted = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<AuthProvider>().init();
    });
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: PrivacyService.instance,
      builder: (context, _) {
        final agreed = PrivacyService.instance.agreed;

        // ① 本地状态尚未读出（极短瞬间）：不启动任何流程
        if (agreed == null) {
          return const PrivacyChecking();
        }

        // ② 未同意：空屏 + 不可关闭的同意弹窗（**在登录态判断之前**）
        if (!agreed) {
          return PrivacyConsentScreen(
            onAgreed: () => PrivacyService.instance.agree(),
          );
        }

        // ③ 已同意：此时才允许发起网络请求
        _startAuthOnce();
        final auth = context.watch<AuthProvider>();
        if (!auth.initialized) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        if (!auth.isLoggedIn) {
          return const LoginPage();
        }
        return const HomePage();
      },
    );
  }
}
