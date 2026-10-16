/// 答题页（T10-2）— 三阶段：出题 → 作答 → 判分结果
///
/// 铁律（本批高危线）：
/// - 题目、判分结果**全部来自后端接口**（T9 `/ai/quiz/generate`、`/ai/quiz/grade`）
/// - **绝不**硬编码示例题目、**绝不**本地自造分数；拿不到数据就如实空态 / 报错，
///   绝不"造几道题糊上去"
/// - 空态 / 错误态一律用后端返回的**真实文案**（`reason` / `detail`）
///
/// 复用现有机制（不重写）：
/// - 429 冷却倒计时：与 T7 学情页同款（`_cooldownSeconds` / `_notice` / `_cooldownTimer`）
/// - 异常 → 中文文案：`mapExceptionToMessage`
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/api/api_client.dart';
import '../../core/theme/app_colors.dart';

/// 作答字数上限：与后端 `QuizAnswer.answer_text` 硬上限（2000）一致。
/// 前端先拦（`maxLength`），避免用户白填一通后被后端 422 拒绝。
const int kQuizAnswerMaxLength = 2000;

/// 掌握度 → 中文标签（后端只返回 good / partial / weak）
const Map<String, String> kQuizMasteryLabels = {
  'good': '掌握良好',
  'partial': '部分掌握',
  'weak': '未掌握',
};

/// 题目（来自 `/ai/quiz/generate`；后端刻意不返回参考答案）
class QuizQuestion {
  final int questionId;
  final int seq;
  final String question;
  final String knowledgePoint;

  QuizQuestion({
    required this.questionId,
    required this.seq,
    required this.question,
    required this.knowledgePoint,
  });

  factory QuizQuestion.fromJson(Map<String, dynamic> j) => QuizQuestion(
        questionId: (j['question_id'] as num).toInt(),
        seq: (j['seq'] as num?)?.toInt() ?? 0,
        question: j['question'] as String? ?? '',
        knowledgePoint: j['knowledge_point'] as String? ?? '',
      );
}

/// 单题判分结果（来自 `/ai/quiz/grade`）
class QuizResult {
  final int questionId;
  final int seq;
  final String question;
  final String knowledgePoint;
  final String userAnswer;
  final bool isCorrect;
  final String mastery;
  final String comment;

  QuizResult({
    required this.questionId,
    required this.seq,
    required this.question,
    required this.knowledgePoint,
    required this.userAnswer,
    required this.isCorrect,
    required this.mastery,
    required this.comment,
  });

  factory QuizResult.fromJson(Map<String, dynamic> j) => QuizResult(
        questionId: (j['question_id'] as num).toInt(),
        seq: (j['seq'] as num?)?.toInt() ?? 0,
        question: j['question'] as String? ?? '',
        knowledgePoint: j['knowledge_point'] as String? ?? '',
        userAnswer: j['user_answer'] as String? ?? '',
        isCorrect: j['is_correct'] == true,
        mastery: j['mastery'] as String? ?? '',
        comment: j['comment'] as String? ?? '',
      );
}

enum _QuizPhase { loading, answering, result }

/// 答题页配色 —— T13-2：整页深色化（与学情页同一套"语义重指"策略）。
///
/// 原来这里自带一份浅绿纸感色板（与学情页重复），现统一指向深色令牌，色盘做唯一真相源。
class _Q {
  static const bg1 = AppColors.surfaceMuted;
  static const bg2 = AppColors.surfaceMuted;
  static const ink = AppColors.ink;
  static const ink2 = AppColors.inkSecondary;
  static const ink3 = AppColors.inkTertiary;
  static const green1 = AppColors.primaryLight;
  static const green2 = AppColors.primary;
  static const greenDeep = AppColors.primaryLight;
  static const red = AppColors.red;
  static const orange = AppColors.orange;
}

class QuizPage extends StatefulWidget {
  final int? subjectId;
  final String? subjectName;
  final ApiClient? api; // 测试注入

  const QuizPage({super.key, this.subjectId, this.subjectName, this.api});

  @override
  State<QuizPage> createState() => _QuizPageState();
}

class _QuizPageState extends State<QuizPage> {
  late final ApiClient _api = widget.api ?? ApiClient();

  _QuizPhase _phase = _QuizPhase.loading;
  List<QuizQuestion> _questions = [];
  final List<TextEditingController> _controllers = [];
  int? _sessionId;

  /// 后端空态文案（`reason` 原文）—— 直接展示，绝不自造
  String? _emptyReason;

  /// 出题失败文案（`mapExceptionToMessage` 结果）
  String? _error;

