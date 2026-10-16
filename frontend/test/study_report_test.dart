/// T5 学情分析页 widget 测试
///
/// 覆盖：统计卡渲染（页数/完成率/30 根趋势柱）、空态、生成报告 + 仅供参考、限流文案。
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:shiye_app/core/api/api_client.dart';
import 'package:shiye_app/features/study/study_report_page.dart';

/// 桩 ApiClient：返回可配置的 studyReport 结果
class _StubApiClient extends ApiClient {
  _StubApiClient() : super.forTesting();

  Map<String, dynamic> result = {};
  Object? error;
  int calls = 0;

  @override
  Future<Map<String, dynamic>> studyReport({int? subjectId}) async {
    calls++;
    if (error != null) throw error!;
    return result;
  }
}

/// 构造有页 stats（29 页 / 27 已识别）
Map<String, dynamic> _stats(int pages, {int done = 27}) => {
      'total_pages': pages,
      'ocr_done': done,
      'ocr_failed': pages - done,
      'ocr_processing': 0,
      'done_ratio': pages == 0 ? 0.0 : done / pages,
      'days_30_trend': List.filled(28, 0) + [done - 11, 11],
      'subjects': [
        {'subject_id': 1, 'name': '数学', 'page_count': pages, 'done_ratio': done / pages},
      ],
      'chapters': [
        {'chapter_id': null, 'name': '未分章', 'page_count': pages},
      ],
      'failed_pages': [
        {'page_id': 999, 'title': '错题页'},
      ],
      'stale_subjects': <String>[],
      'page_titles': ['立体几何', '导数定义'],
    };

/// pump 页面并推进动画（避免 pumpAndSettle 卡在顶部光晕无限动画上）
Future<void> _pumpPage(WidgetTester tester, Widget page) async {
  await tester.pumpWidget(MaterialApp(home: page));
  await tester.pump(); // initState → _load
  await tester.pump(); // flush _load 的 Future
  await tester.pump(const Duration(milliseconds: 800)); // 数字滚动 620ms
}

/// T7 辅助：首屏成功拿到报告（按钮变「重新生成」），再让下一次点击返回 [err]
Future<void> _primeThenFail(WidgetTester tester, _StubApiClient stub, Object err) async {
  stub.result = {
    'report_md': '① 本阶段学习概况\n共记录 29 页笔记\n（仅供参考）',
    'stats': _stats(29),
    'generated_at': '2026-09-12T00:00:00Z',
  };
  await _pumpPage(tester, StudyReportPage(api: stub));
  stub.error = err;
  await tester.tap(find.byKey(const ValueKey('study_generate_button')));
  await tester.pump(); // 触发 _generate
  await tester.pump(); // flush 失败 Future
}

ElevatedButton _button(WidgetTester tester) =>
    tester.widget<ElevatedButton>(find.byKey(const ValueKey('study_generate_button')));

