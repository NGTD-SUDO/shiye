/// 学科详情页 — 笔记页列表 + 章筛选 + 上传 FAB + 章管理
///
/// T4 改造：
/// - AppBar 加「章管理」入口（弹窗列章、新建、删除）
/// - 章删除前二次确认，文案按后端真实语义（章内页保留并归入「未分章」）
/// - 错误文案走 [mapExceptionToMessage] 统一映射
library;

import 'package:flutter/material.dart';
import '../../core/api/api_client.dart';
import '../../core/models/chapter.dart';
import '../../core/models/note_page.dart';
import '../../core/models/subject.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../pages/page_detail_page.dart';
import '../pages/page_upload_page.dart';
import '../study/study_report_page.dart';
import '../../shared/widgets/remote_note_image.dart';
import 'chapter_organize_page.dart';

class SubjectDetailPage extends StatefulWidget {
  final Subject subject;
  /// 测试注入用；生产用单例 [ApiClient()]
  final ApiClient? api;

  const SubjectDetailPage({super.key, required this.subject, this.api});

  @override
  State<SubjectDetailPage> createState() => _SubjectDetailPageState();
}

class _SubjectDetailPageState extends State<SubjectDetailPage> {
  late final ApiClient _api = widget.api ?? ApiClient();
  List<Chapter> _chapters = [];
  Chapter? _selectedChapter;
  List<NotePage> _pages = [];
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
      final chaps = await _api.listChapters(widget.subject.id);
      final pagesData = await _api.listPages(
        subjectId: widget.subject.id,
        chapterId: _selectedChapter?.id,
        size: 200,
      );
      final items = (pagesData['items'] as List).cast<Map<String, dynamic>>();
      setState(() {
        _chapters = chaps.map((j) => Chapter.fromJson(j)).toList();
        _pages = items.map((j) => NotePage.fromJson(j, ApiClient.baseUrl)).toList();
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = mapExceptionToMessage(e);
        _loading = false;
      });
    }
  }

  Future<void> _openPage(NotePage p) async {
    final refresh = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => PageDetailPage(pageId: p.id)),
    );
    if (refresh == true) _load();
  }

  Future<void> _upload() async {
    final refresh = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => PageUploadPage(subjectId: widget.subject.id),
      ),
    );
    if (refresh == true) _load();
  }

  /// 章管理弹窗：列出当前学科下的章，支持新建与删除（T4-4）
  Future<void> _openChapterManagement() async {
    await showDialog<void>(
      context: context,
      builder: (ctx) => _ChapterManageDialog(
        subject: widget.subject,
        chapters: _chapters,
        api: _api,
        onChanged: () => _load(),
      ),
    );
  }

  /// 学情分析入口（T5）：进入该学科的学情分析页
  Future<void> _openStudyReport() async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => StudyReportPage(
          subjectId: widget.subject.id,
          subjectName: widget.subject.name,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.subject.name,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (_pages.isNotEmpty)
              Text(
                '${_pages.length} 页',
                style: Theme.of(context).textTheme.labelSmall,
              ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: '学情分析',
            icon: const Icon(Icons.insights_rounded),
            onPressed: _openStudyReport,
          ),
          IconButton(
            tooltip: '章管理',
            icon: const Icon(Icons.bookmarks_outlined),
            onPressed: _openChapterManagement,
          ),
          if (_chapters.isNotEmpty)
            PopupMenuButton<int?>(
              tooltip: '按章节筛选',
              icon: const Icon(Icons.filter_list_rounded),
              onSelected: (v) {
                setState(() {
                  _selectedChapter = v == null
                      ? null
                      : _chapters.firstWhere((c) => c.id == v);
                });
                _load();
              },
              itemBuilder: (ctx) => [
                const PopupMenuItem<int?>(value: null, child: Text('全部章节')),
                ..._chapters.map(
                  (c) => PopupMenuItem<int?>(
                    value: c.id,
                    child: Row(
                      children: [
                        Expanded(child: Text(c.name)),
                        IconButton(
                          icon: const Icon(
                            Icons.auto_awesome_rounded,
                            color: AppColors.primary,
                            size: 20,
                          ),
                          tooltip: 'AI 整章整理',
                          onPressed: () {
                            // 先关闭筛选菜单，再跳转整理页
                            Navigator.pop(ctx);
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) => ChapterOrganizePage(
                                  subjectId: widget.subject.id,
                                  chapterId: c.id,
                                  chapterName: c.name,
                                ),
                              ),
                            );
                          },
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _buildBody(),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _upload,
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        child: const Icon(Icons.photo_camera_rounded),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading && _pages.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return _ErrorView(message: _error!, onRetry: _load);
    }
    if (_pages.isEmpty) {
      return _EmptyView(onUpload: _upload);
    }
    return CustomScrollView(
      slivers: [
        if (_selectedChapter != null)
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.lg,
                AppSpacing.sm,
                AppSpacing.lg,
                AppSpacing.sm,
              ),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.md,
                  vertical: AppSpacing.sm,
                ),
                decoration: BoxDecoration(
                  color: AppColors.primaryBg,
                  borderRadius: BorderRadius.circular(AppRadius.button),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.filter_alt_outlined, size: 16, color: AppColors.primary),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Text(
                        '已筛选：${_selectedChapter!.name}',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: AppColors.primaryDark,
                            ),
                      ),
                    ),
                    GestureDetector(
                      onTap: () {
                        setState(() => _selectedChapter = null);
                        _load();
                      },
                      child: const Icon(Icons.close, size: 16, color: AppColors.primary),
                    ),
                  ],
                ),
              ),
            ),
          ),
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          sliver: SliverGrid(
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              mainAxisSpacing: AppSpacing.md,
              crossAxisSpacing: AppSpacing.md,
              childAspectRatio: 0.72,
            ),
            delegate: SliverChildBuilderDelegate(
              (ctx, i) => _PageTile(page: _pages[i], onTap: () => _openPage(_pages[i]), onExpired: _load),
              childCount: _pages.length,
            ),
          ),
        ),
      ],
    );
  }
}

