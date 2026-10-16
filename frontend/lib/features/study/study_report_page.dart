/// 学情分析页（T5-3）— 按冻结稿「拾页-学情分析页-UI提案」实现
///
/// 9 条硬要求：固定底部玻璃工具栏 / 生成后滚动到报告 / 30 柱趋势真实数值 /
/// 反光纹理浅色极淡深色去掉 / MaShanZheng 标题 / 顶部光晕仅一处 /
/// 概览卡数字滚动 / 空态不调 AI / 线条图标。
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show Clipboard, ClipboardData;
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/api/api_client.dart';
import '../../core/theme/app_colors.dart';
import '../pages/page_upload_page.dart';
import 'quiz_page.dart';

/// 学情统计（从后端 /ai/study-report 的 stats 解析）
class StudyStats {
  final int totalPages;
  final int ocrDone;
  final int ocrFailed;
  final int ocrProcessing;
  final double doneRatio;
  final List<int> days30Trend;
  final List<StudySubjectStat> subjects;
  final List<StudyChapterStat> chapters;
  final List<StudyFailedPage> failedPages;
  final List<String> staleSubjects;

  StudyStats({
    required this.totalPages,
    required this.ocrDone,
    required this.ocrFailed,
    required this.ocrProcessing,
    required this.doneRatio,
    required this.days30Trend,
    required this.subjects,
    required this.chapters,
    required this.failedPages,
    required this.staleSubjects,
  });

  factory StudyStats.fromJson(Map<String, dynamic> json) {
    return StudyStats(
      totalPages: (json['total_pages'] as num?)?.toInt() ?? 0,
      ocrDone: (json['ocr_done'] as num?)?.toInt() ?? 0,
      ocrFailed: (json['ocr_failed'] as num?)?.toInt() ?? 0,
      ocrProcessing: (json['ocr_processing'] as num?)?.toInt() ?? 0,
      doneRatio: (json['done_ratio'] as num?)?.toDouble() ?? 0.0,
      days30Trend: ((json['days_30_trend'] as List?) ?? const [])
          .map((e) => (e as num).toInt())
          .toList(),
      subjects: ((json['subjects'] as List?) ?? const [])
          .map((e) => StudySubjectStat.fromJson(e as Map<String, dynamic>))
          .toList(),
      chapters: ((json['chapters'] as List?) ?? const [])
          .map((e) => StudyChapterStat.fromJson(e as Map<String, dynamic>))
          .toList(),
      failedPages: ((json['failed_pages'] as List?) ?? const [])
          .map((e) => StudyFailedPage.fromJson(e as Map<String, dynamic>))
          .toList(),
      staleSubjects: ((json['stale_subjects'] as List?) ?? const [])
          .map((e) => e as String)
          .toList(),
    );
  }
}

class StudySubjectStat {
  final int subjectId;
  final String name;
  final int pageCount;
  final double doneRatio;
  StudySubjectStat({
    required this.subjectId,
    required this.name,
    required this.pageCount,
    required this.doneRatio,
  });
  factory StudySubjectStat.fromJson(Map<String, dynamic> j) => StudySubjectStat(
        subjectId: (j['subject_id'] as num).toInt(),
        name: j['name'] as String? ?? '',
        pageCount: (j['page_count'] as num?)?.toInt() ?? 0,
        doneRatio: (j['done_ratio'] as num?)?.toDouble() ?? 0.0,
      );
}

class StudyChapterStat {
  final int? chapterId;
  final String name;
  final int pageCount;
  StudyChapterStat({required this.chapterId, required this.name, required this.pageCount});
  factory StudyChapterStat.fromJson(Map<String, dynamic> j) => StudyChapterStat(
        chapterId: (j['chapter_id'] as num?)?.toInt(),
        name: j['name'] as String? ?? '',
        pageCount: (j['page_count'] as num?)?.toInt() ?? 0,
      );
}

class StudyFailedPage {
  final int pageId;
  final String title;
  StudyFailedPage({required this.pageId, required this.title});
  factory StudyFailedPage.fromJson(Map<String, dynamic> j) => StudyFailedPage(
        pageId: (j['page_id'] as num).toInt(),
        title: j['title'] as String? ?? '(无标题)',
      );
}

