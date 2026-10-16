/// 拍照/选图上传 — 单/批量
///
/// T4 改造：
/// - 删除假进度（原单张 0.5、批量 (i+1)/N），改用真实字节进度（[uploadProgress] 纯函数）
/// - 错误文案走 [mapExceptionToMessage] 统一映射，不再拼 `$e`
/// - 上传失败时保留未上传图片，不清空用户已选图
library;

import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/api/api_client.dart';
import '../../core/models/subject.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/upload_progress.dart';

class PageUploadPage extends StatefulWidget {
  /// 预选学科 id（从主页/学科详情进入可传入）
  final int? subjectId;

  const PageUploadPage({super.key, required this.subjectId});

  @override
  State<PageUploadPage> createState() => _PageUploadPageState();
}

class _PageUploadPageState extends State<PageUploadPage> {
  final _api = ApiClient();
  final _picker = ImagePicker();

  final List<File> _picked = [];
  List<Subject> _subjects = [];
  Subject? _selectedSubject;
  bool _loading = true;
  bool _uploading = false;

  /// 进度显示：0~1（来自真实字节统计），null 表示未在上传
  double? _progress;
  /// 当前正在上传第几张（1~N），用于显示「第 i/N 张」真实序号
  int _currentIdx = 0;
  /// 总张数
  int _totalImgs = 0;
  /// 已成功完成的张数（用于缩略图完成标记与失败保留）
  int _completed = 0;

  @override
  void initState() {
    super.initState();
    _loadSubjects();
  }

  Future<void> _loadSubjects() async {
    setState(() => _loading = true);
    try {
      final list = await _api.listSubjects();
      final subjects = list.map((j) => Subject.fromJson(j)).toList();
      Subject? picked;
      if (widget.subjectId != null) {
        final idx = subjects.indexWhere((s) => s.id == widget.subjectId);
        if (idx >= 0) picked = subjects[idx];
      }
      setState(() {
        _subjects = subjects;
        _selectedSubject = picked ?? (subjects.isEmpty ? null : subjects.first);
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

  Future<void> _takePhoto() async {
    try {
      final x = await _picker.pickImage(source: ImageSource.camera, imageQuality: 92);
      if (x != null) {
        setState(() => _picked.add(File(x.path)));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(mapExceptionToMessage(e))),
        );
      }
    }
  }

  Future<void> _pickGallery() async {
    try {
      final xs = await _picker.pickMultiImage(imageQuality: 92);
      if (xs.isNotEmpty) {
        setState(() => _picked.addAll(xs.map((x) => File(x.path))));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(mapExceptionToMessage(e))),
        );
      }
    }
  }

  void _removeAt(int i) {
    setState(() => _picked.removeAt(i));
  }

