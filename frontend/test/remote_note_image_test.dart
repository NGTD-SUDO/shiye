// RemoteNoteImage 组件测试
//
// 覆盖三条路径（对应评审问题10）：
// 1. 有 URL 时构建 Image（不依赖网络，pump 一次即构建）
// 2. 无 URL 时渲染空态（Icon，不构建 Image，不显示破图）
// 3. errorBuilder 触发时渲染失败文案（用不可达 URL 触发失败路径）

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shiye_app/shared/widgets/remote_note_image.dart';

void main() {
  group('RemoteNoteImage', () {
    testWidgets('有 URL 时构建 Image widget', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 100,
              height: 100,
              child: RemoteNoteImage(
                url: 'http://example.com/test.jpg',
              ),
            ),
          ),
        ),
      );
      await tester.pump(); // 触发构建
      // 有 URL → Image.network 应已构建（即使还在 loading）
      expect(find.byType(Image), findsOneWidget);
    });

    testWidgets('无 URL 时渲染空态（Icon，不显示破图）', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 100,
              height: 100,
              child: RemoteNoteImage(url: null),
            ),
          ),
        ),
      );
      await tester.pump();
      // 空态 → 有占位 Icon
      expect(find.byIcon(Icons.image_outlined), findsOneWidget);
      // 空态 → 不应构建 Image（避免触发网络加载/破图）
      expect(find.byType(Image), findsNothing);
    });

    testWidgets('errorBuilder 触发时渲染失败文案', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 100,
              height: 100,
              child: RemoteNoteImage(
                // 不可达 URL（端口 1 无服务监听），连接被拒绝 → errorBuilder 触发
                url: 'http://localhost:1/nonexistent.jpg',
              ),
            ),
          ),
        ),
      );
      await tester.pump();
      // runAsync 让真实异步 IO 在测试里执行（不受 FakeAsync 限制）
      await tester.runAsync(() async {
        await Future.delayed(const Duration(seconds: 3));
      });
      await tester.pump(); // 触发 errorBuilder 重绘
      // 失败文案应出现（"加载失败"或"点按重试"）
      expect(find.textContaining('加载失败'), findsWidgets);
    });
  });
}
