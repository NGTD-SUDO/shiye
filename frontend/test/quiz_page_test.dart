/// T10-2 / T10-3 答题页（三阶段）+ 学情页测评入口 widget 测试
///
/// 全部用桩注入（不真连网）；覆盖：取题、空态原文、429 冷却倒计时、502/503 重试、
/// 作答提交、未填拦截、超长拦截、判分中文标签、suggestions 逐条、失败保留输入、入口跳转。
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:shiye_app/core/api/api_client.dart';
import 'package:shiye_app/features/study/quiz_page.dart';
import 'package:shiye_app/features/study/study_report_page.dart';

/// 桩 ApiClient：同时支持出题 / 判分（以及入口测试所需的 studyReport）
class _StubApiClient extends ApiClient {
  _StubApiClient() : super.forTesting();

  // ---- 出题 ----
  Map<String, dynamic> generateResult = {};
  Object? generateError;
  int generateCalls = 0;

  // ---- 判分 ----
  Map<String, dynamic> gradeResult = {};
  Object? gradeError;
  int gradeCalls = 0;
  int? lastSessionId;
  List<Map<String, dynamic>>? lastAnswers;

  // ---- 学情报告（入口测试用）----
  Map<String, dynamic> reportResult = {
    'report_md': '① 本阶段学习概况\n共记录 29 页笔记\n（仅供参考）',
    'stats': {
      'total_pages': 29,
      'ocr_done': 27,
      'ocr_failed': 2,
      'ocr_processing': 0,
      'done_ratio': 27 / 29,
      'days_30_trend': List.filled(28, 0) + [16, 11],
      'subjects': [
        {'subject_id': 1, 'name': '数学', 'page_count': 29, 'done_ratio': 27 / 29},
      ],
      'chapters': [
        {'chapter_id': null, 'name': '未分章', 'page_count': 29},
      ],
      'failed_pages': [
        {'page_id': 999, 'title': '错题页'},
      ],
      'stale_subjects': <String>[],
    },
    'generated_at': '2026-09-13T00:00:00Z',
  };

  @override
  Future<Map<String, dynamic>> generateQuiz({int? subjectId}) async {
    generateCalls++;
    if (generateError != null) throw generateError!;
    return generateResult;
  }

  @override
  Future<Map<String, dynamic>> gradeQuiz({
    required int sessionId,
    required List<Map<String, dynamic>> answers,
  }) async {
    gradeCalls++;
    lastSessionId = sessionId;
    lastAnswers = answers;
    if (gradeError != null) throw gradeError!;
    return gradeResult;
  }

  @override
  Future<Map<String, dynamic>> studyReport({int? subjectId}) async => reportResult;
}

/// 后端风格的三题（无参考答案）
Map<String, dynamic> _threeQuestions() => {
      'session_id': 7,
      'questions': [
        {
          'question_id': 101,
          'seq': 1,
          'question': '根据笔记，导数的定义是什么？',
          'knowledge_point': '导数的定义',
        },
        {
          'question_id': 102,
          'seq': 2,
          'question': '极值点处导数有什么特点？',
          'knowledge_point': '极值点处导数为零',
        },
        {
          'question_id': 103,
          'seq': 3,
          'question': '说明导数与极值之间的关系。',
          'knowledge_point': '导数与极值的关系',
        },
      ],
    };

/// 后端风格的判分结果（含 good / partial / weak 三种掌握度）
Map<String, dynamic> _gradeResult() => {
      'session_id': 7,
      'status': 'graded',
      'results': [
        {
          'question_id': 101,
          'seq': 1,
          'question': '根据笔记，导数的定义是什么？',
          'knowledge_point': '导数的定义',
          'user_answer': '导数就是瞬时变化率',
          'is_correct': true,
          'mastery': 'good',
          'comment': '作答准确，抓住了瞬时变化率这一核心。',
        },
        {
          'question_id': 102,
          'seq': 2,
          'question': '极值点处导数有什么特点？',
          'knowledge_point': '极值点处导数为零',
          'user_answer': '切线斜率',
          'is_correct': false,
          'mastery': 'partial',
          'comment': '答的是几何意义，未点出「导数为零」。',
        },
        {
          'question_id': 103,
          'seq': 3,
          'question': '说明导数与极值之间的关系。',
          'knowledge_point': '导数与极值的关系',
          'user_answer': '不知道',
          'is_correct': false,
          'mastery': 'weak',
          'comment': '与考点无关，属于答非所问。',
        },
      ],
      'summary': '总体诊断：导数定义掌握良好，极值相关结论薄弱。',
      'suggestions': [
        '针对「极值点处导数为零」：默写该结论并做 5 组判断练习。',
        '针对「导数与极值的关系」：用表格对比极大值/极小值的符号条件。',
      ],
    };