/// 学情页配色 —— T13-2：整页深色化。
///
/// 原来这里自带一套**浅绿纸感色板**（bg/ink/green*），深色主题下会与其他页面割裂。
/// 现按**语义重指**到深色令牌，`app_colors.dart` 继续做唯一真相源（不在此处自创深色值）：
/// - bg*   → 页面底（systemGray6）
/// - ink*  → 三档白文字
/// - green*→ 主色系（原清新绿 → systemBlue）；`greenDeep` 取自读性更好的 `primaryLight`
///           （#007AFF 在深底上对比度仅 3.5:1，做小字号强调文字偏弱）。
class _C {
  static const bg1 = AppColors.surfaceMuted;
  static const bg2 = AppColors.surfaceMuted;
  static const ink = AppColors.ink;
  static const ink2 = AppColors.inkSecondary;
  static const ink3 = AppColors.inkTertiary;
  static const green1 = AppColors.primaryLight;
  static const green2 = AppColors.primary;
  static const greenDeep = AppColors.primaryLight;
}

class StudyReportPage extends StatefulWidget {
  final int? subjectId;
  final String? subjectName;
  final ApiClient? api; // 测试注入

  const StudyReportPage({super.key, this.subjectId, this.subjectName, this.api});

  @override
  State<StudyReportPage> createState() => _StudyReportPageState();
}

class _StudyReportPageState extends State<StudyReportPage> {
  late final ApiClient _api = widget.api ?? ApiClient();

  StudyStats? _stats;
  String? _reportMd;
  String? _generatedAt;
  bool _loading = true; // 首屏加载
  bool _generating = false; // 生成中（骨架）
  bool _empty = false;
  String? _error;

  /// T7：429 冷却剩余秒数（0 = 不在冷却期）。只来自后端 retry_after_seconds，禁止前端自造。
  int _cooldownSeconds = 0;

  /// T7：按钮下方展示的后端 detail 原文（与倒计时并存，让用户知道"为什么"）
  String? _notice;

  /// T7：冷却倒计时 Timer（每秒递减；dispose / 生成成功时必须取消）
  Timer? _cooldownTimer;

  final _scrollController = ScrollController();
  final _reportKey = GlobalKey();

