/// 设备标识生成与持久化 — 用于开发模式登录
///
/// 卸载重装会换标识（数据会表现为新账号），内测可接受。
/// 用 Random.secure() 生成，不允许用时间戳/自增等可猜值。
library;

import 'dart:math';
import 'package:shared_preferences/shared_preferences.dart';

const _deviceIdKey = 'shiye_device_id';

/// 获取（必要时生成并持久化）设备标识，形如 dev_<32位随机hex>
///
/// 首次调用时生成并写入 SharedPreferences；后续调用直接读取。
/// 卸载重装会换标识（数据表现为新账号）。
Future<String> getDeviceId() async {
  final prefs = await SharedPreferences.getInstance();
  final existing = prefs.getString(_deviceIdKey);
  if (existing != null && existing.isNotEmpty) {
    return existing;
  }
  // 用 Random.secure() 生成 16 字节（128 位）随机数，转成 32 位 hex
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  final id = 'dev_$hex';
  await prefs.setString(_deviceIdKey, id);
  return id;
}
