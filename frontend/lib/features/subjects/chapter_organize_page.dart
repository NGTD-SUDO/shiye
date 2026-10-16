/// 章级 AI 整理结果页
///
/// T11-A4：整理结果用 SharedPreferences 缓存，**避免每次进页都重烧 AI**（不落库、不改表）；
/// 「重新整理」可强制刷新并覆盖缓存。
/// T11-A3：新增「导出」入口（三态判断 → 混合来源提示 → 真调后端 → 真实落盘）。
library;

import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/api/api_client.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../shared/export_flow.dart';

class ChapterOrganizePage extends StatefulWidget {
  final int subjectId;
  final int chapterId;
  final String chapterName;

  /// 测试注入用；生产用单例 [ApiClient()]
  final ApiClient? api;

  /// 测试注入用写入器；生产为 null（走 [writeExportFile] 真实落盘）
  final ExportWriter? exportWriter;

  const ChapterOrganizePage({
    super.key,
    required this.subjectId,
    required this.chapterId,
    required this.chapterName,
    this.api,
    this.exportWriter,
  });

  @override
  State<ChapterOrganizePage> createState() => _ChapterOrganizePageState();
}

class _ChapterOrganizePageState extends State<ChapterOrganizePage> {
  late final ApiClient _api = widget.api ?? ApiClient();

  String? _structuredText;
  bool _loading = true;
  String? _error;

  /// T11-A4：本次结果是否来自本地缓存（缓存命中时不调用 AI）
  bool _fromCache = false;

  /// T11-A3：导出中禁用入口
  bool _exporting = false;

  /// T11-A3：导出前的页级事实（用于三态判断与「混合来源」提示）；null = 尚未取到
  int? _organizedPages;
  int? _rawPages;
  int? _emptyPages;

  /// 缓存 key（含学科与章 id，避免串页）
  String get _cacheKey => 'shiye_chapter_organize_${widget.subjectId}_${widget.chapterId}';

  @override
  void initState() {
    super.initState();
    _load();
    _loadExportFacts();
  }

  // ===== T11-A4：本地缓存 =====