  String get _cacheKey => 'shiye_study_report_${widget.subjectId ?? 'all'}';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    // T7：页面销毁必须取消 Timer（否则归零后仍在跑 / 泄漏）
    _cooldownTimer?.cancel();
    _cooldownTimer = null;
    _scrollController.dispose();
    super.dispose();
  }

  /// T7：启动/重置冷却倒计时
  ///
  /// - [seconds] 必须来自后端 `retry_after_seconds`（真实值），调用方不得自造
  /// - [detail] 后端 detail 原文，倒计时期间显示在按钮下方
  /// - 先取消已有 Timer，避免重复点击叠加多个 Timer
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

  /// T7：清除冷却态（生成成功时调用）
  void _clearCooldown() {
    _cooldownTimer?.cancel();
    _cooldownTimer = null;
    _cooldownSeconds = 0;
    _notice = null;
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    // D2：先读本地缓存，避免每次打开都烧 AI
    final cached = await _readCache();
    if (cached != null && mounted) {
      setState(() {
        _stats = cached.$1;
        _reportMd = cached.$2;
        _generatedAt = cached.$3;
        _empty = false;
        _loading = false;
      });
      return;
    }
    // 无缓存 → 首屏拉一次 stats（0 页不调 AI；有页会顺带生成报告）
    await _fetch(showSkeleton: false);
  }

  Future<void> _fetch({required bool showSkeleton}) async {
    if (showSkeleton) {
      setState(() => _generating = true);
    }
    try {
      final data = await _api.studyReport(subjectId: widget.subjectId);
      if (!mounted) return;
      final empty = data['empty'] == true;
      if (empty) {
        setState(() {
          _clearCooldown();
          _empty = true;
          _stats = StudyStats.fromJson(data['stats'] as Map<String, dynamic>? ?? {});
          _reportMd = null;
          _generatedAt = null;
          _loading = false;
          _generating = false;
        });
        return;
      }
      final stats = StudyStats.fromJson(data['stats'] as Map<String, dynamic>);
      final reportMd = data['report_md'] as String? ?? '';
      final generatedAt = data['generated_at'] as String?;
      setState(() {
        _clearCooldown();
        _stats = stats;
        _reportMd = reportMd;
        _generatedAt = generatedAt;
        _empty = false;
        _loading = false;
        _generating = false;
      });
      await _writeCache(stats, reportMd, generatedAt);
      // 生成后自动滚动到报告卡（硬要求 2）
      if (showSkeleton && _reportKey.currentContext != null) {
        _scrollToReport();
      }
    } catch (e) {
      if (!mounted) return;
      final msg = mapExceptionToMessage(e);
      // T7：只有后端真实返回 retry_after_seconds 才起倒计时；拿不到就只显示 detail
      final retry = e is ApiException ? e.retryAfterSeconds : null;
      setState(() {
        _error = msg;
        _loading = false;
        _generating = false;
        // 已有内容展示时，把后端 detail 放到按钮下方（无内容时交给错误视图，避免重复）
        _notice = _stats != null ? msg : null;
        if (retry != null && retry > 0) {
          _startCooldown(retry, msg);
          if (_stats == null) _notice = null;
        }
      });
      // 有缓存时失败也不覆盖缓存，仅提示
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(msg)),
      );
    }
  }

  void _scrollToReport() {
    // 生成后自动平滑滚动到报告卡视口中间（硬要求 2）
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final ctx = _reportKey.currentContext;
      if (ctx == null) return;
      Scrollable.ensureVisible(
        ctx,
        duration: const Duration(milliseconds: 450),
        curve: Curves.easeOut,
        alignment: 0.5,
      );
    });
  }

  Future<void> _generate() async {
    // T7：冷却期间不重复发起（按钮已禁用，这里再兜一层，防重复点击叠加 Timer）
    if (_generating || _cooldownSeconds > 0) return;
    await _fetch(showSkeleton: true);
  }

  Future<void> _goUpload() async {
    await Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => PageUploadPage(subjectId: widget.subjectId)),
    );
  }

  // ===== 缓存 =====
  Future<(StudyStats, String, String?)?> _readCache() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_cacheKey);
      if (raw == null || raw.isEmpty) return null;
      final j = jsonDecode(raw) as Map<String, dynamic>;
      final stats = StudyStats.fromJson(j['stats'] as Map<String, dynamic>);
      final reportMd = j['report_md'] as String? ?? '';
      final generatedAt = j['generated_at'] as String?;
      return (stats, reportMd, generatedAt);
    } catch (_) {
      return null;
    }
  }

  Future<void> _writeCache(StudyStats stats, String reportMd, String? generatedAt) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        _cacheKey,
        jsonEncode({
          'stats': _statsToJson(stats),
          'report_md': reportMd,
          'generated_at': generatedAt,
        }),
      );
    } catch (_) {
      // 缓存失败不影响主流程
    }
  }

  Map<String, dynamic> _statsToJson(StudyStats s) => {
        'total_pages': s.totalPages,
        'ocr_done': s.ocrDone,
        'ocr_failed': s.ocrFailed,
        'ocr_processing': s.ocrProcessing,
        'done_ratio': s.doneRatio,
        'days_30_trend': s.days30Trend,
        'subjects': [
          for (final x in s.subjects)
            {'subject_id': x.subjectId, 'name': x.name, 'page_count': x.pageCount, 'done_ratio': x.doneRatio},
        ],
        'chapters': [
          for (final x in s.chapters)
            {'chapter_id': x.chapterId, 'name': x.name, 'page_count': x.pageCount},
        ],
        'failed_pages': [
          for (final x in s.failedPages) {'page_id': x.pageId, 'title': x.title},
        ],
        'stale_subjects': s.staleSubjects,
      };

  @override
  Widget build(BuildContext context) {
    // T7：冷却中按钮文案用后端真实剩余秒数；归零后恢复原文案且可点
    final cooling = _cooldownSeconds > 0;
    final buttonLabel = cooling
        ? '$_cooldownSeconds 秒后可重新生成'
        : (_empty ? '去拍一页笔记' : (_reportMd == null ? '生成 AI 学情报告' : '重新生成'));
    return Scaffold(
      backgroundColor: _C.bg1,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [_C.bg1, _C.bg2],
          ),
        ),
        child: Stack(
          children: [
            // 顶部唯一光晕（硬要求 6）
            const Positioned(
              top: -80,
              left: 0,
              right: 0,
              child: IgnorePointer(child: _TopHalo()),
            ),
            SafeArea(
              bottom: false,
              child: Column(
                children: [
                  _buildHeader(),
                  Expanded(
                    child: _buildBody(),
                  ),
                ],
              ),
            ),
            // 固定底部玻璃工具栏（硬要求 1）
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: _BottomBar(
                empty: _empty,
                generating: _generating,
                disabled: cooling,
                notice: _notice,
                onGenerate: _empty ? _goUpload : _generate,
                buttonLabel: buttonLabel,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    final scope = widget.subjectName ?? '全部学科';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
          child: Row(
            children: [
              _IconBtn(
                icon: Icons.arrow_back_ios_new,
                tooltip: '返回',
                onTap: () => Navigator.pop(context),
              ),
              const SizedBox(width: 8),
              const Expanded(
                child: Text(
                  '学情分析',
                  style: TextStyle(
                    fontFamily: 'MaShanZheng',
                    fontSize: 27,
                    color: _C.ink,
                  ),
                ),
              ),
              // T10-3：测评入口（做题测水平）→ QuizPage；透传学科，保持「按学科测」语义。
              // 其余（T7 冷却状态机 / _load / _generate）一律未动。
              TextButton.icon(
                key: const ValueKey('quiz_entry_button'),
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => QuizPage(
                      subjectId: widget.subjectId,
                      subjectName: widget.subjectName,
                      api: widget.api,
                    ),
                  ),
                ),
                icon: const Icon(Icons.quiz_outlined, size: 16, color: _C.greenDeep),
                label: const Text('开始测评', style: TextStyle(fontSize: 12.5, color: _C.greenDeep)),
                style: TextButton.styleFrom(
                  // T13-2：改用令牌自带 alpha（12%），不再传浅色期的 .6
                  backgroundColor: AppColors.glassFill,
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
          child: Text(
            '$scope · 数据更新至刚刚',
            style: const TextStyle(fontSize: 11, color: _C.ink3),
          ),
        ),
      ],
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: _C.green2));
    }
    if (_empty) {
      return const _EmptyView();
    }
    final stats = _stats;
    if (stats == null) {
      return _ErrorView(message: _error ?? '加载失败', onRetry: _load);
    }
    final pending = stats.totalPages - stats.ocrDone;
    return SingleChildScrollView(
      controller: _scrollController,
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 110),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _HeroCard(stats: stats, pending: pending),
          const SizedBox(height: 14),
          _TrendCard(values: stats.days30Trend, total: stats.totalPages),
          const SizedBox(height: 14),
          _SubjectCard(subjects: stats.subjects),
          if (stats.failedPages.isNotEmpty) ...[
            const SizedBox(height: 14),
            _FailedCard(pages: stats.failedPages),
          ],
          const SizedBox(height: 14),
          _ReportCard(
            key: _reportKey,
            reportMd: _reportMd,
            generatedAt: _generatedAt,
            generating: _generating,
          ),
        ],
      ),
    );
  }
}