  /// 逐张上传：每张用真实字节进度回调（T4-2 A 方案）
  /// 失败时立刻停、提示第几张失败、保留剩余未上传图片
  Future<void> _upload() async {
    if (_picked.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请先选择图片')),
      );
      return;
    }
    if (_selectedSubject == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请先选择学科')),
      );
      return;
    }
    setState(() {
      _uploading = true;
      _progress = 0;
      _completed = 0;
      _totalImgs = _picked.length;
      _currentIdx = 1;
    });
    final subjectId = _selectedSubject!.id;
    int failedAt = -1;
    String failedMsg = '';
    try {
      for (var i = 0; i < _picked.length; i++) {
        if (!mounted) return;
        setState(() {
          _currentIdx = i + 1;
          _progress = 0;
        });
        try {
          await _api.uploadPage(
            _picked[i],
            subjectId,
            onProgress: (sent, total) {
              if (mounted) {
                setState(() => _progress = uploadProgress(sent, total));
              }
            },
          );
          if (!mounted) return;
          setState(() {
            _completed = i + 1;
            _progress = 1.0;
          });
        } catch (e) {
          failedAt = i + 1;
          failedMsg = mapExceptionToMessage(e, isUpload: true);
          break;
        }
      }
      if (!mounted) return;
      if (failedAt < 0) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('已上传 ${_picked.length} 张')),
        );
        Navigator.pop(context, true);
      } else {
        // 失败：保留剩余未上传图片（_picked 不动），仅提示第几张失败
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('第 $failedAt 张上传失败：$failedMsg（已保留未上传图片）')),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _uploading = false;
          _progress = null;
          _currentIdx = 0;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('拍照上传'),
        actions: [
          if (_picked.isNotEmpty && !_uploading)
            TextButton(
              onPressed: _picked.clear,
              child: const Text('清空'),
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _subjects.isEmpty
              ? _buildNoSubject()
              : Column(
                  children: [
                    Expanded(child: _buildPreview()),
                    Container(
                      decoration: const BoxDecoration(
                        color: AppColors.cardBackground,
                        border: Border(
                          top: BorderSide(color: AppColors.border, width: 0.5),
                        ),
                      ),
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.lg,
                        AppSpacing.md,
                        AppSpacing.lg,
                        AppSpacing.xxl,
                      ),
                      child: _buildActions(),
                    ),
                  ],
                ),
    );
  }

  Widget _buildNoSubject() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.folder_off_outlined, size: 48, color: AppColors.inkTertiary),
            const SizedBox(height: AppSpacing.md),
            Text('请先创建学科', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: AppSpacing.xs),
            Text(
              '上传笔记页前需要先选择一个学科',
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.lg),
            FilledButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('返回'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPreview() {
    if (_picked.isEmpty) {
      return Center(
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
                Icons.add_a_photo_outlined,
                size: 48,
                color: AppColors.primary,
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            Text(
              '点击下方按钮拍照或选图',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
        ),
      );
    }
    // 缩略图列表
    return GridView.builder(
      padding: const EdgeInsets.all(AppSpacing.lg),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        mainAxisSpacing: AppSpacing.sm,
        crossAxisSpacing: AppSpacing.sm,
      ),
      itemCount: _picked.length,
      itemBuilder: (ctx, i) {
        // 完成标记：按真实已上传张数（i+1 <= _completed 表示这张已完成）
        final done = (i + 1) <= _completed;
        // 等待标记：当前上传序号之后且未完成的
        final waiting = _uploading && !done && (i + 1) > _currentIdx;
        final current = _uploading && (i + 1) == _currentIdx;
        return Stack(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(AppRadius.sm),
              child: Image.file(
                _picked[i],
                width: double.infinity,
                height: double.infinity,
                fit: BoxFit.cover,
              ),
            ),
            if (!_uploading)
              Positioned(
                top: 2,
                right: 2,
                child: GestureDetector(
                  onTap: () => _removeAt(i),
                  child: Container(
                    width: 20,
                    height: 20,
                    decoration: BoxDecoration(
                      // T13-2 §4.2：深色下圆底由"黑 54%"改为"白 30%"（叠在图片上更清晰）
                      color: Colors.white.withValues(alpha: .3),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.close, color: Colors.white, size: 14),
                  ),
                ),
              ),
            if (done)
              Positioned.fill(
                child: Container(
                  color: AppColors.shadow,
                  child: const Center(
                    child: Text('完成', style: TextStyle(color: Colors.white, fontSize: 10)),
                  ),
                ),
              )
            else if (current)
              Positioned.fill(
                child: Container(
                  color: AppColors.shadow,
                  child: Center(
                    child: Text(
                      _progress == null ? '上传中' : '上传中 ${(_progress! * 100).round()}%',
                      style: const TextStyle(color: Colors.white, fontSize: 10),
                    ),
                  ),
                ),
              )
            else if (waiting)
              Positioned.fill(
                child: Container(
                  color: AppColors.shadow,
                  child: const Center(
                    child: Text('等待', style: TextStyle(color: Colors.white, fontSize: 10)),
                  ),
                ),
              ),
          ],
        );
      },
    );
  }

  Widget _buildActions() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // 学科选择器
        Row(
          children: [
            const Icon(Icons.book_outlined, size: 18, color: AppColors.inkTertiary),
            const SizedBox(width: AppSpacing.sm),
            Text('学科', style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: DropdownButtonFormField<Subject?>(
                initialValue: _selectedSubject,
                decoration: const InputDecoration(
                  isDense: true,
                  contentPadding: EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.sm,
                  ),
                ),
                items: _subjects
                    .map((s) => DropdownMenuItem<Subject?>(
                          value: s,
                          child: Text(s.name),
                        ))
                    .toList(),
                onChanged: _uploading
                    ? null
                    : (v) => setState(() => _selectedSubject = v),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        // 操作按钮行
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _uploading ? null : _takePhoto,
                icon: const Icon(Icons.photo_camera_rounded),
                label: const Text('拍照'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(AppRadius.button),
                  ),
                ),
              ),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _uploading ? null : _pickGallery,
                icon: const Icon(Icons.photo_library_outlined),
                label: const Text('相册'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(AppRadius.button),
                  ),
                ),
              ),
            ),
          ],
        ),
        if (_picked.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          FilledButton(
            onPressed: _uploading ? null : _upload,
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(AppRadius.button),
              ),
            ),
            child: _uploading
                ? Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Text(
                        _progress == null
                            ? '上传中…'
                            : '上传中 第 $_currentIdx/$_totalImgs 张 ${(_progress! * 100).round()}%',
                      ),
                    ],
                  )
                : Text('上传 ${_picked.length} 张'),
          ),
        ],
      ],
    );
  }
}
