/// 法律文档页（T12-3）：通用渲染页 + 4 份文档入口
///
/// - 4 份文档**内置在 assets/legal/**（离线可见，应用商店审核要求）
/// - 用已装的 `flutter_markdown` 渲染（**不新增依赖**）
/// - 底部「在浏览器中打开」：见 [kLegalWebUrl] 注释（本项目未装 url_launcher，
///   按钮以「复制链接/如实提示」实现，不伪造"能拉起浏览器"的能力）
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show Clipboard, ClipboardData;
import 'package:flutter_markdown/flutter_markdown.dart';

import '../../core/api/api_client.dart';
import '../../core/privacy_service.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';

/// 法律文档在线地址（后端 `GET /legal`，4 份文档合页）。
///
/// **与 API 同源拼接**：`{ApiClient.baseUrl}/legal`。
/// ⚠️ 不要硬编码隧道域名：本项目用 cloudflared 临时隧道，地址随时会变；
/// 同源拼接后无论隧道重启还是换部署环境，地址都跟着 API 走。
/// （`ApiClient.baseUrl` 是 getter，不能在 const 表达式里求值，故用 `final`。）
final String kLegalWebUrl = '${ApiClient.baseUrl}/legal';

/// 通用法律文档页
class LegalDocPage extends StatefulWidget {
  final String title;
  final String assetPath;

  /// 页脚额外内容（例如隐私政策页的「撤回同意」）
  final Widget? footer;

  const LegalDocPage({
    super.key,
    required this.title,
    required this.assetPath,
    this.footer,
  });

  @override
  State<LegalDocPage> createState() => _LegalDocPageState();
}

class _LegalDocPageState extends State<LegalDocPage> {
  String? _content;
  String? _error;
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // 只加载一次；用 DefaultAssetBundle（生产=应用资源包；测试可注入 bundle）
    if (_started) return;
    _started = true;
    _load();
  }

  Future<void> _load() async {
    try {
      final text = await DefaultAssetBundle.of(context).loadString(widget.assetPath);
      if (!mounted) return;
      setState(() => _content = text);
    } catch (e) {
      if (!mounted) return;
      // 如实展示失败原因，不假装有内容
      setState(() => _error = '文档加载失败：$e');
    }
  }

  void _openInBrowser() {
    final messenger = ScaffoldMessenger.of(context);
    if (kLegalWebUrl.isEmpty) {
      messenger.showSnackBar(
        const SnackBar(content: Text('当前未配置在线地址，可在本页查看完整内容')),
      );
      return;
    }
    Clipboard.setData(ClipboardData(text: kLegalWebUrl));
    messenger.showSnackBar(
      const SnackBar(content: Text('链接已复制，请在浏览器中打开')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Text(_error!, style: Theme.of(context).textTheme.bodyMedium),
        ),
      );
    }
    if (_content == null) {
      return const Center(child: CircularProgressIndicator());
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          MarkdownBody(
            data: _content!,
            selectable: true,
            styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
              h1: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: AppColors.primary,
                  ),
              h2: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: AppColors.primary,
                  ),
              h3: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
              p: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.7),
              tableBorder: TableBorder.all(color: AppColors.primaryBg, width: 1),
            ),
            // 文档内的第三方链接：无 url_launcher → 复制链接并如实提示（不假装能打开）
            onTapLink: (text, href, title) {
              if (href == null || href.isEmpty) return;
              Clipboard.setData(ClipboardData(text: href));
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('链接已复制：$href')),
              );
            },
          ),
          const SizedBox(height: AppSpacing.lg),
          if (widget.footer != null) ...[
            widget.footer!,
            const SizedBox(height: AppSpacing.lg),
          ],
          Center(
            child: OutlinedButton.icon(
              onPressed: _openInBrowser,
              icon: const Icon(Icons.open_in_browser_rounded, size: 18),
              label: const Text('在浏览器中打开'),
            ),
          ),
        ],
      ),
    );
  }
}

/// 《隐私政策》页（底部带「撤回同意」）
class PrivacyPolicyPage extends StatelessWidget {
  const PrivacyPolicyPage({super.key});

  @override
  Widget build(BuildContext context) {
    return LegalDocPage(
      title: '隐私政策',
      assetPath: 'assets/legal/privacy_policy.md',
      footer: const _WithdrawConsentButton(),
    );
  }
}

/// 《用户协议》页
class UserAgreementPage extends StatelessWidget {
  const UserAgreementPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const LegalDocPage(
      title: '用户协议',
      assetPath: 'assets/legal/user_agreement.md',
    );
  }
}

/// 《第三方信息共享清单》页
class ThirdPartyListPage extends StatelessWidget {
  const ThirdPartyListPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const LegalDocPage(
      title: '第三方信息共享清单',
      assetPath: 'assets/legal/third_party_sdk.md',
    );
  }
}

/// 《个人信息收集清单》页
class DataCollectionListPage extends StatelessWidget {
  const DataCollectionListPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const LegalDocPage(
      title: '个人信息收集清单',
      assetPath: 'assets/legal/data_collection_list.md',
    );
  }
}

/// 撤回同意（T12-5）：二次确认 → 清除同意标记
class _WithdrawConsentButton extends StatelessWidget {
  const _WithdrawConsentButton();

  Future<void> _withdraw(BuildContext context) async {
    final navigator = Navigator.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        key: const ValueKey('withdraw_confirm_dialog'),
        title: const Text('撤回同意'),
        content: const Text('撤回后需重新同意才能使用拾页'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(
            key: const ValueKey('withdraw_confirm_button'),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('确认撤回', style: TextStyle(color: AppColors.red)),
          ),
        ],
      ),
    );
    if (ok != true) return;

    await PrivacyService.instance.withdraw();
    // 回到根路由：AppRouter 检测到「未同意」会立即重新展示同意弹窗
    navigator.popUntil((r) => r.isFirst);
    messenger.showSnackBar(const SnackBar(content: Text('已撤回同意，请重新阅读并同意后使用')));
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        key: const ValueKey('withdraw_consent_entry'),
        leading: const Icon(Icons.undo_rounded, color: AppColors.red),
        title: const Text('撤回同意', style: TextStyle(color: AppColors.red)),
        subtitle: const Text('撤回后需重新同意才能使用拾页'),
        onTap: () => _withdraw(context),
      ),
    );
  }
}
