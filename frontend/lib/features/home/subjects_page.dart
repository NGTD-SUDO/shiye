/// 首页 tab — 学科列表
library;

import 'package:flutter/material.dart';
import '../../core/api/api_client.dart';
import '../../core/models/subject.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../shared/widgets/motion.dart';
import '../../shared/widgets/subject_card.dart';
import '../pages/page_upload_page.dart';
import '../subjects/subject_detail_page.dart';
import '../subjects/subject_edit_page.dart';
import 'search_page.dart';

class SubjectsPage extends StatefulWidget {
  /// 测试注入用；生产用单例 [ApiClient()]
  final ApiClient? api;

  const SubjectsPage({super.key, this.api});

  @override
  State<SubjectsPage> createState() => _SubjectsPageState();
}

class _SubjectsPageState extends State<SubjectsPage> {
  late final ApiClient _api = widget.api ?? ApiClient();
  List<Subject> _subjects = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  /// 拉取学科列表。[silent] 为 true 时不进入整页骨架态（静默刷新，不闪骨架）。
  /// 返回是否成功，供调用方决定是否提示「已刷新」。
  Future<bool> _load({bool silent = false}) async {
    if (!silent) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final list = await _api.listSubjects();
      setState(() {
        _subjects = list.map((j) => Subject.fromJson(j)).toList();
        _loading = false;
        _error = null;
      });
      return true;
    } catch (e) {
      // T4-3：走统一异常→中文文案映射
      setState(() {
        _error = mapExceptionToMessage(e);
        _loading = false;
      });
      return false;
    }
  }

  int get _totalPages => _subjects.fold(0, (s, x) => s + x.pageCount);
  int get _totalDone => _subjects.fold(0, (s, x) => s + x.doneCount);

  Future<void> _openSubject(Subject s) async {
    final refresh = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => SubjectDetailPage(subject: s, api: _api)),
    );
    if (refresh == true) _load();
  }

  Future<void> _showSubjectActions(Subject s) async {
    final action = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: AppColors.cardBackground,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.edit_rounded),
              title: const Text('重命名 / 改色'),
              onTap: () => Navigator.pop(ctx, 'edit'),
            ),
            ListTile(
              leading: const Icon(Icons.delete_outline_rounded, color: AppColors.red),
              title: const Text('删除', style: TextStyle(color: AppColors.red)),
              onTap: () => Navigator.pop(ctx, 'delete'),
            ),
          ],
        ),
      ),
    );
    if (!mounted) return;
    if (action == 'edit') {
      await _editSubject(s);
    } else if (action == 'delete') {
      await _deleteSubject(s);
    }
  }

  Future<void> _newSubject() async {
    final refresh = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => SubjectEditPage(subject: null, api: _api),
    );
    if (refresh == true) _load();
  }

  Future<void> _editSubject(Subject s) async {
    final refresh = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => SubjectEditPage(subject: s, api: _api),
    );
    if (refresh == true) _load();
  }

  Future<void> _deleteSubject(Subject s) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除学科'),
        content: Text('确定删除「${s.name}」？该学科下所有笔记页将一并删除，且不可恢复。'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('删除', style: TextStyle(color: AppColors.red)),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await _api.deleteSubject(s.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('已删除')));
      }
      _load();
    } catch (e) {
      if (mounted) {
        // T4-3：走统一异常→中文文案映射
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('删除失败：${mapExceptionToMessage(e)}')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              SliverToBoxAdapter(child: _buildHeader()),
              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.md)),
              SliverToBoxAdapter(child: _buildStats()),
              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.md)),
              SliverToBoxAdapter(child: _buildSearchBox()),
              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.lg)),
              if (_loading && _subjects.isEmpty)
                const SliverFillRemaining(
                  hasScrollBody: false,
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_error != null)
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: _ErrorView(message: _error!, onRetry: _load),
                )
              else if (_subjects.isEmpty)
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: _EmptyView(onCreate: _newSubject),
                )
              else
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.lg,
                    0,
                    AppSpacing.lg,
                    AppSpacing.xxl,
                  ),
                  sliver: SliverGrid(
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      mainAxisSpacing: AppSpacing.md,
                      crossAxisSpacing: AppSpacing.md,
                      childAspectRatio: 1.05,
                    ),
                    delegate: SliverChildBuilderDelegate(
                      (ctx, i) {
                        // §3.7 卡片交错入场（逐项 +50ms 错峰）
                        if (i == _subjects.length) {
                          return StaggeredIn(index: i, child: _NewSubjectCard(onTap: _newSubject));
                        }
                        final s = _subjects[i];
                        return StaggeredIn(
                          index: i,
                          child: SubjectCard(
                            subject: s,
                            onTap: () => _openSubject(s),
                            onLongPress: () => _showSubjectActions(s),
                          ),
                        );
                      },
                      childCount: _subjects.length + 1,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.lg,
        AppSpacing.lg,
        0,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Text('我的笔记', style: Theme.of(context).textTheme.displayLarge),
          ),
          // §3.5：右侧操作用主色
          IconButton(
            tooltip: '编辑',
            icon: const Icon(Icons.edit_rounded, size: 22, color: AppColors.primary),
            onPressed: () async {
              // T8-2：静默刷新（不闪骨架），仅成功时提示「已刷新」；失败由错误态表达
              final ok = await _load(silent: true);
              if (!mounted || !ok) return;
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('已刷新学科列表')),
              );
            },
          ),
          // T13-3：拍照主入口（原底部栏中央按钮移除后迁到首页右上角，对齐 demo 的「＋ 拍照」）
          TextButton(
            onPressed: _openUpload,
            style: TextButton.styleFrom(
              foregroundColor: AppColors.primary,
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
              minimumSize: Size.zero,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: const Text('＋ 拍照', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
          ),
        ],
      ),
    );
  }

  /// §3.3 统计条：3 个等宽卡片（科目 / 笔记页 / 已识别）。
  ///
  /// 数据**全部来自真实数据源**（`listSubjects()` 返回的学科列表）：
  /// 科目数 = 列表长度；笔记页 = 各学科 pageCount 之和；已识别 = 各学科 doneCount 之和。
  /// 无编造。原页头副标题「X 页 · 已完成 Y · Z 学科」与本条完全同源，故由统计条取代（避免重复）。
  Widget _buildStats() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
      child: Row(
        children: [
          _StatCard(value: '${_subjects.length}', label: '科目'),
          const SizedBox(width: 9),
          _StatCard(value: '$_totalPages', label: '笔记页'),
          const SizedBox(width: 9),
          _StatCard(value: '$_totalDone', label: '已识别'),
        ],
      ),
    );
  }

  Widget _buildSearchBox() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
      child: TextField(
        // T8-1：从「死框」（enabled:false）改为可点击入口；外观（hint/图标/间距）不变
        readOnly: true,
        onTap: _openSearch,
        decoration: InputDecoration(
          hintText: '搜索学科',
          prefixIcon: const Icon(Icons.search, size: 20),
          suffixIcon: const Icon(Icons.mic_none_rounded, size: 20),
          hintStyle: TextStyle(color: AppColors.inkTertiary.withValues(alpha: 0.7)),
        ),
      ),
    );
  }

  /// 跳转已有搜索页（T8-1）
  void _openSearch() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const SearchPage()),
    );
  }

  /// T13-3：拍照主入口 —— 原底部栏中央按钮移除后迁到首页右上角（不动 tab，仅 push）。
  /// 行为与旧 `HomePage._goUpload` 完全一致：`PageUploadPage(subjectId: null)`。
  Future<void> _openUpload() async {
    await Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const PageUploadPage(subjectId: null)),
    );
  }
}

