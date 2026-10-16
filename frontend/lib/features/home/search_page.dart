/// 搜索页 — iOS 风搜索 + 结果列表
library;

import 'dart:async';
import 'package:flutter/material.dart';
import '../../core/api/api_client.dart';
import '../../core/models/search_result.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../shared/widgets/motion.dart';
import '../../shared/widgets/remote_note_image.dart';
import '../pages/page_detail_page.dart';

class SearchPage extends StatefulWidget {
  const SearchPage({super.key});

  @override
  State<SearchPage> createState() => _SearchPageState();
}

class _SearchPageState extends State<SearchPage> {
  final _api = ApiClient();
  final _ctrl = TextEditingController();
  final _focus = FocusNode();
  Timer? _debounce;

  List<SearchResult> _results = [];
  bool _loading = false;
  bool _searched = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _ctrl.addListener(_onChanged);
    // 自动聚焦
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _focus.requestFocus();
    });
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _ctrl.removeListener(_onChanged);
    _ctrl.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _onChanged() {
    _debounce?.cancel();
    final q = _ctrl.text.trim();
    if (q.isEmpty) {
      setState(() {
        _searched = false;
        _results = [];
      });
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 400), () => _search(q));
  }

  Future<void> _search(String q) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await _api.search(q);
      final items = (data['items'] as List).cast<Map<String, dynamic>>();
      setState(() {
        _results = items.map((j) => SearchResult.fromJson(j, ApiClient.baseUrl)).toList();
        _loading = false;
        _searched = true;
      });
    } catch (e) {
      // T4-3：走统一异常→中文文案映射
      setState(() {
        _error = mapExceptionToMessage(e);
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _buildSearchBox(),
            Expanded(child: _buildBody()),
          ],
        ),
      ),
    );
  }

  Widget _buildSearchBox() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.lg,
        AppSpacing.lg,
        AppSpacing.md,
      ),
      child: TextField(
        controller: _ctrl,
        focusNode: _focus,
        textInputAction: TextInputAction.search,
        onSubmitted: (v) {
          _debounce?.cancel();
          final q = v.trim();
          if (q.isNotEmpty) _search(q);
        },
        decoration: InputDecoration(
          hintText: '搜索笔记内容',
          prefixIcon: const Icon(Icons.search_rounded, size: 20),
          suffixIcon: _ctrl.text.isNotEmpty
              ? IconButton(
                  icon: const Icon(Icons.clear_rounded, size: 18),
                  onPressed: () {
                    _ctrl.clear();
                    setState(() {
                      _searched = false;
                      _results = [];
                    });
                  },
                )
              : null,
          filled: true,
          // 深色下输入框填充 = 白 12%（对齐 demo 的 --fill）
          fillColor: AppColors.paperFold,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppRadius.button),
            borderSide: BorderSide.none,
          ),
          contentPadding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.md,
          ),
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return _StatusView(
        icon: Icons.cloud_off_rounded,
        title: '搜索失败',
        detail: _error!,
        actionLabel: '重试',
        onAction: () => _search(_ctrl.text.trim()),
      );
    }
    if (!_searched) {
      return _StatusView(
        icon: Icons.search_rounded,
        title: '搜索笔记内容',
        detail: '输入关键词，可在 OCR 文本中查找',
      );
    }
    if (_results.isEmpty) {
      return _StatusView(
        icon: Icons.search_off_rounded,
        title: '未找到相关笔记',
        detail: '换个关键词试试',
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        0,
        AppSpacing.lg,
        AppSpacing.xxl,
      ),
      itemCount: _results.length,
      separatorBuilder: (_, _) => const SizedBox(height: AppSpacing.md),
      // §3.7 结果卡片交错入场（逐项 +55ms，对齐 demo）+ 按压缩放
      itemBuilder: (ctx, i) => StaggeredIn(
        index: i,
        stepMs: 55,
        child: PressableScale(
          child: _ResultTile(
            result: _results[i],
            query: _ctrl.text.trim(),
            onExpired: () => _search(_ctrl.text.trim()),
            onTap: () async {
              final refresh = await Navigator.push<bool>(
                context,
                MaterialPageRoute(builder: (_) => PageDetailPage(pageId: _results[i].pageId)),
              );
              if (refresh == true) _search(_ctrl.text.trim());
            },
          ),
        ),
      ),
    );
  }
}

class _ResultTile extends StatelessWidget {
  final SearchResult result;
  final String query;
  final VoidCallback onTap;
  final VoidCallback? onExpired;
  const _ResultTile({required this.result, required this.query, required this.onTap, this.onExpired});

  /// 高亮 snippet 中匹配 query 的部分
  List<TextSpan> _highlight(BuildContext context) {
    final snippet = result.snippet.isEmpty ? '（无文本片段）' : result.snippet;
    if (query.isEmpty) return [TextSpan(text: snippet)];
    final spans = <TextSpan>[];
    var start = 0;
    final lowerSnippet = snippet.toLowerCase();
    final lowerQuery = query.toLowerCase();
    while (true) {
      final idx = lowerSnippet.indexOf(lowerQuery, start);
      if (idx < 0) {
        spans.add(TextSpan(text: snippet.substring(start)));
        break;
      }
      if (idx > start) {
        spans.add(TextSpan(text: snippet.substring(start, idx)));
      }
      spans.add(TextSpan(
        text: snippet.substring(idx, idx + query.length),
        // §3.4 关键词高亮：主色 .28 底色 + 亮字（对齐 demo `mark`）
        style: TextStyle(
          color: AppColors.ink,
          fontWeight: FontWeight.w600,
          backgroundColor: AppColors.primary.withValues(alpha: .28),
        ),
      ));
      start = idx + query.length;
    }
    return spans;
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.card),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 缩略图（统一组件，失败可重试，空态独立）
              SizedBox(
                width: 56,
                height: 56,
                child: RemoteNoteImage(
                  url: result.thumbUrl,
                  fit: BoxFit.cover,
                  radius: AppRadius.sm,
                  isThumb: true,
                  onExpired: onExpired,
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              // 文本
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            result.title.isEmpty ? '未命名' : result.title,
                            style: Theme.of(context).textTheme.titleMedium,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        _OcrStateDot(state: result.ocrState),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      result.subjectName,
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    // snippet 高亮
                    Text.rich(
                      TextSpan(
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              height: 1.4,
                              color: AppColors.inkSecondary,
                            ),
                        children: _highlight(context),
                      ),
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

}

class _OcrStateDot extends StatelessWidget {
  final String state;
  const _OcrStateDot({required this.state});

  @override
  Widget build(BuildContext context) {
    final color = switch (state) {
      'done' => AppColors.primary,
      'failed' => AppColors.red,
      'processing' || 'pending' => AppColors.inkTertiary,
      _ => AppColors.inkTertiary,
    };
    return Container(
      width: 8,
      height: 8,
      margin: const EdgeInsets.only(left: AppSpacing.sm),
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

class _StatusView extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? detail;
  final String? actionLabel;
  final VoidCallback? onAction;
  const _StatusView({
    required this.icon,
    required this.title,
    this.detail,
    this.actionLabel,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 48, color: AppColors.inkTertiary),
            const SizedBox(height: AppSpacing.md),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            if (detail != null) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                detail!,
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
            if (onAction != null && actionLabel != null) ...[
              const SizedBox(height: AppSpacing.lg),
              OutlinedButton(onPressed: onAction, child: Text(actionLabel!)),
            ],
          ],
        ),
      ),
    );
  }
}
