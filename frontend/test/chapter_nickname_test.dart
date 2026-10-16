/// T4-4 / T4-5 章管理 + 改昵称 widget 测试
///
/// 用桩 ApiClient（测试内部 mock，不算产品假数据）验证：
/// 1. 章新建后列表出现该章
/// 2. 章删除二次确认后列表移除
/// 3. 改昵称保存后界面显示新昵称
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:shiye_app/core/api/api_client.dart';
import 'package:shiye_app/core/auth_provider.dart';
import 'package:shiye_app/core/models/subject.dart';
import 'package:shiye_app/features/home/profile_page.dart';
import 'package:shiye_app/features/subjects/subject_detail_page.dart';

/// 桩 ApiClient：仅模拟章管理 + 改昵称所需接口
class _StubApiClient extends ApiClient {
  _StubApiClient() : super.forTesting();

  final List<Map<String, dynamic>> _chapters = [];
  int _nextChapterId = 1;
  final Map<String, dynamic> _me = {'id': 1, 'nickname': '原昵称', 'created_at': '2026-09-12T00:00:00'};

  @override
  bool get isLoggedIn => true;

  @override
  Future<List<Map<String, dynamic>>> listChapters(int subjectId) async => List.of(_chapters);

  @override
  Future<Map<String, dynamic>> createChapter(int subjectId, String name) async {
    final ch = {
      'id': _nextChapterId++,
      'subject_id': subjectId,
      'name': name,
      'sort_order': _chapters.length,
      'page_count': 0,
    };
    _chapters.add(ch);
    return Map<String, dynamic>.from(ch);
  }

  @override
  Future<void> deleteChapter(int subjectId, int chapterId) async {
    _chapters.removeWhere((c) => c['id'] == chapterId);
  }

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

  @override
  Future<Map<String, dynamic>> getMe() async => Map<String, dynamic>.from(_me);

  @override
  Future<Map<String, dynamic>> updateMe({String? nickname, String? avatarUrl}) async {
    if (nickname != null) _me['nickname'] = nickname;
    return Map<String, dynamic>.from(_me);
  }
}

Subject _makeSubject() => Subject(
      id: 1,
      name: '数学',
      color: '#4C8C4A',
      icon: 'book',
      sortOrder: 0,
      pageCount: 0,
      doneCount: 0,
      chapterCount: 0,
    );

void main() {
  group('章管理（T4-4）', () {
    testWidgets('新建章后列表出现该章', (tester) async {
      final stub = _StubApiClient();
      await tester.pumpWidget(MaterialApp(
        home: SubjectDetailPage(subject: _makeSubject(), api: stub),
      ));
      await tester.pumpAndSettle();

      // 打开章管理
      await tester.tap(find.byTooltip('章管理'));
      await tester.pumpAndSettle();

      // 输入章名并新建
      await tester.enterText(find.byType(TextField), '函数与导数');
      await tester.tap(find.widgetWithText(FilledButton, '新建'));
      await tester.pumpAndSettle();

      // 列表出现该章
      expect(find.text('函数与导数'), findsOneWidget);
    });

    testWidgets('删除章二次确认后列表移除', (tester) async {
      final stub = _StubApiClient();
      // 预置一个章
      await stub.createChapter(1, '函数与导数');

      await tester.pumpWidget(MaterialApp(
        home: SubjectDetailPage(subject: _makeSubject(), api: stub),
      ));
      await tester.pumpAndSettle();

      // 打开章管理
      await tester.tap(find.byTooltip('章管理'));
      await tester.pumpAndSettle();
      expect(find.text('函数与导数'), findsOneWidget);

      // 点删除图标 → 二次确认
      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pumpAndSettle();
      // 确认弹窗里的「删除」按钮
      await tester.tap(find.widgetWithText(TextButton, '删除'));
      await tester.pumpAndSettle();

      // 列表移除该章
      expect(find.text('函数与导数'), findsNothing);
    });
  });

  group('改昵称（T4-5）', () {
    testWidgets('保存成功后界面显示新昵称', (tester) async {
      final stub = _StubApiClient();
      await tester.pumpWidget(
        ChangeNotifierProvider<AuthProvider>.value(
          value: AuthProvider(api: stub),
          child: MaterialApp(home: ProfilePage(api: stub)),
        ),
      );
      await tester.pumpAndSettle();

      // 初始昵称
      expect(find.text('原昵称'), findsOneWidget);

      // 点昵称卡片进入编辑
      await tester.tap(find.text('点击修改昵称'));
      await tester.pumpAndSettle();

      // 输入新昵称并保存
      await tester.enterText(find.byType(TextField), '新昵称');
      await tester.tap(find.widgetWithText(FilledButton, '保存'));
      await tester.pumpAndSettle();

      // 界面显示新昵称
      expect(find.text('新昵称'), findsOneWidget);
      expect(find.text('原昵称'), findsNothing);
    });
  });
}
