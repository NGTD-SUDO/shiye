/// 隐私同意状态管理（T12-1 / T12-2 / T12-5）
///
/// - key 带版本号：政策大改（收集范围/共享对象变化）后把版本号 +1，即可重新要求同意
/// - 点【拒绝并退出】**不写入任何标记** → 下次启动重新弹窗
/// - 做成 [ChangeNotifier] 单例：撤回同意后 AppRouter 会自动回到同意弹窗（无需重启）
///
/// ⚠️ 零采集：本文件只读写**本地** SharedPreferences，不发网络请求、不读设备标识。
library;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class PrivacyService extends ChangeNotifier {
  /// 同意状态 key（带版本号，v1）
  static const String agreedKey = 'shiye_privacy_agreed_v1';

  static final PrivacyService instance = PrivacyService._();

  PrivacyService._();

  bool? _agreed;

  /// 同意状态：`null` = 尚未读取本地存储（启动瞬间），`false` = 未同意，`true` = 已同意
  bool? get agreed => _agreed;

  /// 读取本地同意状态（只读本地，不发网络请求）
  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    _agreed = prefs.getBool(agreedKey) ?? false;
    notifyListeners();
  }

  /// 用户点了【同意】：写入标记并进入正常流程
  Future<void> agree() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(agreedKey, true);
    _agreed = true;
    notifyListeners();
  }

  /// 撤回同意（T12-5）：清除标记 → 下次（或立即）重新要求同意
  ///
  /// 【拒绝并退出】走的是另一条路径，**不调用本方法**（不写入、也不清除，保持"从未同意"）。
  Future<void> withdraw() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(agreedKey);
    _agreed = false;
    notifyListeners();
  }
}