/// 顶部光晕（呼吸动画）
class _TopHalo extends StatefulWidget {
  const _TopHalo();
  @override
  State<_TopHalo> createState() => _TopHaloState();
}

class _TopHaloState extends State<_TopHalo> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 3600))..repeat(reverse: true);
  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      builder: (_, _) {
        final s = 1.0 + 0.075 * _c.value;
        return Transform.scale(
          scale: s,
          child: Container(
            height: 220,
            decoration: BoxDecoration(
              gradient: RadialGradient(
                center: const Alignment(0, 0),
                radius: 1.0,
                colors: [
                  _C.green1.withValues(alpha: 0.42),
                  Colors.transparent,
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

/// 玻璃卡片基座（浅色极淡反光纹理，深色去纹理 —— 硬要求 4）
class _GlassCard extends StatelessWidget {
  final Widget child;
  const _GlassCard({required this.child});

  @override
  Widget build(BuildContext context) {
    // T13-2：App 已是深色单一主题，原 isDark 的浅/深两套玻璃分支合并为深色一套
    // （浅色分支的 .72/.50/.85 在深色下等于"白玻璃压白"，是错的）。
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(26),
        border: Border.all(color: AppColors.glassBorder),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.glassFill,
            AppColors.glassFill,
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: AppColors.shadow.withValues(alpha: .45),
            blurRadius: 30,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: child,
    );
  }
}

/// 概览卡：大号页数数字滚动 + 完成率胶囊 + 摘要（硬要求 7）
class _HeroCard extends StatelessWidget {
  final StudyStats stats;
  final int pending;
  const _HeroCard({required this.stats, required this.pending});

  @override
  Widget build(BuildContext context) {
    return _GlassCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          _CountUpNumber(
            value: stats.totalPages.toDouble(),
            style: const TextStyle(fontSize: 52, fontWeight: FontWeight.w700, color: _C.ink, height: 0.9, letterSpacing: -1),
          ),
          const SizedBox(width: 4),
          const Padding(
            padding: EdgeInsets.only(bottom: 2),
            child: Text('页', style: TextStyle(fontSize: 14, color: _C.ink2)),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: _C.green1.withValues(alpha: .22),
                      border: Border.all(color: _C.green1.withValues(alpha: .35)),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.check, size: 12, color: _C.greenDeep),
                        const SizedBox(width: 6),
                        Text(
                          '${_CountUpNumber.formatPct(stats.doneRatio)}% 识别完成',
                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: _C.greenDeep),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 9),
                  Text(
                    '${stats.subjects.length} 个学科 · ${stats.ocrDone} 页已识别 · $pending 页待处理',
                    style: const TextStyle(fontSize: 11.5, color: _C.ink3),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 数字滚动（620ms，三次缓出）
class _CountUpNumber extends StatefulWidget {
  final double value;
  final TextStyle style;
  const _CountUpNumber({required this.value, required this.style});

  static String formatPct(double ratio) => (ratio * 100).toStringAsFixed(1);

  @override
  State<_CountUpNumber> createState() => _CountUpNumberState();
}

class _CountUpNumberState extends State<_CountUpNumber> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 620),
  )..forward();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      builder: (_, _) {
        final eased = Curves.easeOutCubic.transform(_c.value);
        final v = widget.value * eased;
        return Text(v.toStringAsFixed(0), style: widget.style);
      },
    );
  }
}

/// 趋势卡：30 根柱，非零标数值，生长动画（硬要求 3）
class _TrendCard extends StatelessWidget {
  final List<int> values;
  final int total;
  const _TrendCard({required this.values, required this.total});

  @override
  Widget build(BuildContext context) {
    final norm = values.isEmpty ? List<int>.filled(30, 0) : values;
    return _GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('近 30 天记录', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: _C.ink)),
              Text('共 $total 页', style: const TextStyle(fontSize: 11.5, color: _C.ink3)),
            ],
          ),
          const SizedBox(height: 12),
          _TrendChart(values: norm),
          const SizedBox(height: 8),
          const Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('30 天前', style: TextStyle(fontSize: 11, color: _C.ink3)),
              Text('今天', style: TextStyle(fontSize: 11, color: _C.ink3)),
            ],
          ),
        ],
      ),
    );
  }
}

