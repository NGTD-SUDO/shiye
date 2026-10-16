/// 登录页 — 内测邀请码登录（openid 由设备标识自动生成）
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/api/api_client.dart';
import '../../core/auth_provider.dart';
import '../../core/device_id.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _inviteCodeCtrl = TextEditingController();
  final _nicknameCtrl = TextEditingController(text: '小拾');
  bool _loading = false;

  @override
  void dispose() {
    _inviteCodeCtrl.dispose();
    _nicknameCtrl.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    final inviteCode = _inviteCodeCtrl.text.trim();
    if (inviteCode.isEmpty) {
      // 邀请码为空时不发请求，直接中文提示
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请输入邀请码')),
      );
      return;
    }
    setState(() => _loading = true);
    try {
      // 在 await 之前取 Provider，避免跨 async gap 使用 BuildContext
      final auth = Provider.of<AuthProvider>(context, listen: false);
      // openid 由设备标识自动生成，界面上不再出现 openid 输入框
      final deviceId = await getDeviceId();
      await auth.devLogin(
        deviceId,
        nickname: _nicknameCtrl.text.trim().isEmpty ? null : _nicknameCtrl.text.trim(),
        inviteCode: inviteCode,
      );
    } catch (e) {
      // T4-3：走统一异常→中文文案映射（ApiException 保留后端 detail，其它异常给中文提示）
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(mapExceptionToMessage(e))),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xxl),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: AppSpacing.xxl * 2),
              // App 名 + 副标题
              Center(
                child: Column(
                  children: [
                    Container(
                      width: 72,
                      height: 72,
                      decoration: BoxDecoration(
                        color: AppColors.primaryBg,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: const Icon(
                        Icons.menu_book_rounded,
                        size: 40,
                        color: AppColors.primary,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    Text(
                      '拾页',
                      style: Theme.of(context).textTheme.displayLarge,
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      '手写笔记 · 拍照数字化',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.xxl * 2),
              // 纸色卡片包裹输入区
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        '内测登录',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: AppSpacing.lg),
                      TextField(
                        controller: _inviteCodeCtrl,
                        decoration: const InputDecoration(
                          labelText: '内测邀请码',
                          hintText: '由发起人提供',
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      TextField(
                        controller: _nicknameCtrl,
                        decoration: const InputDecoration(
                          labelText: '昵称（可选）',
                          hintText: '展示用昵称',
                        ),
                      ),
                      const SizedBox(height: AppSpacing.lg),
                      FilledButton(
                        onPressed: _loading ? null : _login,
                        style: FilledButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(AppRadius.button),
                          ),
                        ),
                        child: _loading
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : const Text('登录'),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.xxl),
              Center(
                child: Text(
                  '内测模式 · 设备标识自动生成',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
