/// 首次启动隐私弹窗（T12-1 / T12-2，路线 A：拒绝即退出）
///
/// 硬性要求（违反即打回）：
/// 1. 禁止默认勾选 / 默认同意 —— 本弹窗**没有**任何预勾选项，只能主动点【同意】
/// 2. 禁止"点任意处视为同意" —— 遮罩 `barrierDismissible: false`，点空白无任何效果
/// 3. 弹窗不可关闭 —— `barrierDismissible: false` + `PopScope(canPop: false)` 拦返回键
/// 4. **同意前零采集** —— 本文件只做本地状态判断，不发网络请求、不读设备标识、不申请权限
/// 5. 正文可滚动查看全文，含第三方披露（百度智能云、DeepSeek）
/// 6. 不出现"同意即表示接受全部条款"式的隐含捆绑表述
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show SystemNavigator;

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';

class PrivacyConsentDialog extends StatelessWidget {
  /// 点【同意】后的回调（由 AppRouter 写入同意标记并进入正常流程）
  final VoidCallback onAgreed;

  /// 方案 A：点【拒绝并退出APP】后的退出延迟（先让用户看到提示，再退出）
  static const Duration exitDelay = Duration(milliseconds: 1200);

  const PrivacyConsentDialog({super.key, required this.onAgreed});

  /// 弹窗标题
  static const String dialogTitle = '隐私政策';

  /// 弹窗正文（任务书定稿文案，**不得改写**）
  static const String bodyText = '欢迎使用拾页（手写笔记整理 App）。\n'
      '\n'
      '在使用前，请阅读并同意《拾页隐私政策》。我们特别提示：\n'
      '\n'
      '· 拍照/上传会使用你的相机与相册；\n'
      '· 你上传的笔记图片将发送至第三方 OCR 服务（百度智能云）进行文字识别；\n'
      '· 使用 AI 功能时，你的笔记文本内容将发送至 AI 服务（DeepSeek）；\n'
      '· 笔记图片与文本保存在你自己部署的服务器上。\n'
      '\n'
      '不同意将无法使用本 App。';

  /// 以**不可关闭**的对话框形式弹出
  static Future<void> show(BuildContext context, {required VoidCallback onAgreed}) {
    return showDialog<void>(
      context: context,
      barrierDismissible: false, // 点遮罩不关闭、也不代表同意
      builder: (dialogContext) => PopScope(
        canPop: false, // 返回键无效
        child: PrivacyConsentDialog(
          // 先关掉弹窗，再写入同意标记并进入正常流程
          onAgreed: () {
            Navigator.of(dialogContext).pop();
            onAgreed();
          },
        ),
      ),
    );
  }

  void _onReject(BuildContext context) {
    // 不写入任何标记 → 下次启动重新弹窗
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('不同意将无法使用拾页'),
        duration: exitDelay,
      ),
    );
    // ⚠️ 必须用 SystemNavigator.pop()（应用商店规范），禁止 exit(0)
    Future.delayed(exitDelay, SystemNavigator.pop);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      key: const ValueKey('privacy_consent_dialog'),
      title: const Text(dialogTitle),
      content: SizedBox(
        width: double.maxFinite,
        child: SingleChildScrollView(
          key: const ValueKey('privacy_consent_body'),
          child: Text(
            bodyText,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.7),
          ),
        ),
      ),
      actions: [
        // 【同意】：唯一进入 App 的方式（无默认选中、无需勾选）
        FilledButton(
          key: const ValueKey('privacy_agree_button'),
          onPressed: onAgreed,
          child: const Text('同意'),
        ),
        // 【拒绝并退出APP】：方案 A
        TextButton(
          key: const ValueKey('privacy_reject_button'),
          onPressed: () => _onReject(context),
          child: const Text('拒绝并退出APP', style: TextStyle(color: AppColors.red)),
        ),
      ],
    );
  }
}

/// 未同意时的整屏容器：只负责把【不可关闭】的同意弹窗弹出来
///
/// 同意前**不渲染任何业务内容**（页面为空），因此不存在任何采集入口。
class PrivacyConsentScreen extends StatefulWidget {
  final VoidCallback onAgreed;

  const PrivacyConsentScreen({super.key, required this.onAgreed});

  @override
  State<PrivacyConsentScreen> createState() => _PrivacyConsentScreenState();
}

class _PrivacyConsentScreenState extends State<PrivacyConsentScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) PrivacyConsentDialog.show(context, onAgreed: widget.onAgreed);
    });
  }

  @override
  Widget build(BuildContext context) {
    // 空屏：同意前不展示、不加载、不请求任何东西
    return const Scaffold(
      body: SizedBox.expand(key: ValueKey('privacy_blank_screen')),
    );
  }
}

/// 同意前/读取本地同意状态时的过渡态（不发任何网络请求）
class PrivacyChecking extends StatelessWidget {
  const PrivacyChecking({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: Padding(
          padding: EdgeInsets.all(AppSpacing.lg),
          child: CircularProgressIndicator(),
        ),
      ),
    );
  }
}