class _TrendChart extends StatefulWidget {
  final List<int> values;
  const _TrendChart({required this.values});
  @override
  State<_TrendChart> createState() => _TrendChartState();
}

class _TrendChartState extends State<_TrendChart> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 750),
  )..forward();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final maxV = widget.values.fold<int>(0, (a, b) => b > a ? b : a);
    return SizedBox(
      height: 88,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: List.generate(widget.values.length, (i) {
          final v = widget.values[i];
          // 每根柱 stagger：delay = i * 0.018s（30 根最大 0.522 < 1）
          final anim = CurvedAnimation(
            parent: _c,
            curve: Interval(i * 0.018, 1.0, curve: Curves.easeOut),
          );
          return Expanded(
            key: ValueKey('trend_bar_$i'),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 1.5),
              child: AnimatedBuilder(
                animation: _c,
                builder: (_, _) {
                  final targetH = v == 0 ? 4.0 : 6.0 + (v / (maxV == 0 ? 1 : maxV)) * 60.0;
                  final h = targetH * anim.value;
                  return Stack(
                    alignment: Alignment.bottomCenter,
                    children: [
                      if (v > 0)
                        Positioned(
                          bottom: h + 2,
                          child: Text('$v', style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: _C.greenDeep)),
                        ),
                      Container(
                        height: h,
                        decoration: BoxDecoration(
                          borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
                          gradient: const LinearGradient(
                            begin: Alignment.topCenter,
                            end: Alignment.bottomCenter,
                            colors: [_C.green1, _C.green2],
                          ),
                        ),
                      ),
                    ],
                  );
                },
              ),
            ),
          );
        }),
      ),
    );
  }
}