  Future<String?> _readCache() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_cacheKey);
      return (raw == null || raw.isEmpty) ? null : raw;
    } catch (_) {
      return null;
    }
  }

  Future<void> _writeCache(String text) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_cacheKey, text);
    } catch (_) {
      // 缓存失败不影响主流程
    }
  }

  /// 首屏：优先读缓存（命中即**不调 AI**），无缓存才真正整理
  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _structuredText = null;
      _fromCache = false;
    });
    final cached = await _readCache();
    if (!mounted) return;
    if (cached != null) {
      setState(() {
        _structuredText = cached;
        _loading = false;
        _fromCache = true;
      });
      return;
    }
    await _organize();
  }

  /// 真正调用 AI 整理（「重新整理」也走这里，会覆盖缓存）
  Future<void> _organize() async {
    setState(() {
      _loading = true;
      _error = null;
      _structuredText = null;
      _fromCache = false;
    });
    try {
      final data = await _api.organizeChapter(widget.subjectId, widget.chapterId);
      if (!mounted) return;
      final text = data['structured_text'] as String?;
      setState(() {
        _structuredText = text;
        _loading = false;
      });
      if ((text ?? '').isNotEmpty) {
        await _writeCache(text!);
      }
    } catch (e) {
      // T4-3：走统一异常→中文文案映射
      if (!mounted) return;
      setState(() {
        _error = mapExceptionToMessage(e);
        _loading = false;
      });
    }
  }

  // ===== T11-A3：导出 =====

  /// 拉取章内页清单，算出「已整理 / 仅原始 / 全空」页数（决定入口可用性与提示数字）
  Future<void> _loadExportFacts() async {
    try {
      final data = await _api.listPages(
        subjectId: widget.subjectId,
        chapterId: widget.chapterId,
        size: 200,
      );
      final items = ((data['items'] as List?) ?? const []).cast<Map<String, dynamic>>();
      var organized = 0;
      var raw = 0;
      var empty = 0;
      for (final item in items) {
        final structured = (item['structured_text'] as String?)?.trim() ?? '';
        final ocr = (item['ocr_text'] as String?)?.trim() ?? '';
        if (structured.isNotEmpty) {
          organized++;
        } else if (ocr.isNotEmpty) {
          raw++;
        } else {
          empty++;
        }
      }
      if (!mounted) return;
      setState(() {
        _organizedPages = organized;
        _rawPages = raw;
        _emptyPages = empty;
      });
    } catch (_) {
      // 页清单拿不到不影响导出：由后端做最终判定（错误文案由后端给）
    }
  }

  /// 是否有内容可导出：事实未知时不禁用（交给后端判定）
  bool get _canExport {
    final organized = _organizedPages;
    final raw = _rawPages;
    if (organized == null || raw == null) return true;
    return organized + raw > 0;
  }

  Future<void> _export() async {
    if (!_canExport) {
      // 前端前置校验：**不调用导出接口**
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('该章下没有可导出的文本（章内页都还没有识别或整理内容）')),
      );
      return;
    }

    // 状态判断：把「来源构成」如实告诉用户（与后端写在文件开头的标注同一口径）
    final organized = _organizedPages;
    final raw = _rawPages;
    final skipped = _emptyPages ?? 0;
    final warnings = <String>[];
    if (organized != null && raw != null) {
      final suffix = skipped > 0 ? '（另有 $skipped 页无文本，未包含）' : '';
      if (organized > 0 && raw > 0) {
        warnings.add('本稿含 $organized 页 AI 整理 + $raw 页原始识别$suffix');
      } else if (organized == 0 && raw > 0) {
        warnings.add('本稿全部为原始识别文本，未经 AI 整理$suffix');
      } else if (skipped > 0) {
        // 全是整理稿但仍有页无文本：稿子不完整也要说清楚
        warnings.add('本稿仅包含有内容的页$suffix');
      }
    }

    final format = await showExportDialog(context, title: '导出整章', warnings: warnings);
    if (format == null || !mounted) return;

    setState(() => _exporting = true);
    try {
      final file = await _api.exportChapter(widget.subjectId, widget.chapterId, format: format);
      if (!mounted) return;
      await saveAndShowExportResult(context, file: file, format: format, writer: widget.exportWriter);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('导出失败：${mapExceptionToMessage(e)}')),
      );
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ready = !_loading && _error == null;
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.chapterName} · AI 整理'),
        actions: [
          if (ready)
            IconButton(
              key: const ValueKey('export_button'),
              tooltip: _canExport ? '导出' : '没有可导出的文本',
              icon: const Icon(Icons.ios_share_rounded),
              onPressed: (_canExport && !_exporting) ? _export : null,
            ),
          if (ready)
            IconButton(
              tooltip: '重新整理',
              icon: const Icon(Icons.refresh_rounded),
              onPressed: _exporting ? null : _organize,
            ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const CircularProgressIndicator(color: AppColors.primary),
            const SizedBox(height: AppSpacing.md),
            Text('AI 正在整章整理…', style: Theme.of(context).textTheme.bodyMedium),
          ],
        ),
      );
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline_rounded, size: 48, color: AppColors.red),
            const SizedBox(height: AppSpacing.md),
            Text(_error!, style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: AppSpacing.lg),
            FilledButton.icon(
              onPressed: _organize,
              icon: const Icon(Icons.refresh_rounded, size: 18),
              label: const Text('重试'),
            ),
          ],
        ),
      );
    }
    if (_structuredText == null || _structuredText!.isEmpty) {
      return Center(
        child: Text('暂无整理结果', style: Theme.of(context).textTheme.bodyMedium),
      );
    }
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        if (_fromCache)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.md),
            child: Row(
              children: [
                const Icon(Icons.offline_pin_outlined, size: 16, color: AppColors.inkTertiary),
                const SizedBox(width: AppSpacing.xs),
                Expanded(
                  child: Text(
                    '已使用本地缓存的整理结果（未重复调用 AI）；点右上「重新整理」可刷新',
                    key: const ValueKey('chapter_cache_hint'),
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                ),
              ],
            ),
          ),
        MarkdownBody(
          data: _structuredText!,
          styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
            h1: Theme.of(context).textTheme.headlineSmall?.copyWith(color: AppColors.primary, fontWeight: FontWeight.bold),
            h2: Theme.of(context).textTheme.titleLarge?.copyWith(color: AppColors.primary),
            h3: Theme.of(context).textTheme.titleMedium?.copyWith(color: AppColors.primary),
            p: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.6),
          ),
        ),
      ],
    );
  }
}
