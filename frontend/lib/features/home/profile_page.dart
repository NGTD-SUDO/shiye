/// 个人页 — 用户信息 + 设置项
///
/// T4 改造：
/// - 已登录时昵称区域可点按弹出编辑对话框（[updateMe]）
/// - 校验：去空格、非空、长度上限 20（任务书要求，后端 UpdateMeRequest 上限 100）
/// - 成功后用 [updateMe] 返回的昵称刷新界面（不臆造）
/// - 未登录时不显示编辑入口
/// - 错误文案走 [mapExceptionToMessage] 统一映射
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/api/api_client.dart';
import '../../core/auth_provider.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../legal/legal_doc_page.dart';
import '../study/study_report_page.dart';

class ProfilePage extends StatefulWidget {
  /// 测试注入用；生产用单例 [ApiClient()]
  final ApiClient? api;

  const ProfilePage({super.key, this.api});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  late final ApiClient _api = widget.api ?? ApiClient();
  Map<String, dynamic>? _me;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadMe();
  }

  Future<void> _loadMe() async {
    try {
      final data = await _api.getMe();
      setState(() {
        _me = data;
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(mapExceptionToMessage(e))),
        );
      }
    }
  }

  String _formatDate(String? iso) {
    if (iso == null || iso.isEmpty) return '—';
    try {
      final dt = DateTime.parse(iso).toLocal();
      return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
    } catch (_) {
      return iso;
    }
  }

  Future<void> _logout() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('退出登录'),
        content: const Text('确定要退出当前账号吗？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('退出', style: TextStyle(color: AppColors.red)),
          ),
        ],
      ),
    );
    if (ok != true) return;
    if (!mounted) return;
    final auth = Provider.of<AuthProvider>(context, listen: false);
    await auth.logout();
  }

  /// 改昵称对话框（T4-5）：用 updateMe 真实落库 + 用返回值刷新界面
  Future<void> _editNickname() async {
    final current = (_me?['nickname'] as String?) ?? '';
    // 在 await 之前取 Provider，避免跨 async gap 用 BuildContext；
    // dialog 的 ctx 不在原 Provider 树内，必须用外层 context 取。
    final auth = Provider.of<AuthProvider>(context, listen: false);
    final ctrl = TextEditingController(text: current);
    bool saving = false;
    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) {
          return AlertDialog(
            title: const Text('修改昵称'),
            content: TextField(
              controller: ctrl,
              autofocus: true,
              decoration: const InputDecoration(
                hintText: '请输入新昵称（1~20 字）',
                border: OutlineInputBorder(),
              ),
              maxLength: 20,
            ),
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.pop(ctx, false),
                child: const Text('取消'),
              ),
              FilledButton(
                onPressed: saving
                    ? null
                    : () async {
                        final name = ctrl.text.trim();
                        if (name.isEmpty) {
                          ScaffoldMessenger.of(ctx).showSnackBar(
                            const SnackBar(content: Text('昵称不能为空')),
                          );
                          return;
                        }
                        if (name.length > 20) {
                          ScaffoldMessenger.of(ctx).showSnackBar(
                            const SnackBar(content: Text('昵称最长 20 字')),
                          );
                          return;
                        }
                        if (name == current) {
                          Navigator.pop(ctx, true);
                          return;
                        }
                        setS(() => saving = true);
                        try {
                          final data = await _api.updateMe(nickname: name);
                          if (ctx.mounted) {
                            // 用 updateMe 返回的真实昵称刷新界面（不臆造）
                            final newNick = data['nickname'] as String? ?? name;
                            setState(() => _me = data);
                            // 同步 AuthProvider 缓存，让所有依赖 nickname 的界面都刷新
                            auth.setNickname(newNick);
                            ScaffoldMessenger.of(ctx).showSnackBar(
                              const SnackBar(content: Text('已保存')),
                            );
                            Navigator.pop(ctx, true);
                          }
                        } catch (e) {
                          if (ctx.mounted) {
                            ScaffoldMessenger.of(ctx).showSnackBar(
                              SnackBar(content: Text(mapExceptionToMessage(e))),
                            );
                          }
                        } finally {
                          if (ctx.mounted) setS(() => saving = false);
                        }
                      },
                child: saving
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Text('保存'),
              ),
            ],
          );
        },
      ),
    );
    if (result == true && mounted) {
      // 已在对话框内 setState 更新 _me，这里无需额外操作
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final isLoggedIn = auth.isLoggedIn;
    final nickname = auth.nickname ?? _me?['nickname'] as String? ?? '未登录';
    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _loadMe,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.lg,
              AppSpacing.lg,
              AppSpacing.lg,
              AppSpacing.xxl,
            ),
            children: [
              // 用户卡片
              Card(
                child: InkWell(
                  borderRadius: BorderRadius.circular(AppRadius.card),
                  onTap: isLoggedIn ? _editNickname : null,
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpacing.lg),
                    child: Row(
                      children: [
                        Container(
                          width: 64,
                          height: 64,
                          decoration: const BoxDecoration(
                            color: AppColors.primaryBg,
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            Icons.person_rounded,
                            size: 36,
                            color: AppColors.primary,
                          ),
                        ),
                        const SizedBox(width: AppSpacing.lg),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                nickname,
                                style: Theme.of(context).textTheme.titleLarge,
                              ),
                              const SizedBox(height: 2),
                              if (_loading)
                                const SizedBox(
                                  width: 14,
                                  height: 14,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              else
                                Text(
                                  '注册于 ${_formatDate(_me?['created_at'] as String?)}',
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                              if (isLoggedIn)
                                Padding(
                                  padding: const EdgeInsets.only(top: 2),
                                  child: Text(
                                    '点击修改昵称',
                                    style: Theme.of(context).textTheme.labelSmall,
                                  ),
                                ),
                            ],
                          ),
                        ),
                        if (isLoggedIn)
                          const Icon(Icons.chevron_right_rounded, color: AppColors.inkTertiary),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              // 设置项
              _SectionTitle(title: '设置'),
              const SizedBox(height: AppSpacing.sm),
              Card(
                child: Column(
                  children: [
                    ListTile(
                      leading: const Icon(Icons.insights_rounded),
                      title: const Text('学情分析'),
                      trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.inkTertiary),
                      onTap: () => _openStudyReport(),
                    ),
                    const Divider(height: 1, indent: AppSpacing.lg + 4),
                    ListTile(
                      leading: const Icon(Icons.info_outline_rounded),
                      title: const Text('关于拾页'),
                      trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.inkTertiary),
                      onTap: () => _showAbout(context),
                    ),
                    const Divider(height: 1, indent: AppSpacing.lg + 4),
                    ListTile(
                      leading: const Icon(Icons.dns_outlined),
                      title: const Text('服务器地址'),
                      subtitle: Text(
                        ApiClient.baseUrl,
                        style: Theme.of(context).textTheme.labelSmall,
                      ),
                      trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.inkTertiary),
                      onTap: () => _showServerInfo(context),
                    ),
                    // T12-4：法律文档入口（4 项）。路径核算：主页 → 我的 → 隐私政策 = 3 次点击（≤4）
                    const Divider(height: 1, indent: AppSpacing.lg + 4),
                    ListTile(
                      key: const ValueKey('entry_privacy_policy'),
                      leading: const Icon(Icons.privacy_tip_outlined),
                      title: const Text('隐私政策'),
                      trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.inkTertiary),
                      onTap: () => _openLegal(const PrivacyPolicyPage()),
                    ),
                    const Divider(height: 1, indent: AppSpacing.lg + 4),
                    ListTile(
                      key: const ValueKey('entry_user_agreement'),
                      leading: const Icon(Icons.description_outlined),
                      title: const Text('用户协议'),
                      trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.inkTertiary),
                      onTap: () => _openLegal(const UserAgreementPage()),
                    ),
                    const Divider(height: 1, indent: AppSpacing.lg + 4),
                    ListTile(
                      key: const ValueKey('entry_third_party'),
                      leading: const Icon(Icons.handshake_outlined),
                      title: const Text('第三方信息共享清单'),
                      trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.inkTertiary),
                      onTap: () => _openLegal(const ThirdPartyListPage()),
                    ),
                    const Divider(height: 1, indent: AppSpacing.lg + 4),
                    ListTile(
                      key: const ValueKey('entry_data_collection'),
                      leading: const Icon(Icons.fact_check_outlined),
                      title: const Text('个人信息收集清单'),
                      trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.inkTertiary),
                      onTap: () => _openLegal(const DataCollectionListPage()),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              // 登出 / 注销
              _SectionTitle(title: '账号'),
              const SizedBox(height: AppSpacing.sm),
              Card(
                child: Column(
                  children: [
                    ListTile(
                      key: const ValueKey('delete_account_entry'),
                      leading: const Icon(Icons.person_remove_alt_1_outlined, color: AppColors.red),
                      title: const Text('注销账号', style: TextStyle(color: AppColors.red)),
                      trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.inkTertiary),
                      onTap: _deleteAccount,
                    ),
                    const Divider(height: 1, indent: AppSpacing.lg + 4),
                    ListTile(
                      leading: const Icon(Icons.logout_rounded, color: AppColors.red),
                      title: const Text('退出登录', style: TextStyle(color: AppColors.red)),
                      onTap: _logout,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.xxl),
              Center(
                child: Text(
                  '拾页 · v1.0.0',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// 学情分析入口（T5）：进入全学科总览学情分析页
  void _openStudyReport() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const StudyReportPage()),
    );
  }

  /// 打开法律文档页（T12-4）
  void _openLegal(Widget page) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => page));
  }

  /// 注销账号（T12-6）
  ///
  /// 二次确认（文案含「此操作不可恢复」）→ 真调 `DELETE /auth/me`（后端删库 + **物理删图**）
  /// → 成功后清除本地 token → AppRouter 回到登录页。
  Future<void> _deleteAccount() async {
    final messenger = ScaffoldMessenger.of(context);
    final auth = Provider.of<AuthProvider>(context, listen: false);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        key: const ValueKey('delete_account_confirm_dialog'),
        title: const Text('注销账号'),
        content: const Text(
          '注销后，你的账号、全部学科、章节、笔记记录与图片文件将被永久删除，'
          '此操作不可恢复。\n\n确定要注销吗？',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(
            key: const ValueKey('delete_account_confirm_button'),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('确认注销', style: TextStyle(color: AppColors.red)),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await _api.deleteMe();
    } catch (e) {
      // 失败如实报错（并明确"未删除"），不谎报成功
      messenger.showSnackBar(
        SnackBar(content: Text('注销失败：${mapExceptionToMessage(e)}')),
      );
      return;
    }
    await auth.logout(); // 清本地 token → 触发路由回登录页
    messenger.showSnackBar(const SnackBar(content: Text('账号已注销')));
  }

  void _showAbout(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('关于拾页'),
        content: const Text(
          '拾页 · 手写笔记拍照数字化整理 App\n\n'
          '将纸质笔记拍照上传，自动 OCR 识别文字，便于检索与校对。',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('知道了')),
        ],
      ),
    );
  }

  void _showServerInfo(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('服务器地址'),
        content: SelectableText(ApiClient.baseUrl),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('关闭')),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  const _SectionTitle({required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: AppSpacing.sm),
      child: Text(
        title,
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
              fontWeight: FontWeight.w600,
              color: AppColors.inkTertiary,
            ),
      ),
    );
  }
}