/// 章管理对话框（T4-4）：列章、新建、删除
class _ChapterManageDialog extends StatefulWidget {
  final Subject subject;
  final List<Chapter> chapters;
  final ApiClient api;
  final VoidCallback onChanged;

  const _ChapterManageDialog({
    required this.subject,
    required this.chapters,
    required this.api,
    required this.onChanged,
  });

  @override
  State<_ChapterManageDialog> createState() => _ChapterManageDialogState();
}

class _ChapterManageDialogState extends State<_ChapterManageDialog> {
  late List<Chapter> _list;
  final _nameCtrl = TextEditingController();
  bool _creating = false;

  @override
  void initState() {
    super.initState();
    _list = List.of(widget.chapters);
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('章名不能为空')),
      );
      return;
    }
    if (name.length > 50) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('章名最长 50 字')),
      );
      return;
    }
    setState(() => _creating = true);
    try {
      final data = await widget.api.createChapter(widget.subject.id, name);
      final ch = Chapter.fromJson(data);
      setState(() {
        _list.add(ch);
        _nameCtrl.clear();
      });
      widget.onChanged();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('已新建章')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(mapExceptionToMessage(e))),
        );
      }
    } finally {
      if (mounted) setState(() => _creating = false);
    }
  }

  Future<void> _delete(Chapter c) async {
    // 删除二次确认：文案按后端真实语义（章内页保留并归入「未分章」）
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('删除章「${c.name}」'),
        content: const Text(
          '删除后章内笔记页会保留并归入「未分章」，但页的章归属会被清空。\n确定删除吗？',
        ),
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
      await widget.api.deleteChapter(widget.subject.id, c.id);
      setState(() => _list.removeWhere((x) => x.id == c.id));
      widget.onChanged();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('已删除章')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(mapExceptionToMessage(e))),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('章管理'),
      content: SizedBox(
        width: double.maxFinite,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // 新建章输入区
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _nameCtrl,
                    decoration: const InputDecoration(
                      isDense: true,
                      hintText: '新章名（1~50 字）',
                      border: OutlineInputBorder(),
                    ),
                    maxLength: 50,
                    onSubmitted: (_) => _creating ? null : _create(),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                FilledButton(
                  onPressed: _creating ? null : _create,
                  child: const Text('新建'),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            // 章列表
            if (_list.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.lg),
                child: Text(
                  '还没有章',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              )
            else
              Flexible(
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: _list.length,
                  itemBuilder: (ctx, i) {
                    final c = _list[i];
                    return ListTile(
                      dense: true,
                      title: Text(c.name),
                      trailing: IconButton(
                        icon: const Icon(Icons.delete_outline, color: AppColors.red),
                        tooltip: '删除',
                        onPressed: () => _delete(c),
                      ),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('关闭'),
        ),
      ],
    );
  }
}

