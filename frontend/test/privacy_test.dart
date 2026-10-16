/// T12 隐私合规 widget 测试
///
/// 覆盖任务书第三节的 10 条前端验收：
/// 1 首次弹窗 + 正文可见 / 2 **未同意零采集（网络调用 == 0）** / 3 返回键不可关闭 /
/// 4 同意写入 + 进入正常流程 / 5 二次启动不再弹窗 / 6 入口 ≤4 次点击可达 /
/// 7 拒绝不写入标记（且真调 SystemNavigator.pop）/ 8 4 份文档非空 /
/// 9 撤回同意重置状态 / 10 政策正文含"百度""DeepSeek"
/// 额外（本批新做的注销功能）：11 注销二次确认 + 真调接口 + 清 token / 12 注销失败不谎报
library;

import 'dart:io';

import 'package:flutter/foundation.dart' show SynchronousFuture;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show AssetBundle, ByteData, MethodCall, SystemChannels;
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:shiye_app/core/api/api_client.dart';
import 'package:shiye_app/core/auth_provider.dart';
import 'package:shiye_app/core/privacy_service.dart';
import 'package:shiye_app/features/auth/login_page.dart';
import 'package:shiye_app/features/home/home_page.dart';
import 'package:shiye_app/features/home/profile_page.dart';
import 'package:shiye_app/features/legal/legal_doc_page.dart';
import 'package:shiye_app/features/pages/page_upload_page.dart';
import 'package:shiye_app/main.dart';

/// 桩 ApiClient：统计**网络调用次数**（零采集的硬证明）
class _StubApiClient extends ApiClient {
  _StubApiClient() : super.forTesting();

  /// 已发生的网络请求次数（本地读取如 restoreToken 不计）
  int networkCalls = 0;
  bool loggedIn = false;
  bool deleteMeFails = false;
  int deleteMeCalls = 0;

  @override
  bool get isLoggedIn => loggedIn;

  @override
  Future<void> restoreToken() async {
    // 本地读取，不算网络请求
  }

  @override
  Future<void> clearToken() async {
    loggedIn = false;
  }

  @override
  Future<Map<String, dynamic>> getMe() async {
    networkCalls++;
    return {
      'id': 1,
      'nickname': '测试用户',
      'avatar_url': '',
      'created_at': '2026-09-19T00:00:00Z',
    };
  }

  @override
  Future<void> deleteMe() async {
    deleteMeCalls++;
    networkCalls++;
    if (deleteMeFails) {
      throw ApiException('服务暂时不可用，请稍后重试');
    }
    loggedIn = false;
  }

  @override
  Future<List<Map<String, dynamic>>> listSubjects() async {
    networkCalls++;
    return [];
  }
}

