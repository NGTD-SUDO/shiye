/// 导出流程（T11-A3）：格式选择 → 真实落盘 → 结果展示
///
/// 硬性要求（任务书 T11-A3）：
/// - 导出前**必须**做状态判断，不许静默、不许假装成功
/// - **真拿到文件才提示成功**（落盘用 `dart:io`，导出的是后端真实产出）
/// - 失败提示由调用方走 `mapExceptionToMessage`（本文件不吞异常）
/// - **零新依赖**：落盘 `dart:io`、复制 `flutter/services` 的 Clipboard
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show Clipboard, ClipboardData;

import '../core/api/api_client.dart';
import '../core/theme/app_colors.dart';

/// 文件名兜底清理（防路径穿越：服务端文件名不参与目录拼接）
String safeExportFilename(String name) {
  final cleaned = name.replaceAll(RegExp(r'[\\/:*?"<>|]'), '_').trim();
  return cleaned.isEmpty ? 'export.txt' : cleaned;
}

/// 导出文件写入器：默认 [writeExportFile]（**真实落盘**）
///
/// 之所以做成可注入：widget 测试跑在 fake-async 区，**真实文件 IO 不会完成**，
/// 因此测试注入桩；生产环境一律使用默认的真实写入器。
typedef ExportWriter = Future<File> Function(ExportFile file);

/// 把导出内容**真实写入**临时目录，返回落盘后的文件对象（可被测试直接调用验证「真文件」）
Future<File> writeExportFile(ExportFile file) async {
  final dir = await Directory.systemTemp.createTemp('shiye_export_');
  final target = File('${dir.path}${Platform.pathSeparator}${safeExportFilename(file.filename)}');
  await target.writeAsString(file.content, flush: true);
  return target;
}

/// 导出格式选择对话框（含状态提示）；返回 `'md'` / `'txt'`，取消返回 `null`
///
/// [warnings] 非空时先展示提示（如「尚未 AI 整理，将导出原始识别文本」），用户确认后才选格式。
Future<String?> showExportDialog(
  BuildContext context, {
  required String title,
  List<String> warnings = const [],
}) {
  return showDialog<String>(
    context: context,
    builder: (ctx) => AlertDialog(
      key: const ValueKey('export_dialog'),
      title: Text(title),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final w in warnings)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // T13-2：写死的浅橙 → 功能色令牌
                  const Icon(Icons.info_outline_rounded, size: 16, color: AppColors.orange),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      w,
                      key: const ValueKey('export_warning'),
                      style: const TextStyle(fontSize: 12.5, height: 1.5),
                    ),
                  ),
                ],
              ),
            ),
          if (warnings.isNotEmpty) const SizedBox(height: 2),
          const Text('选择导出格式：', style: TextStyle(fontSize: 12.5)),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
        TextButton(
          key: const ValueKey('export_format_txt'),
          onPressed: () => Navigator.pop(ctx, 'txt'),
          child: const Text('纯文本 (.txt)'),
        ),
        FilledButton(
          key: const ValueKey('export_format_md'),
          onPressed: () => Navigator.pop(ctx, 'md'),
          child: const Text('Markdown (.md)'),
        ),
      ],
    ),
  );
}

/// 落盘并展示结果（**落盘成功才提示成功**）
///
/// 结果对话框展示：文件名、真实保存路径、字节数、内容预览，并提供「复制全文」。
/// [writer] 缺省为真实落盘 [writeExportFile]。
Future<void> saveAndShowExportResult(
  BuildContext context, {
  required ExportFile file,
  required String format,
  ExportWriter? writer,
}) async {
  final saved = await (writer ?? writeExportFile)(file);
  if (!context.mounted) return;
  final preview = file.content.split('\n').take(10).join('\n');
  final formatLabel = format == 'md' ? 'Markdown' : '纯文本';
  await showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      key: const ValueKey('export_result_dialog'),
      title: const Text('导出成功'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '文件：${file.filename}',
              key: const ValueKey('export_result_filename'),
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 6),
            Text(
              '已保存到本地：${saved.path}',
              key: const ValueKey('export_result_path'),
              style: const TextStyle(fontSize: 11.5, height: 1.5),
            ),
            const SizedBox(height: 4),
            Text('大小：${file.byteLength} 字节', style: const TextStyle(fontSize: 11.5)),
            const SizedBox(height: 12),
            Text('内容预览（$formatLabel）', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
            const SizedBox(height: 6),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                // T13-2：原写死的浅绿底 → 卡片色（深色下对话框上的"抬升块"）
                color: AppColors.cardBackground,
                borderRadius: BorderRadius.circular(8),
              ),
              child: SelectableText(
                preview.isEmpty ? '（空内容）' : preview,
                style: const TextStyle(fontSize: 11.5, height: 1.55),
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton.icon(
          key: const ValueKey('export_copy_button'),
          onPressed: () async {
            await Clipboard.setData(ClipboardData(text: file.content));
            if (ctx.mounted) {
              ScaffoldMessenger.of(ctx).showSnackBar(const SnackBar(content: Text('已复制全文')));
            }
          },
          icon: const Icon(Icons.copy_rounded, size: 16),
          label: const Text('复制全文'),
        ),
        FilledButton(onPressed: () => Navigator.pop(ctx), child: const Text('完成')),
      ],
    ),
  );
}