/// 学科分布
class _SubjectCard extends StatelessWidget {
  final List<StudySubjectStat> subjects;
  const _SubjectCard({required this.subjects});

  @override
  Widget build(BuildContext context) {
    return _GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('学科分布', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: _C.ink)),
          const SizedBox(height: 6),
          ...subjects.map((s) => _SubjectRow(stat: s)),
        ],
      ),
    );
  }
}

class _SubjectRow extends StatelessWidget {
  final StudySubjectStat stat;
  const _SubjectRow({required this.stat});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 9),
      child: Row(
        children: [
          SizedBox(
            width: 96,
            child: Text(
              stat.name,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: _C.ink),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(99),
              child: LinearProgressIndicator(
                value: stat.doneRatio.clamp(0.0, 1.0),
                minHeight: 6,
                backgroundColor: _C.greenDeep.withValues(alpha: .10),
                valueColor: const AlwaysStoppedAnimation(_C.green2),
              ),
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 34,
            child: Text(
              '${stat.pageCount}',
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: _C.ink2),
              textAlign: TextAlign.right,
            ),
          ),
        ],
      ),
    );
  }
}

/// 待处理（识别失败）
class _FailedCard extends StatelessWidget {
  final List<StudyFailedPage> pages;
  const _FailedCard({required this.pages});

