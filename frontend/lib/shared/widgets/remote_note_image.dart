/// 统一取图组件 — 收敛三处 Image.network 重复逻辑
///
/// 后端返回的图片 URL 已携带签名参数（e/s），有效期 15 分钟。
/// 签名过期后（15 分钟）返回 403，**不能原地重试同一 URL**（必然再次 403）。
/// 因此组件提供 [onExpired] 回调：失败态点按"刷新"时由上层重新拉接口拿新签名。
/// 签名 15 分钟过期，过期必须换新链接，不能缓存旧 URL。
library;

import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';

class RemoteNoteImage extends StatefulWidget {
  /// 图片 URL（可空）。为空时显示空态占位，不显示破图
  final String? url;

  /// 适配方式
  final BoxFit fit;

  /// 圆角（缩略图卡片用圆角，大图按需）
  final double radius;

  /// 空态占位图标尺寸
  final double emptyIconSize;

  /// 是否为缩略图模式（缩略图失败/空态用更小图标与紧凑文案）
  final bool isThumb;

  /// 是否启用缩放交互（原图详情页用 true，缩略图用 false）
  final bool enableZoom;

  /// 链接失效回调（签名过期 / 403 / 其他加载失败）。
  /// 提供此回调时，失败态按钮文案为"点按刷新"，触发上层重新拉接口拿新签名；
  /// 不提供时，失败态按钮文案为"点按重试"，原地重载同一 URL（仅对瞬时网络错误有效）。
  final VoidCallback? onExpired;

  const RemoteNoteImage({
    super.key,
    required this.url,
    this.fit = BoxFit.cover,
    this.radius = 0,
    this.emptyIconSize = 28,
    this.isThumb = false,
    this.enableZoom = false,
    this.onExpired,
  });

  @override
  State<RemoteNoteImage> createState() => _RemoteNoteImageState();
}

class _RemoteNoteImageState extends State<RemoteNoteImage> {
  int _retryToken = 0;

  @override
  void didUpdateWidget(covariant RemoteNoteImage oldWidget) {
    super.didUpdateWidget(oldWidget);
    // URL 变化时复位重试状态（列表刷新拿新签名后不应保留旧的重试计数）
    if (widget.url != oldWidget.url) {
      _retryToken = 0;
    }
  }

  @override
  Widget build(BuildContext context) {
    final url = widget.url;
    // 空态：无 URL（后端 thumb_key 为 null 或字段缺失），独立表现，不显示破图
    if (url == null || url.isEmpty) {
      return _EmptyPlaceholder(
        iconSize: widget.emptyIconSize,
        isThumb: widget.isThumb,
      );
    }

    // 用 fragment 末位变化触发 Image.network 重新加载；
    // fragment 不会发到服务端，不影响后端对 e/s 的验证
    final loadUrl = '$url#retry=$_retryToken';

    Widget image = Image.network(
      loadUrl,
      fit: widget.fit,
      loadingBuilder: (ctx, child, progress) {
        if (progress == null) return child;
        return const _LoadingShimmer();
      },
      errorBuilder: (_, _, _) => _ErrorView(
        onRetry: () {
          if (widget.onExpired != null) {
            // 上层提供了刷新回调 → 让它重新拉接口拿新签名
            widget.onExpired!();
          } else {
            // 无刷新回调 → 原地重载（仅对瞬时网络错误有效，签名过期无效）
            setState(() => _retryToken++);
          }
        },
        isThumb: widget.isThumb,
        hasRefresh: widget.onExpired != null,
      ),
    );

    if (widget.enableZoom) {
      image = InteractiveViewer(
        boundaryMargin: const EdgeInsets.all(double.infinity),
        minScale: 0.5,
        maxScale: 4.0,
        child: image,
      );
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(widget.radius),
      child: image,
    );
  }
}

/// 加载中骨架：淡灰底 + 微光呼吸
class _LoadingShimmer extends StatelessWidget {
  const _LoadingShimmer();

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.surfaceMuted,
      child: const Center(
        child: Icon(
          Icons.image_outlined,
          color: AppColors.inkTertiary,
          size: 24,
        ),
      ),
    );
  }
}

/// 失败态：真实文案 + 可点按（禁止假图/假插画）
class _ErrorView extends StatelessWidget {
  final VoidCallback onRetry;
  final bool isThumb;
  /// 是否有上层刷新回调（决定文案是"刷新"还是"重试"）
  final bool hasRefresh;
  const _ErrorView({
    required this.onRetry,
    required this.isThumb,
    required this.hasRefresh,
  });

  String get _label => hasRefresh ? '点按刷新' : '加载失败，点按重试';

  @override
  Widget build(BuildContext context) {
    if (isThumb) {
      return GestureDetector(
        onTap: onRetry,
        child: Container(
          color: AppColors.surfaceMuted,
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.broken_image_outlined,
                    color: AppColors.inkTertiary, size: 18),
                const SizedBox(height: 2),
                Text(
                  hasRefresh ? '已过期' : '加载失败',
                  style: const TextStyle(fontSize: 9, color: AppColors.inkTertiary),
                ),
              ],
            ),
          ),
        ),
      );
    }
    return GestureDetector(
      onTap: onRetry,
      child: Container(
        color: AppColors.surfaceMuted,
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.broken_image_outlined,
                  color: AppColors.inkTertiary, size: 36),
              const SizedBox(height: 8),
              Text(
                _label,
                style: const TextStyle(fontSize: 12, color: AppColors.inkTertiary),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 空态占位：无 URL 时的独立表现
class _EmptyPlaceholder extends StatelessWidget {
  final double iconSize;
  final bool isThumb;
  const _EmptyPlaceholder({required this.iconSize, required this.isThumb});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.surfaceMuted,
      child: Center(
        child: Icon(
          Icons.image_outlined,
          color: AppColors.inkTertiary,
          size: isThumb ? 20 : iconSize,
        ),
      ),
    );
  }
}
