/// 页详情 — 大图 + OCR 文本（可编辑/重试）+ 删除/移章
library;

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../../core/api/api_client.dart';
import '../../core/models/chapter.dart';
import '../../core/models/note_page.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../shared/export_flow.dart';
import '../../shared/widgets/remote_note_image.dart';

class PageDetailPage extends StatefulWidget {
  final int pageId;

  /// 测试注入用；生产用单例 [ApiClient()]
  final ApiClient? api;

  /// 测试注入用写入器；生产为 null（走 [writeExportFile] 真实落盘）
  final ExportWriter? exportWriter;

  const PageDetailPage({super.key, required this.pageId, this.api, this.exportWriter});

  @override
  State<PageDetailPage> createState() => _PageDetailPageState();
}

class _PageDetailPageState extends State<PageDetailPage> {
  late final ApiClient _api = widget.api ?? ApiClient();
  NotePage? _page;
  List<Chapter> _chapters = [];
  bool _loading = true;
  String? _error;

  bool _editing = false;
  bool _saving = false;
  int _tabIndex = 0; // 0=原文, 1=整理后
  bool _organizing = false;
  bool _exporting = false; // T11-A3：导出中禁用入口，避免重复触发
  bool _structuredEditing = false;
  late final TextEditingController _ocrCtrl;
  late final TextEditingController _structuredCtrl;
  late final TextEditingController _titleCtrl;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _ocrCtrl = TextEditingController();
    _structuredCtrl = TextEditingController();
    _titleCtrl = TextEditingController();
    _load();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _ocrCtrl.dispose();
    _titleCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await _api.getPage(widget.pageId);
      final page = NotePage.fromJson(data, ApiClient.baseUrl);
      _page = page;
      _ocrCtrl.text = page.ocrText;
      _titleCtrl.text = page.title;
      // 拉取该学科的章
      try {
        final chaps = await _api.listChapters(page.subjectId);
        _chapters = chaps.map((j) => Chapter.fromJson(j)).toList();
      } catch (_) {
        // 章列表失败不阻断主流程
      }
      setState(() => _loading = false);
      // 处理中则启动轮询
      if (page.isProcessing) _startPolling();
    } catch (e) {
      // T4-3：走统一异常→中文文案映射
      setState(() {
        _error = mapExceptionToMessage(e);
        _loading = false;
      });
    }
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) async {
      try {
        final data = await _api.getPage(widget.pageId);
        final page = NotePage.fromJson(data, ApiClient.baseUrl);
        if (!mounted) {
          _pollTimer?.cancel();
          return;
        }
        setState(() => _page = page);
        _ocrCtrl.text = page.ocrText;
        _structuredCtrl.text = page.structuredText ?? '';
        _titleCtrl.text = page.title;
        if (!page.isProcessing) {
          _pollTimer?.cancel();
        }
      } catch (_) {
        // 网络瞬时错误，忽略继续轮询
      }
    });
  }

  Future<void> _reocr() async {
    try {
      await _api.reocrPage(widget.pageId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('已重新发起识别')),
        );
      }
      _load();
      _startPolling();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('重试失败：${mapExceptionToMessage(e)}')),
        );
      }
    }
  }

  Future<void> _saveOcrText() async {
    if (_page == null) return;
    setState(() => _saving = true);
    try {
      await _api.updatePage(_page!.id, ocrText: _ocrCtrl.text);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('已保存')),
        );
        setState(() => _editing = false);
      }
      _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('保存失败：${mapExceptionToMessage(e)}')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _organizePage() async {
    if (_page == null) return;
    setState(() => _organizing = true);
    try {
      final data = await _api.organizePage(_page!.id);
      final page = NotePage.fromJson(data, ApiClient.baseUrl);
      if (!mounted) return;
      setState(() {
        _page = page;
        _structuredCtrl.text = page.structuredText ?? '';
        _tabIndex = 1;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('AI 整理完成')),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('整理失败：${mapExceptionToMessage(e)}')),
        );
      }
    } finally {
      if (mounted) setState(() => _organizing = false);
    }
  }

  Future<void> _saveStructuredText() async {
    if (_page == null) return;
    try {
      await _api.updatePage(_page!.id, structuredText: _structuredCtrl.text);
      if (mounted) {
        setState(() {
          _structuredEditing = false;
          _page = _page!.copyWith(structuredText: _structuredCtrl.text);
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('已保存')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('保存失败：${mapExceptionToMessage(e)}')),
        );
      }
    }
  }

  Future<void> _saveTitle() async {
    if (_page == null) return;
    final title = _titleCtrl.text.trim();
    if (title.isEmpty || title == _page!.title) return;
    try {
      await _api.updatePage(_page!.id, title: title);
      setState(() => _page = NotePage(
        id: _page!.id,
        subjectId: _page!.subjectId,
        subjectName: _page!.subjectName,
        chapterId: _page!.chapterId,
        chapterName: _page!.chapterName,
        title: title,
        imageKey: _page!.imageKey,
        thumbKey: _page!.thumbKey,
        imageUrl: _page!.imageUrl,
        thumbUrl: _page!.thumbUrl,
        width: _page!.width,
        height: _page!.height,
        ocrText: _page!.ocrText,
        ocrState: _page!.ocrState,
        ocrError: _page!.ocrError,
        ocrConf: _page!.ocrConf,
        pageNo: _page!.pageNo,
        createdAt: _page!.createdAt,
        updatedAt: _page!.updatedAt,
      ));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('保存失败：${mapExceptionToMessage(e)}')),
        );
      }
    }
  }

  Future<void> _changeChapter(Chapter? c) async {
    if (_page == null) return;
    try {
      await _api.updatePage(
        _page!.id,
        chapterId: c?.id,
      );
      setState(() => _page = NotePage(
        id: _page!.id,
        subjectId: _page!.subjectId,
        subjectName: _page!.subjectName,
        chapterId: c?.id,
        chapterName: c?.name,
        title: _page!.title,
        imageKey: _page!.imageKey,
        thumbKey: _page!.thumbKey,
        imageUrl: _page!.imageUrl,
        thumbUrl: _page!.thumbUrl,
        width: _page!.width,
        height: _page!.height,
        ocrText: _page!.ocrText,
        ocrState: _page!.ocrState,
        ocrError: _page!.ocrError,
        ocrConf: _page!.ocrConf,
        pageNo: _page!.pageNo,
        createdAt: _page!.createdAt,
        updatedAt: _page!.updatedAt,
      ));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(c == null ? '已移出章节' : '已移至「${c.name}」')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('移章失败：${mapExceptionToMessage(e)}')),
        );
      }
    }
  }

  Future<void> _delete() async {
    if (_page == null) return;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除笔记页'),
        content: const Text('删除后无法恢复，确定继续吗？'),
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
      await _api.deletePage(_page!.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('已删除')));
        Navigator.pop(context, true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('删除失败：${mapExceptionToMessage(e)}')),
        );
      }
    }
  }

  // ===== T11-A3：导出（状态判断 → 用户确认 → 真调后端 → 真实落盘）=====

  bool get _hasStructured => (_page?.structuredText ?? '').trim().isNotEmpty;

  bool get _hasRaw => (_page?.ocrText ?? '').trim().isNotEmpty;

  /// 原文与整理稿都为空 → 无内容可导出（入口禁用）
  bool get _canExport => _page != null && (_hasStructured || _hasRaw);

  Future<void> _export() async {
    final page = _page;
    if (page == null) return;
    if (!_canExport) {
      // 前端前置校验：**不调用导出接口**（任务书要求「空文本时不调用导出接口」）
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('该页没有可导出的文本（原文与 AI 整理稿都为空）')),
      );
      return;
    }

    // 状态判断：尚未整理时明确告知，让用户确认后再导
    final warnings = <String>[
      if (!_hasStructured && _hasRaw) '尚未 AI 整理，将导出原始识别文本',
    ];
    final format = await showExportDialog(context, title: '导出笔记页', warnings: warnings);
    if (format == null || !mounted) return;

    setState(() => _exporting = true);
    try {
      final file = await _api.exportPage(page.id, format: format);
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('笔记页'),
        actions: [
          if (_page != null)
            IconButton(
              key: const ValueKey('export_button'),
              tooltip: _canExport ? '导出' : '没有可导出的文本',
              icon: const Icon(Icons.ios_share_rounded),
              onPressed: (_canExport && !_exporting) ? _export : null,
            ),
          if (_page != null)
            IconButton(
              tooltip: '删除',
              icon: const Icon(Icons.delete_outline_rounded, color: AppColors.red),
              onPressed: _delete,
            ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null || _page == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cloud_off_rounded, size: 48, color: AppColors.inkTertiary),
            const SizedBox(height: AppSpacing.md),
            Text(_error ?? '加载失败', style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: AppSpacing.lg),
            OutlinedButton(onPressed: _load, child: const Text('重试')),
          ],
        ),
      );
    }
    final page = _page!;
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        0,
        AppSpacing.lg,
        AppSpacing.xxl,
      ),
      children: [
        // 大图（统一组件 + 缩放交互；签名 URL 自带凭据，无需 Authorization）
        AspectRatio(
          aspectRatio: page.width != null && page.height != null
              ? (page.width! / page.height!)
              : 0.75,
          child: RemoteNoteImage(
            url: page.imageUrl,
            fit: BoxFit.contain,
            radius: AppRadius.card,
            enableZoom: true,
            onExpired: _load,
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        _buildTextSection(),
        const SizedBox(height: AppSpacing.lg),
        _buildMetaSection(),
      ],
    );
  }

  Widget _buildTextSection() {
    final page = _page!;
    if (page.isProcessing) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Row(
            children: [
              const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.primary),
              ),
              const SizedBox(width: AppSpacing.md),
              Text('正在识别…', style: Theme.of(context).textTheme.bodyMedium),
            ],
          ),
        ),
      );
    }
    if (page.isFailed) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.error_outline_rounded, color: AppColors.red, size: 18),
                  const SizedBox(width: AppSpacing.sm),
                  Text('识别失败', style: Theme.of(context).textTheme.titleMedium?.copyWith(color: AppColors.red)),
                ],
              ),
              if (page.ocrError != null) ...[
                const SizedBox(height: AppSpacing.xs),
                Text(page.ocrError!, style: Theme.of(context).textTheme.bodySmall),
              ],
              const SizedBox(height: AppSpacing.md),
              OutlinedButton.icon(
                onPressed: _reocr,
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: const Text('重试识别'),
                style: OutlinedButton.styleFrom(foregroundColor: AppColors.primary),
              ),
            ],
          ),
        ),
      );
    }
    // done
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(child: _tabButton('📝 原文', 0)),
              Expanded(child: _tabButton('✨ 整理后', 1)),
            ],
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: _tabIndex == 0 ? _buildOriginalView() : _buildStructuredView(),
          ),
        ],
      ),
    );
  }

  Widget _tabButton(String label, int index) {
    final selected = _tabIndex == index;
    return InkWell(
      onTap: () => setState(() => _tabIndex = index),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: selected ? AppColors.primary : Colors.transparent,
              width: 2,
            ),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? AppColors.primary : AppColors.inkTertiary,
            fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
          ),
        ),
      ),
    );
  }

  Widget _buildOriginalView() {
    final page = _page!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.check_circle_outline_rounded, color: AppColors.primary, size: 18),
            const SizedBox(width: AppSpacing.sm),
            Text('识别文本', style: Theme.of(context).textTheme.titleMedium),
            const Spacer(),
            if (!_editing)
              TextButton.icon(
                onPressed: () => setState(() => _editing = true),
                icon: const Icon(Icons.edit_rounded, size: 16),
                label: const Text('编辑'),
              ),
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        if (_editing)
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(
                controller: _ocrCtrl,
                maxLines: 10,
                minLines: 4,
                decoration: const InputDecoration(hintText: '编辑识别后的文本'),
              ),
              const SizedBox(height: AppSpacing.sm),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _saving
                        ? null
                        : () {
                            setState(() {
                              _editing = false;
                              _ocrCtrl.text = page.ocrText;
                            });
                          },
                    child: const Text('取消'),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  FilledButton(
                    onPressed: _saving ? null : _saveOcrText,
                    child: _saving
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Text('保存'),
                  ),
                ],
              ),
            ],
          )
        else
          Text(
            page.ocrText.isEmpty ? '（暂无识别文本）' : page.ocrText,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  height: 1.5,
                  color: page.ocrText.isEmpty ? AppColors.inkTertiary : AppColors.ink,
                ),
          ),
      ],
    );
  }

  Widget _buildStructuredView() {
    final page = _page!;
    if (_organizing) {
      return Column(
        children: [
          const SizedBox(height: AppSpacing.lg),
          const CircularProgressIndicator(color: AppColors.primary),
          const SizedBox(height: AppSpacing.md),
          Text('AI 正在整理笔记…', style: Theme.of(context).textTheme.bodyMedium),
          const SizedBox(height: AppSpacing.lg),
        ],
      );
    }
    final text = page.structuredText;
    if (text == null || text.isEmpty) {
      return Column(
        children: [
          const SizedBox(height: AppSpacing.lg),
          const Icon(Icons.auto_awesome_outlined, size: 48, color: AppColors.inkTertiary),
          const SizedBox(height: AppSpacing.md),
          Text(
            '点击下方按钮，AI 帮你整理笔记',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.inkTertiary),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.lg),
          FilledButton.icon(
            onPressed: _organizePage,
            icon: const Icon(Icons.auto_awesome_rounded, size: 18),
            label: const Text('AI 整理笔记'),
          ),
          const SizedBox(height: AppSpacing.lg),
        ],
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.auto_awesome_rounded, color: AppColors.primary, size: 18),
            const SizedBox(width: AppSpacing.sm),
            Text('整理后', style: Theme.of(context).textTheme.titleMedium),
            const Spacer(),
            TextButton.icon(
              onPressed: _organizePage,
              icon: const Icon(Icons.refresh_rounded, size: 16),
              label: const Text('重新整理'),
            ),
            if (!_structuredEditing)
              TextButton.icon(
                onPressed: () => setState(() => _structuredEditing = true),
                icon: const Icon(Icons.edit_rounded, size: 16),
                label: const Text('编辑'),
              ),
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        if (_structuredEditing)
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(
                controller: _structuredCtrl,
                maxLines: 15,
                minLines: 6,
                decoration: const InputDecoration(hintText: '编辑整理后的 Markdown'),
              ),
              const SizedBox(height: AppSpacing.sm),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () {
                      setState(() {
                        _structuredEditing = false;
                        _structuredCtrl.text = page.structuredText ?? '';
                      });
                    },
                    child: const Text('取消'),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  FilledButton(
                    onPressed: _saveStructuredText,
                    child: const Text('保存'),
                  ),
                ],
              ),
            ],
          )
        else
          MarkdownBody(
            data: text,
            styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
              h1: Theme.of(context).textTheme.headlineSmall?.copyWith(color: AppColors.primary, fontWeight: FontWeight.bold),
              h2: Theme.of(context).textTheme.titleLarge?.copyWith(color: AppColors.primary),
              h3: Theme.of(context).textTheme.titleMedium?.copyWith(color: AppColors.primary),
              p: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.6),
              listBullet: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
      ],
    );
  }

  Widget _buildMetaSection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('标题', style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: AppSpacing.xs),
            TextField(
              controller: _titleCtrl,
              decoration: const InputDecoration(hintText: '输入页标题'),
              onSubmitted: (_) => _saveTitle(),
            ),
            const SizedBox(height: AppSpacing.lg),
            Text('所属章节', style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: AppSpacing.xs),
            DropdownButtonFormField<Chapter?>(
              initialValue: _chapters.where((c) => c.id == _page?.chapterId).isEmpty
                  ? null
                  : _chapters.firstWhere(
                      (c) => c.id == _page?.chapterId,
                      orElse: () => _chapters.first,
                    ),
              decoration: const InputDecoration(hintText: '选择章节'),
              items: [
                const DropdownMenuItem<Chapter?>(value: null, child: Text('未分配')),
                ..._chapters.map((c) => DropdownMenuItem<Chapter?>(value: c, child: Text(c.name))),
              ],
              onChanged: _changeChapter,
            ),
            if (_page?.chapterName != null) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                '当前：${_page!.chapterName}',
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