  @override
  Widget build(BuildContext context) {
    return _GlassCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 8,
            height: 8,
            margin: const EdgeInsets.only(top: 6, right: 10),
            decoration: const BoxDecoration(color: AppColors.orange, shape: BoxShape.circle),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${pages.length} 页识别失败，建议重拍或重试',
                  style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: _C.ink),
                ),
                const SizedBox(height: 6),
                ...pages.take(3).map((p) => Padding(
                      padding: const EdgeInsets.only(bottom: 3),
                      child: Text('· ${p.title}', style: const TextStyle(fontSize: 12, color: _C.ink2)),
                    )),
                if (pages.length > 3)
                  Text('… 等 ${pages.length} 页', style: const TextStyle(fontSize: 12, color: _C.ink3)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// 报告卡（含骨架屏 + 复制 + 生成时间 + 仅供参考）
class _ReportCard extends StatelessWidget {
  final String? reportMd;
  final String? generatedAt;
  final bool generating;
  const _ReportCard({super.key, required this.reportMd, required this.generatedAt, required this.generating});

  String get _fmtTime {
    if (generatedAt == null) return '';
    try {
      final dt = DateTime.parse(generatedAt!).toLocal();
      return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return '';
    }
  }

  Future<void> _copy(BuildContext context) async {
    if (reportMd == null || reportMd!.isEmpty) return;
    await Clipboard.setData(ClipboardData(text: reportMd!));
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('已复制')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return _GlassCard(
      child: generating
          ? const _Skeleton()
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (reportMd == null || reportMd!.isEmpty)
                  const Text('暂无报告，点击下方按钮生成', style: TextStyle(fontSize: 13, color: _C.ink3))
                else ...[
                  MarkdownBody(
                    data: reportMd!,
                    styleSheet: MarkdownStyleSheet(
                      h3: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: _C.greenDeep),
                      p: const TextStyle(fontSize: 12.5, color: _C.ink2, height: 1.7),
                      listBullet: const TextStyle(fontSize: 12.5, color: _C.ink2, height: 1.7),
                      strong: const TextStyle(fontWeight: FontWeight.w700, color: _C.ink),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Text(
                          '${_fmtTime.isEmpty ? '刚刚生成' : _fmtTime} · 仅供参考',
                          style: const TextStyle(fontSize: 11, color: _C.ink3),
                        ),
                      ),
                      TextButton.icon(
                        onPressed: () => _copy(context),
                        icon: const Icon(Icons.copy_rounded, size: 15, color: _C.ink2),
                        label: const Text('复制', style: TextStyle(fontSize: 12, color: _C.ink)),
                      ),
                    ],
                  ),
                ],
              ],
            ),
    );
  }
}

/// 骨架屏（光带扫过）
class _Skeleton extends StatelessWidget {
  const _Skeleton();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final w in const [0.34, 0.92, 0.86, 0.30, 0.88, 0.70])
          Padding(
            padding: const EdgeInsets.only(bottom: 11),
            child: FractionallySizedBox(
              widthFactor: w,
              child: Container(height: 13, decoration: BoxDecoration(color: _C.greenDeep.withValues(alpha: .09), borderRadius: BorderRadius.circular(8))),
            ),
          ),
      ],
    );
  }
}

/// 固定底部玻璃工具栏（硬要求 1）
class _BottomBar extends StatelessWidget {
  final bool empty;
  final bool generating;

  /// T7：倒计时冷却中 → 按钮禁用（onPressed 为 null）
  final bool disabled;

  /// T7：按钮下方展示的后端 detail 原文（429 时非空；普通状态为 null → 显示常规提示）
  final String? notice;

  final VoidCallback onGenerate;
  final String buttonLabel;
  const _BottomBar({
    required this.empty,
    required this.generating,
    required this.disabled,
    required this.notice,
    required this.onGenerate,
    required this.buttonLabel,
  });

  @override
  Widget build(BuildContext context) {
    // T13-2：合并深浅分支为深色一套；顶部分隔线改用 iOS separator（与底部 Tab 栏一致）。
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 13, 18, 13),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            AppColors.surfaceMuted.withValues(alpha: .86),
            AppColors.surfaceMuted.withValues(alpha: .97),
          ],
        ),
        border: const Border(top: BorderSide(color: AppColors.border, width: 0.5)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _GenerateButton(
            label: buttonLabel,
            generating: generating,
            disabled: disabled,
            onTap: onGenerate,
          ),
          const SizedBox(height: 8),
          // T7：冷却/429 时展示后端 detail 原文（与倒计时并存）；否则显示常规提示
          if (notice != null)
            Text(
              notice!,
              key: const ValueKey('study_notice'),
              style: const TextStyle(fontSize: 11.5, color: _C.ink2),
              textAlign: TextAlign.center,
            )
          else
            Text(
              empty ? '0 页时不会调用 AI，也不会显示任何编造的统计' : 'AI 报告基于统计与页标题生成，仅供参考；不会上传你的图片与笔记正文',
              style: const TextStyle(fontSize: 11, color: _C.ink3),
              textAlign: TextAlign.center,
            ),
        ],
      ),
    );
  }
}

class _GenerateButton extends StatefulWidget {
  final String label;
  final bool generating;

