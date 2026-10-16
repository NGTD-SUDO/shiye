/// 学科编辑/新建 — 底部弹窗
library;

import 'package:flutter/material.dart';
import '../../core/api/api_client.dart';
import '../../core/models/subject.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';

class SubjectEditPage extends StatefulWidget {
  /// null 表示新建；非空表示编辑
  final Subject? subject;
  /// 测试注入用；生产用单例 [ApiClient()]
  final ApiClient? api;

  const SubjectEditPage({super.key, required this.subject, this.api});

  @override
  State<SubjectEditPage> createState() => _SubjectEditPageState();
}

class _SubjectEditPageState extends State<SubjectEditPage> {
  /// T13-3：科目调色板换成 **iOS 系统色系**（与蓝色主题协调），**保留"多色可选"**
  /// （科目靠颜色区分）。默认色 = 第一项 `#007AFF`（主题蓝）。
  static const List<String> _palette = [
    '#007AFF', // 蓝 systemBlue
    '#30D158', // 绿 systemGreen
    '#FF9F0A', // 橙 systemOrange
    '#FF453A', // 红 systemRed
    '#BF5AF2', // 紫 systemPurple
    '#5AC8FA', // 青 systemTeal
  ];

  late final ApiClient _api = widget.api ?? ApiClient();
  late final TextEditingController _nameCtrl;
  late String _color;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _nameCtrl = TextEditingController(text: widget.subject?.name ?? '');
    _color = widget.subject?.color ?? _palette.first;
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    super.dispose();
  }

  Color _hexToColor(String hex) {
    final v = int.tryParse(hex.substring(1), radix: 16);
    return v != null ? Color(v) : AppColors.primary;
  }

  Future<void> _save() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请输入学科名称')),
      );
      return;
    }
    setState(() => _saving = true);
    try {
      if (widget.subject == null) {
        await _api.createSubject(name, color: _color);
      } else {
        await _api.updateSubject(
          widget.subject!.id,
          name: name,
          color: _color,
        );
      }
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      // T4-3：走统一异常→中文文案映射
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('保存失败：${mapExceptionToMessage(e)}')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.subject != null;
    // 适配键盘
    final inset = MediaQuery.of(context).viewInsets.bottom;
    return AnimatedPadding(
      duration: const Duration(milliseconds: 200),
      padding: EdgeInsets.only(bottom: inset),
      child: Container(
        decoration: const BoxDecoration(
          color: AppColors.cardBackground,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.lg,
          AppSpacing.sm,
          AppSpacing.lg,
          AppSpacing.xxl,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 抓手
            Center(
              child: Container(
                width: 36,
                height: 4,
                margin: const EdgeInsets.only(top: AppSpacing.xs, bottom: AppSpacing.md),
                decoration: BoxDecoration(
                  color: AppColors.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            Text(
              isEdit ? '编辑学科' : '新建学科',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: AppSpacing.lg),
            TextField(
              controller: _nameCtrl,
              autofocus: !isEdit,
              textInputAction: TextInputAction.done,
              decoration: const InputDecoration(
                labelText: '学科名称',
                hintText: '如：数学、英语、物理',
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            // 颜色选择
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                '主题色',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.md,
              runSpacing: AppSpacing.md,
              children: _palette.map((hex) {
                final selected = hex == _color;
                return GestureDetector(
                  onTap: () => setState(() => _color = hex),
                  child: Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: _hexToColor(hex),
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: selected ? AppColors.ink : Colors.transparent,
                        width: 3,
                      ),
                      boxShadow: selected
                          ? [
                              BoxShadow(
                                color: _hexToColor(hex).withValues(alpha: 0.3),
                                blurRadius: 6,
                                spreadRadius: 1,
                              )
                            ]
                          : null,
                    ),
                    child: selected
                        ? const Icon(Icons.check, color: Colors.white, size: 20)
                        : null,
                  ),
                );
              }).toList(),
            ),
            const SizedBox(height: AppSpacing.xxl),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _saving ? null : () => Navigator.pop(context, false),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(AppRadius.button),
                      ),
                    ),
                    child: const Text('取消'),
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: FilledButton(
                    onPressed: _saving ? null : _save,
                    style: FilledButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(AppRadius.button),
                      ),
                    ),
                    child: _saving
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : Text(isEdit ? '保存' : '创建'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
