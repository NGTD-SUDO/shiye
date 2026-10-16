/// 认证状态管理 — Provider 模式
///
/// T4：新增 [setNickname] 供「我的」页改昵称后同步缓存与刷新监听者
library;

import 'package:flutter/material.dart';
import 'api/api_client.dart';

class AuthProvider extends ChangeNotifier {
  final ApiClient _api;

  /// 测试可注入桩 ApiClient；生产用单例 [ApiClient()]
  AuthProvider({ApiClient? api}) : _api = api ?? ApiClient();

  bool _initialized = false;
  bool get initialized => _initialized;

  bool get isLoggedIn => _api.isLoggedIn;
  String? get token => _api.token;

  Map<String, dynamic>? _user;
  Map<String, dynamic>? get user => _user;

  String? get nickname => _user?['nickname'] as String?;

  /// 启动时恢复 token
  Future<void> init() async {
    await _api.restoreToken();
    if (_api.isLoggedIn) {
      try {
        _user = await _api.getMe();
      } catch (_) {
        await _api.clearToken();
      }
    }
    _initialized = true;
    notifyListeners();
  }

  /// 开发模式登录
  Future<void> devLogin(String openid, {String? nickname, String? inviteCode}) async {
    final data = await _api.devLogin(openid, nickname: nickname, inviteCode: inviteCode);
    _user = {'id': data['user_id'], 'nickname': data['nickname']};
    notifyListeners();
  }

  /// 微信登录
  Future<void> wechatLogin(String code) async {
    final data = await _api.wechatLogin(code);
    _user = {'id': data['user_id'], 'nickname': data['nickname']};
    notifyListeners();
  }

  /// 同步更新昵称缓存并通知监听者（T4-5）
  ///
  /// 由「我的」页在 [ApiClient.updateMe] 成功后调用，避免界面与 AuthProvider
  /// 缓存不一致；后续 init() 重新 getMe 会从后端拿到最新值。
  void setNickname(String newNickname) {
    if (_user != null) {
      _user = Map<String, dynamic>.from(_user!)..['nickname'] = newNickname;
      notifyListeners();
    }
  }

  /// 登出
  Future<void> logout() async {
    await _api.clearToken();
    _user = null;
    notifyListeners();
  }
}
