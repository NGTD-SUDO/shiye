/// T4-3 异常→中文文案映射单测
///
/// 验证 5 类异常映射为可操作中文文案：
/// - SocketException / http.ClientException →「无法连接服务器…」
/// - TimeoutException →「请求超时…」/「上传超时…」
/// - FormatException →「服务器返回数据异常」
/// - ApiException → 保留后端 detail 原文
/// - 其它 →「操作失败…」/「上传失败…」
library;

import 'dart:async';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:shiye_app/core/api/api_client.dart';

void main() {
  group('mapExceptionToMessage 统一映射', () {
    test('ApiException 优先保留后端 detail 原文', () {
      final e = ApiException('学科下已存在同名章');
      expect(mapExceptionToMessage(e), '学科下已存在同名章');
    });

    test('SocketException → 无法连接服务器', () {
      final e = SocketException('Failed host lookup');
      expect(mapExceptionToMessage(e), '无法连接服务器，请检查网络或确认服务已启动');
    });

    test('http.ClientException → 无法连接服务器', () {
      final e = http.ClientException('Connection refused');
      expect(mapExceptionToMessage(e), '无法连接服务器，请检查网络或确认服务已启动');
    });

    test('TimeoutException → 请求超时', () {
      final e = TimeoutException('timed out');
      final msg = mapExceptionToMessage(e);
      expect(msg, contains('请求超时'));
      expect(msg, contains('请检查网络后重试'));
    });

    test('TimeoutException 上传场景 → 上传超时', () {
      final e = TimeoutException('timed out');
      final msg = mapExceptionToMessage(e, isUpload: true);
      expect(msg, contains('上传超时'));
      expect(msg, contains('请检查网络后重试'));
    });

    test('FormatException → 服务器返回数据异常', () {
      const e = FormatException('Not JSON');
      expect(mapExceptionToMessage(e), '服务器返回数据异常');
    });

    test('其它异常 → 操作失败兜底文案', () {
      final e = StateError('something weird');
      final msg = mapExceptionToMessage(e);
      expect(msg, '操作失败，请稍后重试');
    });

    test('其它异常 上传场景 → 上传失败兜底文案', () {
      final e = StateError('something weird');
      final msg = mapExceptionToMessage(e, isUpload: true);
      expect(msg, '上传失败，请稍后重试');
    });
  });
}
