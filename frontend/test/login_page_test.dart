/// 登录页 widget 测试：设备标识两次同值 + 邀请码空不发请求
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:shiye_app/core/auth_provider.dart';
import 'package:shiye_app/core/device_id.dart';
import 'package:shiye_app/features/auth/login_page.dart';

/// 假 AuthProvider：记录 devLogin 是否被调用及参数
class _FakeAuthProvider extends AuthProvider {
  bool devLoginCalled = false;
  String? lastOpenid;
  String? lastNickname;
  String? lastInviteCode;

  @override
  Future<void> devLogin(String openid, {String? nickname, String? inviteCode}) async {
    devLoginCalled = true;
    lastOpenid = openid;
    lastNickname = nickname;
    lastInviteCode = inviteCode;
  }
}

void main() {
  testWidgets('设备标识：两次调用 getDeviceId 返回同一值，且形如 dev_ + 32 位 hex',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final id1 = await getDeviceId();
    final id2 = await getDeviceId();
    expect(id1, id2);
    expect(id1, startsWith('dev_'));
    final hex = id1.substring(4);
    expect(hex.length, 32);
    expect(RegExp(r'^[0-9a-f]{32}$').hasMatch(hex), isTrue, reason: '应为 32 位 hex');
  });

  testWidgets('登录页：邀请码为空时点登录 → 出现中文提示且不发请求',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final fake = _FakeAuthProvider();
    await tester.pumpWidget(
      ChangeNotifierProvider<AuthProvider>.value(
        value: fake,
        child: const MaterialApp(home: LoginPage()),
      ),
    );
    // 不输入邀请码，直接点登录
    await tester.tap(find.widgetWithText(FilledButton, '登录'));
    await tester.pump();
    // 不应发请求
    expect(fake.devLoginCalled, isFalse, reason: '邀请码为空时不应调用 devLogin');
    // 应出现中文提示
    expect(find.text('请输入邀请码'), findsOneWidget, reason: '应出现"请输入邀请码"提示');
  });
}