class _PageTile extends StatelessWidget {
  final NotePage page;
  final VoidCallback onTap;
  final VoidCallback? onExpired;
  const _PageTile({required this.page, required this.onTap, this.onExpired});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.card),
        child: Stack(
          children: [
            // 缩略图（用统一组件：失败可重试，空态独立，不再各写一遍）
            RemoteNoteImage(
              url: page.thumbUrl,
              fit: BoxFit.cover,
              radius: AppRadius.card,
              isThumb: true,
              onExpired: onExpired,
            ),
            // 渐变底色 + 标题
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.sm,
                  vertical: AppSpacing.sm + 2,
                ),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Colors.transparent,
                      AppColors.shadow.withValues(alpha: 0.45),
                    ],
                  ),
                  borderRadius: const BorderRadius.vertical(
                    bottom: Radius.circular(AppRadius.card),
                  ),
                ),
                child: Text(
                  page.title.isEmpty ? '未命名' : page.title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
            // OCR 状态角标
            Positioned(
              top: AppSpacing.sm,
              right: AppSpacing.sm,
              child: _OcrStateBadge(state: page.ocrState),
            ),
          ],
        ),
      ),
    );
  }

}

/// OCR 状态角标
class _OcrStateBadge extends StatelessWidget {
  final String state;
  const _OcrStateBadge({required this.state});

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (state) {
      'done' => ('已识别', AppColors.primary),
      'failed' => ('失败', AppColors.red),
      'processing' => ('识别中', AppColors.inkTertiary),
      'pending' => ('待识别', AppColors.inkTertiary),
      _ => ('', AppColors.inkTertiary),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 10,
          fontWeight: FontWeight.w600,
        ),
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
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        const SizedBox(height: 120),
        const Center(
          child: Icon(Icons.cloud_off_rounded, size: 48, color: AppColors.inkTertiary),
        ),
        const SizedBox(height: AppSpacing.md),
        Center(child: Text('加载失败', style: Theme.of(context).textTheme.titleMedium)),
        const SizedBox(height: AppSpacing.xs),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xxl),
          child: Text(
            message,
            style: Theme.of(context).textTheme.bodySmall,
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        Center(child: OutlinedButton(onPressed: onRetry, child: const Text('重试'))),
      ],
    );
  }
}

class _EmptyView extends StatelessWidget {
  final VoidCallback onUpload;
  const _EmptyView({required this.onUpload});

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        const SizedBox(height: 100),
        Center(
          child: Card(
            child: Container(
              width: 260,
              padding: const EdgeInsets.all(AppSpacing.xl),
              child: Column(
                children: [
                  Container(
                    width: 72,
                    height: 72,
                    decoration: BoxDecoration(
                      color: AppColors.primaryBg,
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: const Icon(
                      Icons.photo_camera_rounded,
                      size: 36,
                      color: AppColors.primary,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  Text(
                    '还没有笔记页',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    '点击下方按钮拍照导入',
                    style: Theme.of(context).textTheme.bodySmall,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  FilledButton.icon(
                    onPressed: onUpload,
                    icon: const Icon(Icons.photo_camera_rounded),
                    label: const Text('拍照导入'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}
