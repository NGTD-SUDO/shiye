/// T8 首页死控件修复 widget 测试
///
/// 用桩 ApiClient（测试内部 mock，不算产品假数据）验证：
/// 1. 点击首页搜索框 → 推入 SearchPage
/// 2. 搜索框外观未变：hint「搜索学科」与两个图标仍在
/// 3. 点击右上「编辑」按钮 → 真实数据刷新（listSubjects 再次调用 + 新学科出现）
/// 4. 回归：卡片 onTap 进详情 / onLongPress 弹菜单 / 新建学科虚线卡片建学科
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:shiye_app/core/api/api_client.dart';
import 'package:shiye_app/features/home/search_page.dart';
import 'package:shiye_app/features/home/subjects_page.dart';
import 'package:shiye_app/features/subjects/subject_detail_page.dart';
import 'package:shiye_app/features/subjects/subject_edit_page.dart';

/// 桩 ApiClient：仅模拟首页学科列表、新建学科、进详情所需接口
class _StubApiClient extends ApiClient {
  _StubApiClient() : super.forTesting();

  int listSubjectsCalls = 0;
  final List<Map<String, dynamic>> _subjects = [
    {
      'id': 1,
      'name': '数学',
      'color': '#4C8C4A',
      'icon': 'book',
      'sort_order': 0,
      'page_count': 3,
      'done_count': 1,
      'chapter_count': 2,
    },
  ];
  int _nextId = 2;

  /// 置 true 后，下一次 [listSubjects] 抛异常（模拟断网刷新失败）
  bool failListSubjects = false;

  /// 模拟服务端新增一条学科（用于验证「编辑」按钮刷新后界面变化）
  void addSubject(String name) {
    _subjects.add({
      'id': _nextId++,
      'name': name,
      'color': '#4C8C4A',
      'icon': 'book',
      'sort_order': 0,
      'page_count': 0,
      'done_count': 0,
      'chapter_count': 0,
    });
  }

  @override
  Future<List<Map<String, dynamic>>> listSubjects() async {
    listSubjectsCalls++;
    if (failListSubjects) {
      throw ApiException('无法连接服务器，请检查网络或确认服务已启动');
    }
    return List<Map<String, dynamic>>.from(_subjects);
  }

  @override
  Future<Map<String, dynamic>> createSubject(String name, {String color = '#4C8C4A'}) async {
    final s = {
      'id': _nextId++,
      'name': name,
      'color': color,
      'icon': 'book',
      'sort_order': 0,
      'page_count': 0,
      'done_count': 0,
      'chapter_count': 0,
    };
    _subjects.add(s);
    return Map<String, dynamic>.from(s);
  }

  @override
  Future<void> deleteSubject(int id) async {
    _subjects.removeWhere((s) => s['id'] == id);
  }

  @override
  Future<List<Map<String, dynamic>>> listChapters(int subjectId) async => [];

  @override
  Future<Map<String, dynamic>> listPages({
    int? subjectId,
    int? chapterId,
    String? state,
    int page = 1,
    int size = 50,
  }) async {
    return {'items': <Map<String, dynamic>>[], 'total': 0};
  }
}

Future<void> _pumpHome(WidgetTester tester, _StubApiClient stub) async {
  await tester.pumpWidget(MaterialApp(home: SubjectsPage(api: stub)));
  await tester.pumpAndSettle();
}

void main() {
  group('T8 首页搜索框', () {
    testWidgets('点击搜索框推入 SearchPage', (tester) async {
      await _pumpHome(tester, _StubApiClient());

      await tester.tap(find.byType(TextField));
      await tester.pumpAndSettle();

      final found = find.byType(SearchPage).evaluate().isNotEmpty;
      debugPrint('[T8 真跑] 点击搜索框后 SearchPage 是否被推入：$found');
      expect(find.byType(SearchPage), findsOneWidget);
    });

    testWidgets('搜索框外观未变：hint 与两个图标仍在', (tester) async {
      await _pumpHome(tester, _StubApiClient());

      expect(find.text('搜索学科'), findsOneWidget);
      expect(find.byIcon(Icons.search), findsOneWidget);
      expect(find.byIcon(Icons.mic_none_rounded), findsOneWidget);
    });
  });

  group('T8 编辑按钮', () {
    testWidgets('点击编辑按钮触发数据刷新并显示新学科', (tester) async {
      final stub = _StubApiClient();
      await _pumpHome(tester, stub);
      expect(find.text('数学'), findsOneWidget);
      expect(find.text('英语'), findsNothing);
      expect(stub.listSubjectsCalls, 1);

      // 模拟服务端新增数据后，点「编辑」应重新拉取并呈现
      stub.addSubject('英语');
      await tester.tap(find.byTooltip('编辑'));
      await tester.pumpAndSettle();

      debugPrint('[T8 真跑] 点编辑按钮后 listSubjects 调用次数：${stub.listSubjectsCalls}（初始为 1）');
      debugPrint('[T8 真跑] 点编辑按钮后新学科「英语」是否出现：${find.text('英语').evaluate().isNotEmpty}');
      expect(find.text('英语'), findsOneWidget); // 界面变化：新学科出现
      expect(stub.listSubjectsCalls, 2); // 数据刷新：再次调用 listSubjects

      // 清理 SnackBar 的自动关闭 timer，避免 pending timer 报错
      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();
    });

    testWidgets('编辑按钮刷新失败时不提示「已刷新」', (tester) async {
      final stub = _StubApiClient();
      await _pumpHome(tester, stub);
      expect(find.text('数学'), findsOneWidget);
      expect(find.text('已刷新学科列表'), findsNothing);

      // 模拟断网：下一次 listSubjects 抛异常
      stub.failListSubjects = true;
      await tester.tap(find.byTooltip('编辑'));
      await tester.pumpAndSettle();

      debugPrint('[T8 真跑] 刷新失败后「已刷新学科列表」是否出现：${find.text('已刷新学科列表').evaluate().isNotEmpty}');
      expect(find.text('已刷新学科列表'), findsNothing); // 失败不谎报成功
      expect(stub.listSubjectsCalls, 2); // 确实发起了第二次刷新
      expect(find.text('加载失败'), findsOneWidget); // 错误态真实表达失败
    });
  });

  group('T8 回归', () {
    testWidgets('学科卡片 onTap 仍能进详情', (tester) async {
      await _pumpHome(tester, _StubApiClient());

      await tester.tap(find.text('数学'));
      await tester.pumpAndSettle();

      expect(find.byType(SubjectDetailPage), findsOneWidget);
    });

    testWidgets('学科卡片 onLongPress 仍弹出修改/删除菜单', (tester) async {
      await _pumpHome(tester, _StubApiClient());

      await tester.longPress(find.text('数学'));
      await tester.pumpAndSettle();

      expect(find.text('重命名 / 改色'), findsOneWidget);
      expect(find.text('删除'), findsOneWidget);
    });

    testWidgets('新建学科虚线卡片仍能建学科', (tester) async {
      await _pumpHome(tester, _StubApiClient());

      // 点新建学科虚线卡片 → 弹出新建弹窗
      await tester.tap(find.text('新建学科'));
      await tester.pumpAndSettle();

      // 在弹窗内的名称输入框输入并创建
      final nameField = find.descendant(
        of: find.byType(SubjectEditPage),
        matching: find.byType(TextField),
      );
      await tester.enterText(nameField, '英语');
      await tester.tap(find.widgetWithText(FilledButton, '创建'));
      await tester.pumpAndSettle();

      expect(find.text('英语'), findsOneWidget);
    });
  });
}
