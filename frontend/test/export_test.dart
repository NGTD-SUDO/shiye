/// T11-A3 / T11-A4 导出入口与章整理缓存 widget 测试
///
/// 全部桩注入（不真连网）；widget 测试处于 fake-async 区**无法完成真实文件 IO**，
/// 因此注入假写入器；「导出内容真落盘」由文件末尾的普通 `test()` 真实读写验证。
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:shiye_app/core/api/api_client.dart';
import 'package:shiye_app/features/pages/page_detail_page.dart';
import 'package:shiye_app/features/subjects/chapter_organize_page.dart';
import 'package:shiye_app/shared/export_flow.dart';

class _StubApiClient extends ApiClient {
  _StubApiClient() : super.forTesting();

  // ---- 单页 ----
  Map<String, dynamic> pageJson = {};
  ExportFile? pageExport;
  Object? pageExportError;
  int pageExportCalls = 0;

  // ---- 整章 ----
  String chapterStructured = '# 整章整理结果';
  Object? organizeError;
  int organizeCalls = 0;
  List<Map<String, dynamic>> chapterPages = [];
  int listPagesCalls = 0;
  ExportFile? chapterExport;
  Object? chapterExportError;
  int chapterExportCalls = 0;

  String? lastFormat;

  @override
  Future<Map<String, dynamic>> getPage(int id) async => pageJson;

  @override
  Future<List<Map<String, dynamic>>> listChapters(int subjectId) async => [];

  @override
  Future<ExportFile> exportPage(int id, {String format = 'md'}) async {
    pageExportCalls++;
    lastFormat = format;
    if (pageExportError != null) throw pageExportError!;
    return pageExport ?? const ExportFile(filename: 'fallback.md', content: 'x');
  }

  @override
  Future<Map<String, dynamic>> organizeChapter(int subjectId, int chapterId) async {
    organizeCalls++;
    if (organizeError != null) throw organizeError!;
    return {
      'chapter_id': chapterId,
      'chapter_name': '第一章',
      'structured_text': chapterStructured,
    };
  }

  @override
  Future<Map<String, dynamic>> listPages({
    int? subjectId,
    int? chapterId,
    String? state,
    int page = 1,
    int size = 50,
  }) async {
    listPagesCalls++;
    return {'items': chapterPages, 'total': chapterPages.length};
  }

  @override
  Future<ExportFile> exportChapter(int subjectId, int chapterId, {String format = 'md'}) async {
    chapterExportCalls++;
    lastFormat = format;
    if (chapterExportError != null) throw chapterExportError!;
    return chapterExport ?? const ExportFile(filename: 'fallback.md', content: 'x');
  }
}

/// 假写入器：不碰真实文件系统（widget 测试无法完成真实 IO），只返回路径句柄
Future<File> _fakeWriter(ExportFile file) async => File(
      '${Directory.systemTemp.path}${Platform.pathSeparator}${safeExportFilename(file.filename)}',
    );

Map<String, dynamic> _pageJson({String ocr = '原始识别文本', String? structured}) => {
      'id': 1,
      'subject_id': 1,
      'subject_name': '数学',
      'chapter_id': null,
      'chapter_name': null,
      'title': '导数定义',
      'image_key': '1/a.jpg',
      'thumb_key': null,
      // 空 URL → RemoteNoteImage 走空态占位（测试里不发网络请求）
      'image_url': '',
      'thumb_url': null,
      'width': 100,
      'height': 200,
      'ocr_text': ocr,
      'ocr_state': 'done',
      'ocr_error': null,
      'ocr_conf': 0.98,
      'structured_text': structured,
      'page_no': null,
      'created_at': '2026-09-18T00:00:00Z',
      'updated_at': null,
    };

void _tall(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

/// 推进若干帧（对话框/异步流程需要多帧）
Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 8; i++) {
    await tester.pump(const Duration(milliseconds: 120));
  }
}

Future<void> _pumpPageDetail(WidgetTester tester, _StubApiClient stub) async {
  _tall(tester);
  await tester.pumpWidget(
    MaterialApp(home: PageDetailPage(pageId: 1, api: stub, exportWriter: _fakeWriter)),
  );
  await tester.pump();
  await tester.pump();
}

