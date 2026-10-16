/// 拾页 App — 主入口
///
/// T12（零采集）：这里**不再** `..init()` 启动认证 —— 认证初始化可能发网络请求，
/// 必须等用户在隐私弹窗点【同意】后由 [AppRouter] 触发。
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app_router.dart';
import 'core/api/api_client.dart';
import 'core/auth_provider.dart';
import 'core/theme/app_theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ShiyeApp());
}

class ShiyeApp extends StatelessWidget {
  /// 测试注入用；生产为 `null`（走单例 [ApiClient]）
  final ApiClient? api;

  const ShiyeApp({super.key, this.api});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      // ⚠️ 不在这里 init()：同意前不得发起任何网络请求（见 app_router.dart）
      create: (_) => AuthProvider(api: api),
      child: MaterialApp(
        title: '拾页',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.dark(),
        home: const AppRouter(),
      ),
    );
  }
}