  bool _submitting = false;

  /// 判分失败的提示（**保留**用户已填内容，仅提示 + 允许重试）
  String? _submitError;

  List<QuizResult> _results = [];
  String? _summary;
  List<String> _suggestions = [];

  // ===== T7 冷却倒计时机制（与学情页同款，未重写）=====
  /// 429 冷却剩余秒数（0 = 不在冷却期）。只来自后端 `retry_after_seconds`，禁止前端自造。
  int _cooldownSeconds = 0;

  /// 按钮下方展示的后端 detail 原文
  String? _notice;

  /// 冷却倒计时 Timer（每秒递减；dispose 时必须取消）
  Timer? _cooldownTimer;

  @override
  void initState() {
    super.initState();
    _loadQuestions();
  }

  @override
  void dispose() {
    // T7：页面销毁必须取消 Timer（否则归零后仍在跑 / 泄漏）
    _cooldownTimer?.cancel();
    _cooldownTimer = null;
    for (final c in _controllers) {
      c.dispose();
    }
    super.dispose();
  }

  /// T7：启动/重置冷却倒计时（[seconds] 必须来自后端 `retry_after_seconds`）
  void _startCooldown(int seconds, String detail) {
    _cooldownTimer?.cancel();
    _cooldownSeconds = seconds;
    _notice = detail;
    _cooldownTimer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) {
        t.cancel();
        return;
      }
      setState(() {
        _cooldownSeconds--;
        if (_cooldownSeconds <= 0) {
          // 归零：停表、清理，按钮恢复可点（不自动发起请求）
          _cooldownSeconds = 0;
          _notice = null;
          t.cancel();
          _cooldownTimer = null;
        }
      });
    });
  }

  /// T7：清除冷却态（出题成功时调用）
  void _clearCooldown() {
    _cooldownTimer?.cancel();
    _cooldownTimer = null;
    _cooldownSeconds = 0;
    _notice = null;
  }

  /// 阶段一：加载题目（真调 `/ai/quiz/generate`）
  Future<void> _loadQuestions() async {
    setState(() {
      _phase = _QuizPhase.loading;
      _error = null;
      _emptyReason = null;
      _submitError = null;
    });
    try {
      final data = await _api.generateQuiz(subjectId: widget.subjectId);
      if (!mounted) return;

      // 空态：直接展示后端 reason 原文（**绝不**自造题目糊上去）
      if (data['empty'] == true) {
        _clearCooldown();
        setState(() {
          _emptyReason = (data['reason'] as String?)?.trim().isNotEmpty == true
              ? (data['reason'] as String).trim()
              : '当前数据不足，无法出题';
          _questions = [];
        });
        return;
      }

      final raw = (data['questions'] as List?) ?? const [];
      final questions = raw
          .map((e) => QuizQuestion.fromJson(e as Map<String, dynamic>))
          .toList();
      // 拿到空题目列表 → 如实报错（不糊假题）
      if (questions.isEmpty) {
        _clearCooldown();
        setState(() => _error = '未获取到题目，请稍后重试');
        return;
      }

      _clearCooldown();
      for (final c in _controllers) {
        c.dispose();
      }
      _controllers
        ..clear()
        ..addAll(questions.map((_) => TextEditingController()));
      setState(() {
        _sessionId = (data['session_id'] as num?)?.toInt();
        _questions = questions;
        _phase = _QuizPhase.answering;
      });
    } catch (e) {
      if (!mounted) return;
      final msg = mapExceptionToMessage(e);
      // T7：只有后端真实返回 retry_after_seconds 才起倒计时；拿不到就只显示 detail
      final retry = e is ApiException ? e.retryAfterSeconds : null;
      setState(() {
        _error = msg;
        if (retry != null && retry > 0) {
          _startCooldown(retry, msg);
        }
      });
    }
  }

  /// 阶段二：提交作答（真调 `/ai/quiz/grade`）
  Future<void> _submit() async {
    // 前端拦截：每道题都必须作答，避免误把空作答提交给后端
    for (var i = 0; i < _questions.length; i++) {
      if (_controllers[i].text.trim().isEmpty) {
        const tip = '还有题目未作答，请填写后再提交';
        setState(() => _submitError = tip);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text(tip)));
        return;
      }
    }
    final sessionId = _sessionId;
    if (sessionId == null) {
      setState(() => _submitError = '会话已失效，请重新出题');
      return;
    }

    final answers = <Map<String, dynamic>>[
      for (var i = 0; i < _questions.length; i++)
        {
          'question_id': _questions[i].questionId,
          'answer_text': _controllers[i].text.trim(),
        },
    ];
    setState(() {
      _submitting = true;
      _submitError = null;
    });
    try {
      final data = await _api.gradeQuiz(sessionId: sessionId, answers: answers);
      if (!mounted) return;
      final results = ((data['results'] as List?) ?? const [])
          .map((e) => QuizResult.fromJson(e as Map<String, dynamic>))
          .toList();
      if (results.isEmpty) {
        // 拿不到判分结果 → 如实报错（绝不本地自造分数），并保留已填内容
        setState(() {
          _submitting = false;
          _submitError = '未获取到判分结果，请稍后重试';
        });
        return;
      }
      setState(() {
        _submitting = false;
        _results = results;
        _summary = data['summary'] as String?;
        _suggestions = ((data['suggestions'] as List?) ?? const [])
            .map((e) => e.toString())
            .toList();
        _phase = _QuizPhase.result;
      });
    } catch (e) {
      if (!mounted) return;
      final msg = mapExceptionToMessage(e);
      // 失败：**保留**用户已填内容（不清空 controller），仅提示 + 允许重试
      setState(() {
        _submitting = false;
        _submitError = msg;
      });
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final cooling = _cooldownSeconds > 0;
    return Scaffold(
      backgroundColor: _Q.bg1,
      appBar: AppBar(
        backgroundColor: _Q.bg1,
        elevation: 0,
        foregroundColor: _Q.ink,
        title: Text(
          '答题测水平',
          style: const TextStyle(fontFamily: 'MaShanZheng', fontSize: 24, color: _Q.ink),
        ),
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [_Q.bg1, _Q.bg2],
          ),
        ),
        child: _buildBody(cooling),
      ),
    );
  }

  Widget _buildBody(bool cooling) {
    if (_emptyReason != null) return _buildEmpty();
    if (_error != null) return _buildError(cooling);
    switch (_phase) {
      case _QuizPhase.loading:
        return const Center(child: CircularProgressIndicator(color: _Q.green2));
      case _QuizPhase.answering:
        return _buildAnswering();
      case _QuizPhase.result:
        return _buildResult();
    }
  }

  // ==================== 空态（后端 reason 原文） ====================

  Widget _buildEmpty() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.edit_note_rounded, size: 56, color: _Q.ink3),
            const SizedBox(height: 14),
            const Text('暂时无法出题', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: _Q.ink)),
            const SizedBox(height: 8),
            Text(
              _emptyReason!,
              key: const ValueKey('quiz_empty_reason'),
              style: const TextStyle(fontSize: 13, color: _Q.ink2, height: 1.7),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 20),
            OutlinedButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('返回'),
            ),
          ],
        ),
      ),
    );
  }

  // ==================== 错误态（含 429 冷却倒计时） ====================

  Widget _buildError(bool cooling) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cloud_off_rounded, size: 48, color: _Q.ink3),
            const SizedBox(height: 12),
            Text(
              _error!,
              key: const ValueKey('quiz_error'),
              style: const TextStyle(fontSize: 13, color: _Q.ink2),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 18),
            ElevatedButton(
              key: const ValueKey('quiz_retry_button'),
              onPressed: cooling ? null : _loadQuestions,
              child: Text(cooling ? '$_cooldownSeconds 秒后可重新生成' : '重试'),
            ),
            // 与 T7 同款：按钮下方展示后端 detail 原文（与主文案不同时才重复展示）
            if (_notice != null && _notice != _error) ...[
              const SizedBox(height: 8),
              Text(
                _notice!,
                key: const ValueKey('quiz_notice'),
                style: const TextStyle(fontSize: 11.5, color: _Q.ink3),
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }

  // ==================== 阶段二：作答 ====================

  Widget _buildAnswering() {
    return Column(
      children: [
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
            itemCount: _questions.length,
            separatorBuilder: (_, _) => const SizedBox(height: 14),
            itemBuilder: (_, i) => _buildQuestionCard(i),
          ),
        ),
        Container(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
          decoration: BoxDecoration(
            color: _Q.bg1.withValues(alpha: .94),
            border: Border(top: BorderSide(color: AppColors.glassBorder)),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (_submitError != null) ...[
                Text(
                  _submitError!,
                  key: const ValueKey('quiz_submit_error'),
                  style: const TextStyle(fontSize: 12, color: _Q.red),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
              ] else ...[
                Text(
                  '共 ${_questions.length} 题 · 每题必答，作答后提交判分',
                  style: const TextStyle(fontSize: 11, color: _Q.ink3),
                ),
                const SizedBox(height: 8),
              ],
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  key: const ValueKey('quiz_submit_button'),
                  onPressed: _submitting ? null : _submit,
                  style: FilledButton.styleFrom(
                    backgroundColor: _Q.green2,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  child: _submitting
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Text('提交并判分'),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildQuestionCard(int i) {
    final q = _questions[i];
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.glassFill,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.glassBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                '第 ${q.seq} 题',
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: _Q.greenDeep),
              ),
              const SizedBox(width: 8),
              if (q.knowledgePoint.isNotEmpty)
                Flexible(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: _Q.green1.withValues(alpha: .22),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      q.knowledgePoint,
                      style: const TextStyle(fontSize: 11, color: _Q.greenDeep),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            q.question,
            style: const TextStyle(fontSize: 13.5, color: _Q.ink, height: 1.6),
          ),
          const SizedBox(height: 10),
          TextField(
            key: ValueKey('quiz_answer_field_$i'),
            controller: _controllers[i],
            minLines: 3,
            maxLines: 6,
            // 前端先拦 2000 字（带计数器），避免白填后被后端 422 拒绝
            maxLength: kQuizAnswerMaxLength,
            decoration: InputDecoration(
              hintText: '写下你的作答…',
              hintStyle: const TextStyle(fontSize: 12.5, color: _Q.ink3),
              filled: true,
              fillColor: AppColors.glassFill,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(color: _Q.green1.withValues(alpha: .45)),
              ),
              contentPadding: const EdgeInsets.all(12),
            ),
          ),
        ],
      ),
    );
  }

  // ==================== 阶段三：判分结果 ====================

  Widget _buildResult() {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        if ((_summary ?? '').isNotEmpty) _buildSummaryCard(),
        const SizedBox(height: 14),
        for (var i = 0; i < _results.length; i++) ...[
          _buildResultCard(_results[i]),
          if (i != _results.length - 1) const SizedBox(height: 14),
        ],
        if (_suggestions.isNotEmpty) ...[
          const SizedBox(height: 14),
          _buildSuggestionsCard(),
        ],
        const SizedBox(height: 20),
        OutlinedButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('返回'),
        ),
      ],
    );
  }

  Widget _buildSummaryCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [_Q.green1.withValues(alpha: .26), AppColors.glassFill],
        ),
        border: Border.all(color: AppColors.glassBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('总体诊断', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: _Q.greenDeep)),
          const SizedBox(height: 8),
          Text(
            _summary!,
            key: const ValueKey('quiz_summary'),
            style: const TextStyle(fontSize: 13, color: _Q.ink2, height: 1.75),
          ),
        ],
      ),
    );
  }

  Widget _buildResultCard(QuizResult r) {
    final masteryLabel = kQuizMasteryLabels[r.mastery] ?? r.mastery;
    final okColor = r.isCorrect ? _Q.greenDeep : _Q.red;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.glassFill,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.glassBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                '第 ${r.seq} 题',
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: _Q.greenDeep),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: okColor.withValues(alpha: .14),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  r.isCorrect ? '答对' : '答错',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: okColor),
                ),
              ),
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: _Q.orange.withValues(alpha: .16),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  masteryLabel,
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: _Q.orange),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(r.question, style: const TextStyle(fontSize: 13.5, color: _Q.ink, height: 1.6)),
          const SizedBox(height: 10),
          _kv('考点', r.knowledgePoint.isEmpty ? '—' : r.knowledgePoint),
          _kv('你的作答', r.userAnswer.isEmpty ? '（未作答）' : r.userAnswer),
          const SizedBox(height: 6),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: _Q.green1.withValues(alpha: .14),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              r.comment,
              style: const TextStyle(fontSize: 12.5, color: _Q.ink2, height: 1.7),
            ),
          ),
        ],
      ),
    );
  }

  Widget _kv(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 62,
            child: Text(label, style: const TextStyle(fontSize: 12, color: _Q.ink3)),
          ),
          Expanded(
            child: Text(value, style: const TextStyle(fontSize: 12.5, color: _Q.ink2, height: 1.6)),
          ),
        ],
      ),
    );
  }

  Widget _buildSuggestionsCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.glassFill,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.glassBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('针对性方案', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: _Q.greenDeep)),
          const SizedBox(height: 8),
          for (var i = 0; i < _suggestions.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Text(
                '${i + 1}. ${_suggestions[i]}',
                key: ValueKey('quiz_suggestion_$i'),
                style: const TextStyle(fontSize: 12.5, color: _Q.ink2, height: 1.7),
              ),
            ),
        ],
      ),
    );
  }
}