Future<void> _pumpChapter(WidgetTester tester, _StubApiClient stub) async {
  _tall(tester);
  await tester.pumpWidget(
    MaterialApp(
      home: ChapterOrganizePage(
        subjectId: 1,
        chapterId: 2,
        chapterName: '第一章',
        api: stub,
        exportWriter: _fakeWriter,
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

IconButton _exportButton(WidgetTester tester) =>
    tester.widget<IconButton>(find.byKey(const ValueKey('export_button')));

/// 清掉 SnackBar 的自动关闭 Timer
Future<void> _drainSnackBar(WidgetTester tester) async {
  await tester.pump(const Duration(seconds: 5));
  await tester.pump();
}

void main() {
  // ==================== 单页导出 ====================

  testWidgets('单页-已有整理稿：可选格式，导出成功后展示后端真实文件名', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient()
      ..pageJson = _pageJson(structured: '# 整理稿')
      ..pageExport = const ExportFile(
        filename: '数学-导数定义.md',
        content: '# 整理稿\n\n正文内容',
      );
    await _pumpPageDetail(tester, stub);

    expect(_exportButton(tester).onPressed, isNotNull);
    await tester.tap(find.byKey(const ValueKey('export_button')));
    await _settle(tester);

    expect(find.byKey(const ValueKey('export_dialog')), findsOneWidget);
    // 已有整理稿 → 不应出现「尚未 AI 整理」提示
    expect(find.textContaining('尚未 AI 整理'), findsNothing);
    expect(stub.pageExportCalls, 0, reason: '选格式之前不得调用导出接口');

    await tester.tap(find.byKey(const ValueKey('export_format_md')));
    await _settle(tester);

    expect(stub.pageExportCalls, 1);
    expect(stub.lastFormat, 'md');
    expect(find.byKey(const ValueKey('export_result_dialog')), findsOneWidget);
    expect(find.text('文件：数学-导数定义.md'), findsOneWidget);

    await tester.tap(find.text('完成'));
    await _settle(tester);
  });

  testWidgets('单页-只有原文：先提示「尚未 AI 整理，将导出原始识别文本」，确认后才导出', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient()..pageJson = _pageJson(structured: null);
    await _pumpPageDetail(tester, stub);

    await tester.tap(find.byKey(const ValueKey('export_button')));
    await _settle(tester);

    expect(find.text('尚未 AI 整理，将导出原始识别文本'), findsOneWidget);
    expect(stub.pageExportCalls, 0);

    await tester.tap(find.byKey(const ValueKey('export_format_txt')));
    await _settle(tester);

    expect(stub.pageExportCalls, 1);
    expect(stub.lastFormat, 'txt');
  });

  testWidgets('单页-原文与整理稿都空：入口禁用，且不调用导出接口', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient()..pageJson = _pageJson(ocr: '', structured: '');
    await _pumpPageDetail(tester, stub);

    expect(_exportButton(tester).onPressed, isNull, reason: '无文本时入口必须禁用');
    expect(find.byTooltip('没有可导出的文本'), findsOneWidget);
    expect(stub.pageExportCalls, 0, reason: '空文本时绝不调用导出接口');
  });

  testWidgets('单页-导出失败：显示后端中文文案，且不出现成功对话框', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient()
      ..pageJson = _pageJson(structured: '# 整理稿')
      ..pageExportError = ApiException('该页没有可导出的文本');
    await _pumpPageDetail(tester, stub);

    await tester.tap(find.byKey(const ValueKey('export_button')));
    await _settle(tester);
    await tester.tap(find.byKey(const ValueKey('export_format_md')));
    await _settle(tester);

    expect(stub.pageExportCalls, 1);
    expect(find.textContaining('该页没有可导出的文本'), findsWidgets);
    expect(find.byKey(const ValueKey('export_result_dialog')), findsNothing);
    await _drainSnackBar(tester);
  });

  // ==================== 整章导出 ====================

  testWidgets('整章-混合来源：先提示「本稿含 1 页 AI 整理 + 1 页原始识别」再导出', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient()
      ..chapterStructured = '# 整章'
      ..chapterPages = [
        {'structured_text': '# 整理过的页', 'ocr_text': '原文一'},
        {'structured_text': null, 'ocr_text': '原文二'},
      ]
      ..chapterExport = const ExportFile(
        filename: '立体几何-第一章.md',
        content: '> 本稿含 1 页 AI 整理 + 1 页原始识别\n\n## 第 1 页 · 甲\n\n# 整理过的页',
      );
    await _pumpChapter(tester, stub);

    expect(stub.listPagesCalls, greaterThanOrEqualTo(1));
    expect(_exportButton(tester).onPressed, isNotNull);

    await tester.tap(find.byKey(const ValueKey('export_button')));
    await _settle(tester);

    expect(find.text('本稿含 1 页 AI 整理 + 1 页原始识别'), findsOneWidget);
    expect(stub.chapterExportCalls, 0);

    await tester.tap(find.byKey(const ValueKey('export_format_md')));
    await _settle(tester);

    expect(stub.chapterExportCalls, 1);
    expect(find.byKey(const ValueKey('export_result_dialog')), findsOneWidget);
    expect(find.text('文件：立体几何-第一章.md'), findsOneWidget);
  });

  testWidgets('整章-全部未整理：提示「本稿全部为原始识别文本，未经 AI 整理」', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient()
      ..chapterPages = [
        {'structured_text': '', 'ocr_text': '原文一'},
        {'structured_text': null, 'ocr_text': '原文二'},
      ];
    await _pumpChapter(tester, stub);

    await tester.tap(find.byKey(const ValueKey('export_button')));
    await _settle(tester);

    expect(find.text('本稿全部为原始识别文本，未经 AI 整理'), findsOneWidget);
  });

  testWidgets('整章-章内页都没有文本：入口禁用，且不调用导出接口', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient()
      ..chapterPages = [
        {'structured_text': '', 'ocr_text': ''},
      ];
    await _pumpChapter(tester, stub);

    expect(_exportButton(tester).onPressed, isNull);
    expect(stub.chapterExportCalls, 0, reason: '空文本时绝不调用导出接口');
  });

  testWidgets('整章-有页无文本：提示里注明「未包含」的页数', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient()
      ..chapterPages = [
        {'structured_text': '# 整理过的页', 'ocr_text': '原文一'},
        {'structured_text': '', 'ocr_text': ''},
      ];
    await _pumpChapter(tester, stub);

    await tester.tap(find.byKey(const ValueKey('export_button')));
    await _settle(tester);

    expect(find.text('本稿仅包含有内容的页（另有 1 页无文本，未包含）'), findsOneWidget);
  });

  // ==================== T11-A4 章整理缓存 ====================

  testWidgets('章整理缓存：二次进入不重复调用 AI，「重新整理」才刷新', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient()..chapterStructured = '# 第一次整理';

    await _pumpChapter(tester, stub);
    expect(stub.organizeCalls, 1);
    expect(find.byKey(const ValueKey('chapter_cache_hint')), findsNothing);

    // 卸载后重新进入（同一个 SharedPreferences 内存桩 → 应命中缓存）
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
    await _pumpChapter(tester, stub);

    expect(stub.organizeCalls, 1, reason: '命中缓存时不得再次调用 AI');
    expect(find.byKey(const ValueKey('chapter_cache_hint')), findsOneWidget);
    expect(find.textContaining('已使用本地缓存的整理结果'), findsOneWidget);

    // 「重新整理」→ 强制刷新并覆盖缓存
    await tester.tap(find.byTooltip('重新整理'));
    await tester.pump();
    await tester.pump();

    expect(stub.organizeCalls, 2, reason: '重新整理必须真的再调一次 AI');
    expect(find.byKey(const ValueKey('chapter_cache_hint')), findsNothing);
  });

  // ==================== 真实落盘（普通 test：可真做 IO） ====================

  test('导出内容真实落盘：文件存在、路径含中文文件名、内容逐字一致', () async {
    const file = ExportFile(filename: '数学-第3页.md', content: '# 标题\n\n正文内容\n');
    final saved = await writeExportFile(file);

    expect(saved.existsSync(), isTrue);
    expect(saved.path.contains('数学-第3页.md'), isTrue);
    expect(await saved.readAsString(), '# 标题\n\n正文内容\n');
    expect(file.byteLength, greaterThan(0));

    saved.parent.deleteSync(recursive: true); // 清理临时目录
  });

  test('导出文件名兜底清理：不产生路径分隔符', () {
    expect(safeExportFilename('../../etc/passwd'), '.._.._etc_passwd');
    expect(safeExportFilename('a/b\\c:d.md'), 'a_b_c_d.md');
    expect(safeExportFilename(''), 'export.txt');
  });
}
