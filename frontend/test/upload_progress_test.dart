/// T4-2 上传进度纯函数单测
///
/// 验证：单调不减、完成时恰好为 1、总字节为 0 不出现 NaN
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:shiye_app/core/upload_progress.dart';

void main() {
  group('uploadProgress 纯函数', () {
    test('总字节为 0 时返回 0（不出现 NaN）', () {
      expect(uploadProgress(0, 0), 0.0);
      expect(uploadProgress(100, 0), 0.0);
      // 总字节为负也按 0 处理
      expect(uploadProgress(0, -1), 0.0);
    });

    test('完成时恰好为 1', () {
      expect(uploadProgress(1000, 1000), 1.0);
      expect(uploadProgress(500, 500), 1.0);
    });

    test('已发送超过总字节时截断为 1', () {
      expect(uploadProgress(2000, 1000), 1.0);
    });

    test('已发送为负数时按 0 处理', () {
      expect(uploadProgress(-10, 100), 0.0);
    });

    test('单调不减（模拟上传过程）', () {
      final progresses = <double>[];
      for (var sent = 0; sent <= 1000; sent += 100) {
        progresses.add(uploadProgress(sent, 1000));
      }
      // 0.0 → 0.1 → 0.2 → ... → 1.0
      expect(progresses, [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]);
      // 显式验证单调不减
      for (var i = 1; i < progresses.length; i++) {
        expect(progresses[i], greaterThanOrEqualTo(progresses[i - 1]),
            reason: '进度应单调不减');
      }
    });

    test('中间值正确（非整除情况）', () {
      // 7 字节中的 3 字节 = 3/7 ≈ 0.4286
      final p = uploadProgress(3, 7);
      expect(p, closeTo(3.0 / 7.0, 1e-9));
      expect(p, lessThan(1.0));
      expect(p, greaterThan(0.0));
    });
  });
}