  /// T7：冷却倒计时中 → 禁用（onPressed 置 null）
  final bool disabled;
  final VoidCallback onTap;
  const _GenerateButton({
    required this.label,
    required this.generating,
    required this.disabled,
    required this.onTap,
  });

  @override
  State<_GenerateButton> createState() => _GenerateButtonState();
}

class _GenerateButtonState extends State<_GenerateButton> {
  bool _pressed = false;

  bool get _enabled => !widget.generating && !widget.disabled;

  @override
  Widget build(BuildContext context) {
    // T7：改用真实 ElevatedButton —— 冷却时 onPressed 为 null（禁用可被语义/测试直接断言），
    // 背景设为透明、渐变仍由子 Container 提供，外观与冻结稿一致。
    // 按压缩放用 Listener 观察（不抢手势），仅在可点时生效。
    return Listener(
      onPointerDown: _enabled ? (_) => setState(() => _pressed = true) : null,
      onPointerUp: _enabled ? (_) => setState(() => _pressed = false) : null,
      onPointerCancel: _enabled ? (_) => setState(() => _pressed = false) : null,
      child: AnimatedScale(
        scale: _pressed ? 0.96 : 1.0, // 按压 scale(0.96)
        duration: const Duration(milliseconds: 150),
        child: ElevatedButton(
          key: const ValueKey('study_generate_button'),
          onPressed: _enabled ? widget.onTap : null,
          style: ElevatedButton.styleFrom(
            padding: EdgeInsets.zero,
            minimumSize: const Size.fromHeight(52),
            backgroundColor: Colors.transparent,
            disabledBackgroundColor: Colors.transparent,
            shadowColor: Colors.transparent,
            surfaceTintColor: Colors.transparent,
            elevation: 0,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          ),
          child: Opacity(
            opacity: widget.disabled ? 0.55 : 1.0,
            child: Container(
              height: 52,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(14),
                gradient: const LinearGradient(colors: [_C.green1, _C.green2]),
                boxShadow: [
                  BoxShadow(color: _C.green2.withValues(alpha: .34), blurRadius: 22, offset: const Offset(0, 10)),
                ],
              ),
              child: Center(
                child: widget.generating
                    ? const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)),
                          SizedBox(width: 8),
                          Text('正在生成…', style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600)),
                        ],
                      )
                    : Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.auto_awesome_rounded, size: 16, color: Colors.white),
                          const SizedBox(width: 7),
                          Text(widget.label, style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600)),
                        ],
                      ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 空态（硬要求 8：引导卡 + 不调 AI）
class _EmptyView extends StatelessWidget {
  const _EmptyView();

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 110),
      child: _GlassCard(
        child: Column(
          children: [
            Container(
              width: 86,
              height: 86,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [_C.green1.withValues(alpha: .28), AppColors.glassFill],
                ),
              ),
              child: const Icon(Icons.menu_book_rounded, size: 34, color: _C.greenDeep),
            ),
            const SizedBox(height: 14),
            const Text('还没有笔记可以分析', style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w600, color: _C.ink)),
            const SizedBox(height: 6),
            const Text(
              '先上传几页手写笔记，识别完成后\n这里会显示你的学习统计和 AI 学情报告',
              style: TextStyle(fontSize: 12.5, color: _C.ink2, height: 1.8),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

/// 错误视图
class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 80, 16, 110),
      child: Column(
        children: [
          const Icon(Icons.cloud_off_rounded, size: 48, color: _C.ink3),
          const SizedBox(height: 12),
          Text(message, style: const TextStyle(fontSize: 13, color: _C.ink2), textAlign: TextAlign.center),
          const SizedBox(height: 16),
          OutlinedButton(onPressed: onRetry, child: const Text('重试')),
        ],
      ),
    );
  }
}

class _IconBtn extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final VoidCallback onTap;
  const _IconBtn({required this.icon, required this.tooltip, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return IconButton(
      onPressed: onTap,
      tooltip: tooltip,
      icon: Icon(icon, size: 18, color: _C.ink),
      style: IconButton.styleFrom(
        backgroundColor: AppColors.glassFill,
        side: BorderSide(color: AppColors.glassBorder),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }
}