/// 放大测试视口：题目/结果卡在 ListView 里是懒加载的，
/// 默认 800x600 只会构建前一两张卡，断言会因"未构建"而误判。
void _useTallViewport(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 3200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

Future<void> _pumpQuiz(WidgetTester tester, _StubApiClient stub) async {
  _useTallViewport(tester);
  await tester.pumpWidget(MaterialApp(home: QuizPage(api: stub)));
  await tester.pump(); // initState → generateQuiz
  await tester.pump(); // flush Future
}

/// 清掉 SnackBar 的自动关闭 Timer，避免用例结束时留下 pending timer
Future<void> _drainSnackBar(WidgetTester tester) async {
  await tester.pump(const Duration(seconds: 5));
  await tester.pump();
}

Future<void> _fillAll(WidgetTester tester, List<String> answers) async {
  for (var i = 0; i < answers.length; i++) {
    await tester.enterText(find.byKey(ValueKey('quiz_answer_field_$i')), answers[i]);
  }
  await tester.pump();
}

ElevatedButton _retryButton(WidgetTester tester) =>
    tester.widget<ElevatedButton>(find.byKey(const ValueKey('quiz_retry_button')));

void main() {
  testWidgets('取题：桩返回 3 题 → 题干与考点都渲染出来', (tester) async {
    final stub = _StubApiClient()..generateResult = _threeQuestions();
    await _pumpQuiz(tester, stub);

    expect(stub.generateCalls, 1);
    expect(find.text('根据笔记，导数的定义是什么？'), findsOneWidget);
    expect(find.text('极值点处导数有什么特点？'), findsOneWidget);
    expect(find.text('导数的定义'), findsOneWidget); // 考点标签
    expect(find.text('导数与极值的关系'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(3));
  });

  testWidgets('空态：展示后端 reason 原文，且不显示任何题目', (tester) async {
    const reason = '该学科可用笔记仅 1 页，至少 3 页才能出题';
    final stub = _StubApiClient()..generateResult = {'empty': true, 'reason': reason};
    await _pumpQuiz(tester, stub);

    expect(find.text(reason), findsOneWidget); // 原文，非自造文案
    expect(find.byKey(const ValueKey('quiz_empty_reason')), findsOneWidget);
    expect(find.byType(TextField), findsNothing); // 绝不造题
    expect(find.text('提交并判分'), findsNothing);
  });

  testWidgets('出题返回空题目列表 → 如实报错，不造题', (tester) async {
    final stub = _StubApiClient()..generateResult = {'session_id': 9, 'questions': []};
    await _pumpQuiz(tester, stub);

    expect(find.byKey(const ValueKey('quiz_error')), findsOneWidget);
    expect(find.textContaining('未获取到题目'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
  });

  testWidgets('429：复用 T7 冷却倒计时（禁用 + 文案 + 逐秒递减 + 归零恢复）', (tester) async {
    final stub = _StubApiClient()
      ..generateError = ApiException('太频繁了，请 1 分钟后再试', retryAfterSeconds: 30);
    await _pumpQuiz(tester, stub);

    // 后端 detail 原文可见（与 T7 同款：错误视图展示 detail）
    expect(find.textContaining('太频繁'), findsWidgets);
    expect(find.text('30 秒后可重新生成'), findsOneWidget);
    expect(_retryButton(tester).onPressed, isNull, reason: '冷却中按钮必须禁用');
    debugPrint('[T10 真跑] 429 按钮文案：${tester.widget<Text>(find.text('30 秒后可重新生成')).data}');

    await tester.pump(const Duration(seconds: 1));
    expect(find.text('29 秒后可重新生成'), findsOneWidget);
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('28 秒后可重新生成'), findsOneWidget);

    // 归零：恢复「重试」且可点；不自动重发请求
    final callsBefore = stub.generateCalls;
    await tester.pump(const Duration(seconds: 28));
    expect(find.text('重试'), findsOneWidget);
    expect(_retryButton(tester).onPressed, isNotNull, reason: '归零后必须可点');
    expect(stub.generateCalls, callsBefore, reason: '归零后不得自动请求');
    debugPrint('[T10 真跑] 归零后按钮文案：${tester.widget<Text>(find.text('重试')).data}，可点=${_retryButton(tester).onPressed != null}');

    await tester.pumpWidget(const SizedBox());
    await tester.pump();
  });

  testWidgets('502：显示 mapExceptionToMessage 文案 + 「重试」按钮，点重试真再请求一次', (tester) async {
    final stub = _StubApiClient()
      ..generateError = ApiException('无法连接 AI 服务，请检查网络后重试');
    await _pumpQuiz(tester, stub);

    expect(find.text('无法连接 AI 服务，请检查网络后重试'), findsOneWidget);
    expect(find.text('重试'), findsOneWidget);
    expect(_retryButton(tester).onPressed, isNotNull);
    expect(stub.generateCalls, 1);

    // 重试：这次让接口成功 → 应渲染出题目
    stub.generateError = null;
    stub.generateResult = _threeQuestions();
    await tester.tap(find.byKey(const ValueKey('quiz_retry_button')));
    await tester.pump();
    await tester.pump();

    expect(stub.generateCalls, 2, reason: '点重试必须真的再请求一次');
    expect(find.text('根据笔记，导数的定义是什么？'), findsOneWidget);
  });

  testWidgets('提交：3 题都填 → 调 gradeQuiz，session 与 answers 正确', (tester) async {
    final stub = _StubApiClient()
      ..generateResult = _threeQuestions()
      ..gradeResult = _gradeResult();
    await _pumpQuiz(tester, stub);
    await _fillAll(tester, ['导数就是瞬时变化率', '切线斜率', '不知道']);

    await tester.tap(find.byKey(const ValueKey('quiz_submit_button')));
    await tester.pump();
    await tester.pump();

    expect(stub.gradeCalls, 1);
    expect(stub.lastSessionId, 7);
    expect(stub.lastAnswers!.length, 3);
    expect(stub.lastAnswers![0]['question_id'], 101);
    expect(stub.lastAnswers![0]['answer_text'], '导数就是瞬时变化率');
    expect(stub.lastAnswers![2]['question_id'], 103);
    expect(stub.lastAnswers![2]['answer_text'], '不知道');
  });

  testWidgets('未填拦截：有题未填 → 不调用 gradeQuiz，并给出提示', (tester) async {
    final stub = _StubApiClient()..generateResult = _threeQuestions();
    await _pumpQuiz(tester, stub);
    await _fillAll(tester, ['只填了第一题', '', '']);

    await tester.tap(find.byKey(const ValueKey('quiz_submit_button')));
    await tester.pump();

    expect(stub.gradeCalls, 0, reason: '有题未填时绝不提交给后端');
    expect(find.byKey(const ValueKey('quiz_submit_error')), findsOneWidget);
    expect(find.textContaining('还有题目未作答'), findsWidgets);
    await _drainSnackBar(tester);
  });

  testWidgets('超长拦截：作答框 maxLength=2000，输入 2500 字被截到 2000', (tester) async {
    final stub = _StubApiClient()..generateResult = _threeQuestions();
    await _pumpQuiz(tester, stub);

    final field = find.byKey(const ValueKey('quiz_answer_field_0'));
    expect(tester.widget<TextField>(field).maxLength, kQuizAnswerMaxLength);

    await tester.enterText(field, '长' * 2500);
    await tester.pump();
    final ctrl = tester.widget<TextField>(field).controller!;
    expect(ctrl.text.length, kQuizAnswerMaxLength, reason: '前端必须先拦，别让用户白填后被 422 拒');
  });

  testWidgets('判分结果：掌握度渲染为中文标签 + 点评 + 总体诊断', (tester) async {
    final stub = _StubApiClient()
      ..generateResult = _threeQuestions()
      ..gradeResult = _gradeResult();
    await _pumpQuiz(tester, stub);
    await _fillAll(tester, ['导数就是瞬时变化率', '切线斜率', '不知道']);
    await tester.tap(find.byKey(const ValueKey('quiz_submit_button')));
    await tester.pump();
    await tester.pump();

    // 三种掌握度 → 中文标签
    expect(find.text('掌握良好'), findsOneWidget);
    expect(find.text('部分掌握'), findsOneWidget);
    expect(find.text('未掌握'), findsOneWidget);
    // 对/错 + 点评 + 总体诊断
    expect(find.text('答对'), findsOneWidget);
    expect(find.text('答错'), findsNWidgets(2));
    expect(find.text('作答准确，抓住了瞬时变化率这一核心。'), findsOneWidget);
    expect(find.text('与考点无关，属于答非所问。'), findsOneWidget);
    expect(find.byKey(const ValueKey('quiz_summary')), findsOneWidget);
    expect(find.textContaining('极值相关结论薄弱'), findsOneWidget);
    debugPrint('[T10 真跑] 掌握度标签：${kQuizMasteryLabels.values.toList()}');
  });

  testWidgets('判分结果：suggestions 多条逐条渲染', (tester) async {
    final stub = _StubApiClient()
      ..generateResult = _threeQuestions()
      ..gradeResult = _gradeResult();
    await _pumpQuiz(tester, stub);
    await _fillAll(tester, ['a', 'b', 'c']);
    await tester.tap(find.byKey(const ValueKey('quiz_submit_button')));
    await tester.pump();
    await tester.pump();

    expect(find.byKey(const ValueKey('quiz_suggestion_0')), findsOneWidget);
    expect(find.byKey(const ValueKey('quiz_suggestion_1')), findsOneWidget);
    expect(find.textContaining('默写该结论并做 5 组判断练习'), findsOneWidget);
    expect(find.textContaining('用表格对比极大值/极小值'), findsOneWidget);
  });

  testWidgets('判分失败（502）→ 保留用户已填内容，不清空', (tester) async {
    final stub = _StubApiClient()
      ..generateResult = _threeQuestions()
      ..gradeError = ApiException('AI 服务暂时不可用，请稍后重试');
    await _pumpQuiz(tester, stub);
    await _fillAll(tester, ['我的作答一', '我的作答二', '我的作答三']);

    await tester.tap(find.byKey(const ValueKey('quiz_submit_button')));
    await tester.pump();
    await tester.pump();

    expect(stub.gradeCalls, 1);
    // 仍在作答态：输入框还在、内容原样保留
    expect(find.byKey(const ValueKey('quiz_answer_field_0')), findsOneWidget);
    expect(find.text('我的作答一'), findsOneWidget);
    expect(find.text('我的作答二'), findsOneWidget);
    expect(find.text('我的作答三'), findsOneWidget);
    // 且给出对应提示
    expect(find.byKey(const ValueKey('quiz_submit_error')), findsOneWidget);
    expect(find.textContaining('AI 服务暂时不可用'), findsWidgets);
    await _drainSnackBar(tester);
  });

  testWidgets('T10-3 学情页「开始测评」入口 → 进入 QuizPage 并透传学科', (tester) async {
    _useTallViewport(tester);
    SharedPreferences.setMockInitialValues({});
    final stub = _StubApiClient()..generateResult = _threeQuestions();
    await tester.pumpWidget(
      MaterialApp(home: StudyReportPage(subjectId: 1, subjectName: '数学', api: stub)),
    );
    await tester.pump(); // initState → _load（读缓存）
    await tester.pump(); // flush _fetch
    await tester.pump(const Duration(milliseconds: 800)); // 数字滚动动画

    expect(find.byKey(const ValueKey('quiz_entry_button')), findsOneWidget);
    expect(find.text('开始测评'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('quiz_entry_button')));
    await tester.pump(); // push 路由
    await tester.pump(const Duration(milliseconds: 500)); // 页面切换动画
    await tester.pump();

    expect(find.byType(QuizPage), findsOneWidget);
    expect(find.text('答题测水平'), findsOneWidget);
    // 入口透传学科后，出题应已按该学科发起
    expect(stub.generateCalls, 1);

    // 清掉 StudyReportPage 顶部光晕的无限动画
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
  });
}