/// §3.3 统计条单卡（等宽）：数字 21px bold + 标签 11px inkTertiary，底 = cardBackground，圆角 11
class _StatCard extends StatelessWidget {
  final String value;
  final String label;

  const _StatCard({required this.value, required this.label});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.cardBackground,
          borderRadius: BorderRadius.circular(11),
        ),
        child: Column(
          children: [
            Text(
              value,
              style: const TextStyle(
                fontSize: 21,
                fontWeight: FontWeight.w700,
                color: AppColors.ink,
              ),
            ),
            const SizedBox(height: 3),
            Text(
              label,
              style: const TextStyle(fontSize: 11, color: AppColors.inkTertiary),
            ),
          ],
        ),
      ),
    );
  }
}

/// 新建学科虚线卡片
class _NewSubjectCard extends StatelessWidget {
  final VoidCallback onTap;
  const _NewSubjectCard({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.card),
        child: Container(
          decoration: BoxDecoration(
            color: AppColors.paperWarm.withValues(alpha: 0.6),
            borderRadius: BorderRadius.circular(AppRadius.card),
            border: Border.all(
              color: AppColors.paperLine,
              width: 1.2,
              style: BorderStyle.solid,
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.add_rounded, size: 28, color: AppColors.inkTertiary),
              const SizedBox(height: 4),
              Text(
                '新建学科',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppColors.inkTertiary,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _EmptyView extends StatelessWidget {
  final VoidCallback onCreate;
  const _EmptyView({required this.onCreate});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.xxl),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 96,
            height: 96,
            decoration: BoxDecoration(
              color: AppColors.primaryBg,
              borderRadius: BorderRadius.circular(24),
            ),
            child: const Icon(
              Icons.menu_book_rounded,
              size: 48,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(height: AppSpacing.xl),
          Text(
            '还没有学科',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            '新建一个学科，开始整理你的手写笔记',
            style: Theme.of(context).textTheme.bodySmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.xl),
          FilledButton.icon(
            onPressed: onCreate,
            icon: const Icon(Icons.add_rounded),
            label: const Text('新建学科'),
          ),
        ],
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.cloud_off_rounded, size: 48, color: AppColors.inkTertiary),
        const SizedBox(height: AppSpacing.md),
        Text('加载失败', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: AppSpacing.xs),
        Text(message, style: Theme.of(context).textTheme.bodySmall, textAlign: TextAlign.center),
        const SizedBox(height: AppSpacing.lg),
        OutlinedButton(onPressed: onRetry, child: const Text('重试')),
      ],
    );
  }
}
