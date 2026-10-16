/// 学情页 — 占位 + 学科页数统计
library;

import 'package:flutter/material.dart';
import '../../core/api/api_client.dart';
import '../../core/models/subject.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';

class StudyPage extends StatefulWidget {
  const StudyPage({super.key});

  @override
  State<StudyPage> createState() => _StudyPageState();
}

class _StudyPageState extends State<StudyPage> {
  final _api = ApiClient();
  List<Subject> _subjects = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final list = await _api.listSubjects();
      setState(() {
        _subjects = list.map((j) => Subject.fromJson(j)).toList();
        _loading = false;
      });
    } catch (e) {
      // T4-3：走统一异常→中文文案映射，不再拼 `$e`
      setState(() {
        _error = mapExceptionToMessage(e);
        _loading = false;
      });
    }
  }

  int get _total => _subjects.fold(0, (s, x) => s + x.pageCount);
  int get _maxPages => _subjects.fold(0, (s, x) => x.pageCount > s ? x.pageCount : s);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.lg,
              AppSpacing.lg,
              AppSpacing.lg,
              AppSpacing.xxl,
            ),
            children: [
              Text('学情', style: Theme.of(context).textTheme.displayLarge),
              const SizedBox(height: AppSpacing.xs),
              Text(
                '共 $_total 页 · ${_subjects.length} 个学科',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: AppSpacing.lg),
              _buildSoonBanner(),
              const SizedBox(height: AppSpacing.lg),
              if (_loading)
                const Center(
                  child: Padding(
                    padding: EdgeInsets.all(AppSpacing.xxl),
                    child: CircularProgressIndicator(),
                  ),
                )
              else if (_error != null)
                _ErrorView(message: _error!, onRetry: _load)
              else if (_subjects.isEmpty)
                _EmptyView()
              else
                _buildStats(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSoonBanner() {
    return Card(
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppColors.primaryBg,
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(
                Icons.insights_rounded,
                size: 22,
                color: AppColors.primary,
              ),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '学情分析功能即将上线',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '错题统计 / 复习进度 / 知识点掌握',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right_rounded, color: AppColors.inkTertiary),
          ],
        ),
      ),
    );
  }

  Widget _buildStats() {
    final max = _maxPages == 0 ? 1 : _maxPages;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('学科页数统计', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: AppSpacing.md),
            ..._subjects.map((s) {
              final ratio = s.pageCount / max;
              return Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.md),
                child: _Bar(
                  label: s.name,
                  value: s.pageCount,
                  ratio: ratio,
                  color: _hexToColor(s.color),
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  Color _hexToColor(String hex) {
    if (hex.startsWith('#')) {
      final v = int.tryParse(hex.substring(1), radix: 16);
      if (v != null) return Color(v);
    }
    return AppColors.primary;
  }
}

class _Bar extends StatelessWidget {
  final String label;
  final int value;
  final double ratio;
  final Color color;
  const _Bar({required this.label, required this.value, required this.ratio, required this.color});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 60,
          child: Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.inkSecondary),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Stack(
            children: [
              Container(
                height: 10,
                decoration: BoxDecoration(
                  color: AppColors.surfaceMuted,
                  borderRadius: BorderRadius.circular(5),
                ),
              ),
              FractionallySizedBox(
                widthFactor: ratio.clamp(0.02, 1),
                child: Container(
                  height: 10,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(5),
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        SizedBox(
          width: 36,
          child: Align(
            alignment: Alignment.centerRight,
            child: Text(
              '$value',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.inkSecondary,
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
        ),
      ],
    );
  }
}

class _EmptyView extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.xxl),
      child: Column(
        children: [
          const Icon(Icons.folder_open_rounded, size: 48, color: AppColors.inkTertiary),
          const SizedBox(height: AppSpacing.md),
          Text('暂无学科数据', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: AppSpacing.xs),
          Text(
            '创建学科并上传笔记后即可在此查看统计',
            style: Theme.of(context).textTheme.bodySmall,
            textAlign: TextAlign.center,
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
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.xxl),
      child: Column(
        children: [
          const Icon(Icons.cloud_off_rounded, size: 48, color: AppColors.inkTertiary),
          const SizedBox(height: AppSpacing.md),
          Text('加载失败', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: AppSpacing.xs),
          Text(message, style: Theme.of(context).textTheme.bodySmall, textAlign: TextAlign.center),
          const SizedBox(height: AppSpacing.lg),
          OutlinedButton(onPressed: onRetry, child: const Text('重试')),
        ],
      ),
    );
  }
}