void main() {
  testWidgets('统计卡渲染：页数 + 完成率 + 30 根趋势柱', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient();
    stub.result = {
      'report_md': '',
      'stats': _stats(29),
      'generated_at': '2026-09-12T00:00:00Z',
    };
    await _pumpPage(tester, StudyReportPage(api: stub));

    // 页数（概览卡大号数字）
    expect(find.text('29'), findsWidgets);
    // 完成率胶囊
    expect(find.textContaining('识别完成'), findsOneWidget);
    // 30 根趋势柱
    for (var i = 0; i < 30; i++) {
      expect(find.byKey(ValueKey('trend_bar_$i')), findsOneWidget, reason: '第 $i 根趋势柱应存在');
    }
  });

  testWidgets('空态：empty=true → 引导文案 + 去拍一页笔记按钮，无生成按钮', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient();
    stub.result = {
      'report_md': null,
      'stats': _stats(0, done: 0),
      'empty': true,
    };
    await _pumpPage(tester, StudyReportPage(api: stub));

    expect(find.textContaining('还没有笔记'), findsOneWidget);
    expect(find.text('去拍一页笔记'), findsOneWidget);
    // 无「生成 AI 学情报告」按钮
    expect(find.text('生成 AI 学情报告'), findsNothing);
    // 0 页不调 AI（桩调用次数应为 1，且 empty 时不生成报告）
  });

  testWidgets('生成流程：展示报告文本 + 仅供参考', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient();
    stub.result = {
      'report_md': '① 本阶段学习概况\n共记录 29 页笔记\n（仅供参考）',
      'stats': _stats(29),
      'generated_at': '2026-09-12T00:00:00Z',
    };
    await _pumpPage(tester, StudyReportPage(api: stub));

    expect(find.textContaining('本阶段学习概况'), findsWidgets);
    expect(find.textContaining('仅供参考'), findsWidgets);
  });

  testWidgets('限流：429 → 显示后端 detail 与剩余时间', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient();
    stub.error = ApiException('太频繁了，请 5 分钟后再试');
    await _pumpPage(tester, StudyReportPage(api: stub));

    expect(find.textContaining('太频繁'), findsWidgets);
    expect(find.textContaining('分钟'), findsWidgets);
  });

  // ==================== T7：429 冷却倒计时 ====================

  testWidgets('T7-1 429 且 retry_after_seconds=56 → 倒计时文案 + 按钮禁用', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient();
    await _primeThenFail(tester, stub, ApiException('太频繁了，请 1 分钟后再试', retryAfterSeconds: 56));

    // 按钮文案 = 后端真实剩余秒数（非硬编码）
    expect(find.text('56 秒后可重新生成'), findsOneWidget);
    expect(_button(tester).onPressed, isNull, reason: '冷却中按钮必须禁用');
    // 后端 detail 原文与倒计时并存
    expect(find.byKey(const ValueKey('study_notice')), findsOneWidget);
    expect(find.textContaining('太频繁'), findsWidgets);
    // 报告卡照常显示（上次结果不清空）
    expect(find.textContaining('本阶段学习概况'), findsWidgets);
    debugPrint('[T7 真跑] 按钮实际文案：${tester.widget<Text>(find.text('56 秒后可重新生成')).data}');

    // 结束：销毁页面 → dispose 取消 Timer（不留 pending timer）
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
  });

  testWidgets('T7-1 倒计时每秒递减（fake 时间）', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient();
    await _primeThenFail(tester, stub, ApiException('太频繁了，请 1 分钟后再试', retryAfterSeconds: 56));

    expect(find.text('56 秒后可重新生成'), findsOneWidget);
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('55 秒后可重新生成'), findsOneWidget);
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('54 秒后可重新生成'), findsOneWidget);
    debugPrint('[T7 真跑] 递减后按钮实际文案：${tester.widget<Text>(find.text('54 秒后可重新生成')).data}');

    await tester.pumpWidget(const SizedBox());
    await tester.pump();
  });

  testWidgets('T7-1 归零 → 按钮恢复「重新生成」且可点（不自动请求）', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient();
    await _primeThenFail(tester, stub, ApiException('太频繁了，请稍后再试', retryAfterSeconds: 3));
    final callsBefore = stub.calls;

    expect(find.text('3 秒后可重新生成'), findsOneWidget);
    await tester.pump(const Duration(seconds: 1));
    await tester.pump(const Duration(seconds: 1));
    await tester.pump(const Duration(seconds: 1));

    expect(find.text('重新生成'), findsOneWidget);
    expect(_button(tester).onPressed, isNotNull, reason: '归零后按钮必须可点');
    expect(stub.calls, callsBefore, reason: '归零后不得自动发起请求');
    expect(find.byKey(const ValueKey('study_notice')), findsNothing);
    debugPrint('[T7 真跑] 归零后按钮文案：${tester.widget<Text>(find.text('重新生成')).data}，可点=${_button(tester).onPressed != null}');
  });

  testWidgets('T7-2 429 但无 retry_after_seconds → 只显示 detail，按钮仍可点', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient();
    await _primeThenFail(tester, stub, ApiException('太频繁了，请稍后再试'));

    // 不假造倒计时
    expect(find.textContaining('秒后可重新生成'), findsNothing);
    // 后端 detail 可见
    expect(find.byKey(const ValueKey('study_notice')), findsOneWidget);
    expect(find.textContaining('太频繁'), findsWidgets);
    // 按钮仍可点
    expect(_button(tester).onPressed, isNotNull);
  });

  testWidgets('T7-4 非 429（502）→ 无倒计时、显示后端文案、按钮可点', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient();
    await _primeThenFail(tester, stub, ApiException('AI 服务暂时不可用，请稍后重试'));

    expect(find.textContaining('秒后可重新生成'), findsNothing);
    expect(find.textContaining('AI 服务暂时不可用'), findsWidgets);
    expect(_button(tester).onPressed, isNotNull);
    // 报告卡仍在
    expect(find.textContaining('本阶段学习概况'), findsWidgets);
  });
}
