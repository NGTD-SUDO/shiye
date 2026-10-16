/// 可复用学科卡片 — 纸质质感 + 左侧彩色条
library;

import 'package:flutter/material.dart';
import '../../core/models/subject.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import 'motion.dart';

class SubjectCard extends StatelessWidget {
  final Subject subject;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;

  const SubjectCard({
    super.key,
    required this.subject,
    required this.onTap,
    this.onLongPress,
  });

  /// 将十六进制色字符串转为 Color
  Color get _accentColor {
    final hex = subject.color;
    if (hex.startsWith('#')) {
      final v = int.tryParse(hex.substring(1), radix: 16);
      if (v != null) return Color(v).withValues(alpha: 1);
    }
    return AppColors.primary;
  }

  @override
  Widget build(BuildContext context) {
    final card = Card(
      child: InkWell(
        onTap: onTap,
        onLongPress: onLongPress,
        borderRadius: BorderRadius.circular(AppRadius.card),
        child: ClipPath(
          clipper: _LeftBarClipper(),
          child: Stack(
            children: [
              // 底部横线纹装饰
              Positioned(
                left: 0,
                right: 0,
                bottom: 0,
                child: CustomPaint(
                  size: const Size(double.infinity, 36),
                  painter: _LinePatternPainter(color: _accentColor),
                ),
              ),
              // 内容
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.lg + 4,
                  AppSpacing.lg,
                  AppSpacing.lg,
                  AppSpacing.xxl + 4,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      subject.name,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: AppColors.ink,
                          ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Row(
                      children: [
                        _MetaChip(label: '${subject.pageCount} 页'),
                        const SizedBox(width: AppSpacing.sm),
                        _MetaChip(label: '${subject.chapterCount} 章'),
                        const Spacer(),
                        if (subject.progress > 0)
                          Text(
                            '${(subject.progress * 100).round()}%',
                            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                  color: _accentColor,
                                  fontWeight: FontWeight.w600,
                                ),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
              // 左侧 3px 彩色条
              Positioned(
                left: 0,
                top: 0,
                bottom: 0,
                child: Container(width: 3, color: _accentColor),
              ),
            ],
          ),
        ),
      ),
    );
    // §3.7 按压缩放回弹（demo `.subj:active` = .976）
    return PressableScale(child: card);
  }
}

class _MetaChip extends StatelessWidget {
  final String label;
  const _MetaChip({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.surfaceMuted,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: AppColors.inkTertiary,
            ),
      ),
    );
  }
}

/// 让左上/左下圆角保留，避免彩色条破坏圆角
class _LeftBarClipper extends CustomClipper<Path> {
  @override
  Path getClip(Size size) {
    final r = AppRadius.card;
    final path = Path()
      ..moveTo(0, r)
      ..arcToPoint(Offset(r, 0), radius: Radius.circular(r))
      ..lineTo(size.width - r, 0)
      ..arcToPoint(Offset(size.width, r), radius: Radius.circular(r))
      ..lineTo(size.width, size.height - r)
      ..arcToPoint(Offset(size.width - r, size.height), radius: Radius.circular(r))
      ..lineTo(r, size.height)
      ..arcToPoint(Offset(0, size.height - r), radius: Radius.circular(r))
      ..close();
    return path;
  }

  @override
  bool shouldReclip(covariant CustomClipper<Path> oldClipper) => false;
}

/// 底部横线纹装饰
class _LinePatternPainter extends CustomPainter {
  final Color color;
  _LinePatternPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color.withValues(alpha: 0.12)
      ..strokeWidth = 1;
    const gap = 6.0;
    for (var x = -size.height; x < size.width + size.height; x += gap) {
      canvas.drawLine(
        Offset(x, 0),
        Offset(x + size.height, size.height),
        paint,
      );
    }
    // 底部加重线
    final baseLine = Paint()
      ..color = color.withValues(alpha: 0.18)
      ..strokeWidth = 1;
    canvas.drawLine(Offset(0, size.height - 0.5), Offset(size.width, size.height - 0.5), baseLine);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