void _bigView(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 2600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

/// 同步资产 bundle：直接从磁盘同步读。
///
/// widget 测试运行在 fake-async 区，`rootBundle.loadString` 的异步加载**永远不会完成**
/// （实测：预热后在测试 zone 里仍拿不到值）。用同步 bundle 覆盖 `DefaultAssetBundle`，
/// 页面就会在首帧渲染出**真实文档内容**，断言才有意义（同步 IO 在测试 zone 是允许的）。
class _SyncAssetBundle extends AssetBundle {
  @override
  Future<ByteData> load(String key) async => throw UnimplementedError('仅用于 loadString');

  @override
  Future<String> loadString(String key, {bool cache = true}) =>
      SynchronousFuture(File(key).readAsStringSync());
}

/// 用同步 bundle 承载法律文档页（键 = 相对包根的资源路径，flutter test 的 CWD 即包根）
Widget _legalHost(Widget page) => MaterialApp(
      home: DefaultAssetBundle(bundle: _SyncAssetBundle(), child: page),
    );

/// 滚动到目标（长文档页里页脚在屏幕外，必须先滚出来才能点击）
Future<void> _scrollTo(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    600,
    maxScrolls: 80,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pump();
}

Future<void> _pumpApp(WidgetTester tester, _StubApiClient stub, {int extraPumps = 3}) async {
  _bigView(tester);
  await tester.pumpWidget(ShiyeApp(api: stub));
  for (var i = 0; i < extraPumps; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

Finder get _consentDialog => find.byKey(const ValueKey('privacy_consent_dialog'));

/// 复位本地同意状态（PrivacyService 是单例，必须按用例复位，避免跨用例残留）
Future<void> _resetConsent({bool? agreed}) async {
  SharedPreferences.setMockInitialValues(
    agreed == null ? {} : {PrivacyService.agreedKey: agreed},
  );
  await PrivacyService.instance.load();
}

void main() {
  setUp(() async {
    await _resetConsent(); // 每个用例独立前置：**未同意**（无标记）
  });

  testWidgets('1. 首次启动弹出同意弹窗，正文可见且含第三方披露，且无默认勾选', (tester) async {
    final stub = _StubApiClient();
    await _pumpApp(tester, stub);

    expect(_consentDialog, findsOneWidget);
    expect(find.text('隐私政策'), findsWidgets);
    // 正文（可滚动）可见 + 第三方披露
    expect(find.byKey(const ValueKey('privacy_consent_body')), findsOneWidget);
    expect(find.textContaining('百度智能云', findRichText: true), findsOneWidget);
    expect(find.textContaining('DeepSeek', findRichText: true), findsOneWidget);
    // 两个按钮
    expect(find.text('同意'), findsOneWidget);
    expect(find.text('拒绝并退出APP'), findsOneWidget);
    // 禁止默认勾选：弹窗里不应存在任何勾选框
    expect(find.byType(Checkbox), findsNothing);
    expect(find.byType(CheckboxListTile), findsNothing);
    expect(find.byType(Switch), findsNothing);
  });

  testWidgets('2. 未同意时零采集：网络调用 == 0，且不生成设备标识', (tester) async {
    final stub = _StubApiClient()..loggedIn = true; // 即使本地有"登录态"，也不得发请求
    await _pumpApp(tester, stub, extraPumps: 6);

    expect(_consentDialog, findsOneWidget);
    expect(stub.networkCalls, 0, reason: '未同意前不得发起任何网络请求');
    expect(stub.deleteMeCalls, 0);

    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('shiye_device_id'), isNull, reason: '未同意前不得读取/生成设备标识');
    expect(prefs.getBool(PrivacyService.agreedKey), isNull, reason: '未同意时不应写入任何标记');
  });

  testWidgets('3. 弹窗不可通过返回键关闭', (tester) async {
    final stub = _StubApiClient();
    await _pumpApp(tester, stub);
    expect(_consentDialog, findsOneWidget);

    // 模拟系统返回键
    await tester.binding.handlePopRoute();
    await tester.pump(const Duration(milliseconds: 300));

    expect(_consentDialog, findsOneWidget, reason: 'PopScope(canPop:false) 必须拦住返回键');
  });

  testWidgets('4. 点【同意】→ 写入 SharedPreferences 并进入正常流程', (tester) async {
    final stub = _StubApiClient();
    await _pumpApp(tester, stub);

    await tester.tap(find.byKey(const ValueKey('privacy_agree_button')));
    for (var i = 0; i < 6; i++) {
      await tester.pump(const Duration(milliseconds: 80));
    }

    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getBool(PrivacyService.agreedKey), isTrue, reason: '同意后必须落盘');
    expect(_consentDialog, findsNothing);
    // 正常流程：无 token → 登录页
    expect(find.byType(LoginPage), findsOneWidget);
  });

  testWidgets('5. 二次启动（已有同意标记）不再弹窗', (tester) async {
    await _resetConsent(agreed: true);
    final stub = _StubApiClient();
    await _pumpApp(tester, stub, extraPumps: 6);

    expect(_consentDialog, findsNothing);
    expect(find.byType(LoginPage), findsOneWidget);
  });

  testWidgets('6. 「我的 → 隐私政策」≤4 次点击可达（实测 2 次）', (tester) async {
    await _resetConsent(agreed: true);
    final stub = _StubApiClient()..loggedIn = true;
    await _pumpApp(tester, stub, extraPumps: 8);
    expect(find.byType(HomePage), findsOneWidget);

    // 点击 1：底部「我的」
    await tester.tap(find.text('我的'));
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(milliseconds: 80));
    }
    expect(find.byKey(const ValueKey('entry_privacy_policy')), findsOneWidget);

    // 点击 2：隐私政策
    await tester.tap(find.byKey(const ValueKey('entry_privacy_policy')));
    for (var i = 0; i < 6; i++) {
      await tester.pump(const Duration(milliseconds: 80));
    }
    expect(find.byType(PrivacyPolicyPage), findsOneWidget);
    // 说明：本用例只验证**入口可达**；文档正文渲染由用例 8/10（注入同步 bundle）断言
  });

  testWidgets('7. 点【拒绝并退出APP】→ 调 SystemNavigator.pop（非 exit(0)）且不写入标记', (tester) async {
    final platformCalls = <String>[];
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (MethodCall call) async {
      platformCalls.add(call.method);
      return null;
    });
    addTearDown(() {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null);
    });

    final stub = _StubApiClient();
    await _pumpApp(tester, stub);

    await tester.tap(find.byKey(const ValueKey('privacy_reject_button')));
    await tester.pump(); // 让 SnackBar 出现
    expect(find.textContaining('不同意将无法使用拾页'), findsWidgets);

    // 等退出延时到点
    await tester.pump(const Duration(milliseconds: 1300));

    expect(platformCalls, contains('SystemNavigator.pop'), reason: '必须走 SystemNavigator.pop');
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getBool(PrivacyService.agreedKey), isNull, reason: '拒绝不得写入任何标记');
  });

  testWidgets('8. 4 份法律文档页均可打开且内容非空', (tester) async {
    final cases = <String, String>{
      '隐私政策': '拾页',
      '用户协议': '用户协议',
      '第三方信息共享清单': '百度',
      '个人信息收集清单': '个人信息',
    };
    final pages = <String, Widget>{
      '隐私政策': const PrivacyPolicyPage(),
      '用户协议': const UserAgreementPage(),
      '第三方信息共享清单': const ThirdPartyListPage(),
      '个人信息收集清单': const DataCollectionListPage(),
    };

    for (final entry in pages.entries) {
      await tester.pumpWidget(_legalHost(entry.value));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 60));
      }
      expect(find.text(entry.key), findsWidgets, reason: '${entry.key} 页标题');
      expect(
        find.textContaining(cases[entry.key]!, findRichText: true),
        findsWidgets,
        reason: '${entry.key} 正文应非空（应含「${cases[entry.key]}」）',
      );
      expect(find.textContaining('文档加载失败'), findsNothing);
    }
  });

  testWidgets('9. 撤回同意 → 清除标记，且再次启动会重新弹窗（状态重置）', (tester) async {
    await _resetConsent(agreed: true);
    _bigView(tester);
    await tester.pumpWidget(_legalHost(const PrivacyPolicyPage()));
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(milliseconds: 60));
    }
    // 撤回入口在长文档页底部：先滚动到可见位置再点击
    await _scrollTo(tester, find.byKey(const ValueKey('withdraw_consent_entry')));
    expect(find.byKey(const ValueKey('withdraw_consent_entry')), findsOneWidget,
        reason: '隐私政策页底部必须有撤回入口');

    // 撤回 → 二次确认
    await tester.tap(find.byKey(const ValueKey('withdraw_consent_entry')));
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(milliseconds: 80));
    }
    expect(find.text('撤回后需重新同意才能使用拾页'), findsWidgets);
    expect(PrivacyService.instance.agreed, isTrue, reason: '未确认前不得改动状态');

    await tester.tap(find.byKey(const ValueKey('withdraw_confirm_button')));
    for (var i = 0; i < 8; i++) {
      await tester.pump(const Duration(milliseconds: 80));
    }

    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getBool(PrivacyService.agreedKey), isNull, reason: '撤回后标记必须被清除');
    expect(PrivacyService.instance.agreed, isFalse);

    await tester.pump(const Duration(seconds: 5)); // 清 SnackBar 计时器

    // 再次启动 → 重新弹同意弹窗（状态真的被重置了）
    final stub = _StubApiClient();
    await _pumpApp(tester, stub, extraPumps: 6);
    expect(_consentDialog, findsOneWidget, reason: '撤回后再次启动必须重新要求同意');
    await tester.pump(const Duration(seconds: 5));
    await tester.pump();
  });

  testWidgets('10. 隐私政策正文含「百度」「DeepSeek」（防漏披露）', (tester) async {
    await _resetConsent(agreed: true);
    await tester.pumpWidget(_legalHost(const PrivacyPolicyPage()));
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(milliseconds: 60));
    }
    expect(find.textContaining('百度', findRichText: true), findsWidgets);
    expect(find.textContaining('DeepSeek', findRichText: true), findsWidgets);
  });

  testWidgets('11. 注销账号：二次确认含「此操作不可恢复」，确认后真调接口并清 token', (tester) async {
    final stub = _StubApiClient()..loggedIn = true;
    _bigView(tester); // 视口放大，保证 ListView 里的入口都被构建
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AuthProvider(api: stub),
        child: MaterialApp(home: ProfilePage(api: stub)),
      ),
    );
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(milliseconds: 80));
    }

    await tester.tap(find.byKey(const ValueKey('delete_account_entry')));
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(milliseconds: 80));
    }
    expect(find.textContaining('此操作不可恢复'), findsWidgets);
    expect(stub.deleteMeCalls, 0, reason: '未确认前不得调用注销接口');

    await tester.tap(find.byKey(const ValueKey('delete_account_confirm_button')));
    for (var i = 0; i < 8; i++) {
      await tester.pump(const Duration(milliseconds: 80));
    }

    expect(stub.deleteMeCalls, 1);
    expect(stub.loggedIn, isFalse, reason: '注销成功后必须清除本地 token');
    expect(find.text('账号已注销'), findsWidgets);
  });

  testWidgets('12. 注销失败：如实报错，不谎报成功', (tester) async {
    final stub = _StubApiClient()
      ..loggedIn = true
      ..deleteMeFails = true;
    _bigView(tester); // 视口放大，保证 ListView 里的入口都被构建
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AuthProvider(api: stub),
        child: MaterialApp(home: ProfilePage(api: stub)),
      ),
    );
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(milliseconds: 80));
    }

    await tester.tap(find.byKey(const ValueKey('delete_account_entry')));
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(milliseconds: 80));
    }
    await tester.tap(find.byKey(const ValueKey('delete_account_confirm_button')));
    for (var i = 0; i < 8; i++) {
      await tester.pump(const Duration(milliseconds: 80));
    }

    expect(stub.deleteMeCalls, 1);
    expect(find.textContaining('注销失败'), findsWidgets);
    expect(find.text('账号已注销'), findsNothing);
    expect(stub.loggedIn, isTrue, reason: '注销失败时不得清除登录态');

    await tester.pump(const Duration(seconds: 5)); // 清 SnackBar 计时器
    await tester.pump();
  });

  // ==================== T12 收尾 ====================

  testWidgets('13. kLegalWebUrl 非空且指向 /legal；按钮复制的内容就是它', (tester) async {
    expect(kLegalWebUrl, isNotEmpty, reason: '在线地址不能是空串');
    expect(kLegalWebUrl.endsWith('/legal'), isTrue);

    final platformCalls = <MethodCall>[];
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (MethodCall call) async {
      platformCalls.add(call);
      return null;
    });
    addTearDown(() {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null);
    });

    _bigView(tester);
    await tester.pumpWidget(_legalHost(const PrivacyPolicyPage()));
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(milliseconds: 60));
    }

    // 按钮在文档底部，先滚到可见处
    await _scrollTo(tester, find.text('在浏览器中打开'));
    await tester.tap(find.text('在浏览器中打开'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    final copies = platformCalls.where((c) => c.method == 'Clipboard.setData').toList();
    expect(copies, isNotEmpty, reason: '应真的写入剪贴板');
    expect((copies.last.arguments as Map)['text'], kLegalWebUrl, reason: '复制内容必须是该常量');
    expect(find.textContaining('链接已复制'), findsWidgets);

    await tester.pump(const Duration(seconds: 5)); // 清 SnackBar 计时器
    await tester.pump();
  });

  testWidgets('14. 底部栏 4 个入口正常，且首页「＋ 拍照」可进入上传页', (tester) async {
    await _resetConsent(agreed: true);
    final stub = _StubApiClient()..loggedIn = true;
    await _pumpApp(tester, stub, extraPumps: 8);

    expect(find.byType(HomePage), findsOneWidget);
    // T13-3：导航由 5 Tab 改 4 Tab —— 「拍照」已从底部栏移除（迁到首页右上角），
    // 故这里只校验剩下 4 个入口未退化（原断言的"不溢出"意图保持不变）。
    for (final label in ['首页', '搜索', '学情', '我的']) {
      expect(find.text(label), findsOneWidget, reason: '底部栏缺少「$label」');
    }
    // 修复前这里会拿到 RenderFlex overflowed；现在不应有任何异常
    expect(tester.takeException(), isNull, reason: '底部栏不应再溢出');

    // 拍照入口（迁移后）＝ 首页右上角「＋ 拍照」；点击应能推入上传页（**功能未丢**）
    await tester.tap(find.text('＋ 拍照'));
    for (var i = 0; i < 6; i++) {
      await tester.pump(const Duration(milliseconds: 80));
    }
    expect(find.byType(PageUploadPage), findsOneWidget);
  });
}
