/// 交互动效（T13-2 §3.7）—— 只做三件事：列表交错入场、按压缩放回弹、Tab spring。
///
/// 实现要点：一律用 `AnimationController` + `Interval`（或 `AnimatedScale`），
/// **不用 `Future.delayed`/`Timer`** —— 否则 widget 测试结束时会报 "A Timer is still pending"。
/// 按压缩放用 `Listener`（不进手势竞技场）包住既有 `InkWell`，避免抢走点击。
library;

import 'package:flutter/material.dart';

/// 列表项「交错入场」：第 [index] 项比前一项晚 [stepMs] 毫秒起步。
///
/// 动画：opacity 0→1、上移 13px→0、scale .975→1（对齐 demo 的 `cardIn`）。
class StaggeredIn extends StatefulWidget {
  final int index;
  final Widget child;

  /// 每项错峰毫秒数（demo：卡片 50ms / 页面行 45ms）
  final int stepMs;

  const StaggeredIn({
    super.key,
    required this.index,
    required this.child,
    this.stepMs = 50,
  });

  @override
  State<StaggeredIn> createState() => _StaggeredInState();
}

class _StaggeredInState extends State<StaggeredIn> with SingleTickerProviderStateMixin {
  static const int _durMs = 450;

  late final int _delayMs = widget.index * widget.stepMs;
  late final int _totalMs = _durMs + _delayMs;

  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: Duration(milliseconds: _totalMs),
  )..forward();

  late final Animation<double> _t = CurvedAnimation(
    parent: _c,
    curve: Interval(_delayMs / _totalMs, 1.0, curve: Curves.easeOutCubic),
  );

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _t,
      child: widget.child,
      builder: (_, child) {
        final v = _t.value;
        return Opacity(
          opacity: v,
          child: Transform.translate(
            offset: Offset(0, (1 - v) * 13),
            child: Transform.scale(scale: .975 + .025 * v, child: child),
          ),
        );
      },
    );
  }
}

/// 按压缩放回弹：按住缩到 [pressedScale]，松开回 1。
///
/// 用 `Listener` 而非 `GestureDetector` —— 不参与手势竞技场，不会抢走内层 `InkWell` 的点击。
class PressableScale extends StatefulWidget {
  final Widget child;
  final double pressedScale;

  const PressableScale({
    super.key,
    required this.child,
    this.pressedScale = .976,
  });

  @override
  State<PressableScale> createState() => _PressableScaleState();
}

class _PressableScaleState extends State<PressableScale> {
  bool _down = false;

  void _set(bool v) {
    if (_down != v) setState(() => _down = v);
  }

  @override
  Widget build(BuildContext context) {
    return Listener(
      onPointerDown: (_) => _set(true),
      onPointerUp: (_) => _set(false),
      onPointerCancel: (_) => _set(false),
      child: AnimatedScale(
        scale: _down ? widget.pressedScale : 1.0,
        duration: const Duration(milliseconds: 160),
        curve: Curves.easeOut,
        child: widget.child,
      ),
    );
  }
}
