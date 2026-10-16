/// 后端 API 客户端 — 封装全部接口调用
///
/// T4 改造：
/// - 所有请求加超时（普通 15s / 上传 60s，可由编译期环境变量覆盖）
/// - 统一异常→中文文案映射（[mapExceptionToMessage]），UI 不再拼 `$e`
/// - 上传方法支持真实字节进度回调（[uploadPage]）
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart' show debugPrint;
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ApiClient {
  static const _baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );

  /// 普通请求（GET/POST/PATCH/DELETE，JSON）超时秒数（T4-1）
  static const _normalTimeoutSeconds = int.fromEnvironment(
    'API_NORMAL_TIMEOUT_SECONDS',
    defaultValue: 15,
  );

  /// 图片上传（multipart）超时秒数（T4-1）：大图 + 弱网放宽
  static const _uploadTimeoutSeconds = int.fromEnvironment(
    'API_UPLOAD_TIMEOUT_SECONDS',
    defaultValue: 60,
  );

  /// 学情报告超时秒数（T5）：服务端同步生成约 5~15s，单独放宽到 60s
  static const _studyReportTimeoutSeconds = int.fromEnvironment(
    'API_STUDY_REPORT_TIMEOUT_SECONDS',
    defaultValue: 60,
  );

  /// AI 测评（出题 / 判分）超时秒数（T10）：与学情报告同级的同步 AI 调用，同样放宽到 60s
  static const _quizTimeoutSeconds = int.fromEnvironment(
    'API_QUIZ_TIMEOUT_SECONDS',
    defaultValue: 60,
  );

  Duration get _normalTimeout => Duration(seconds: _normalTimeoutSeconds);
  Duration get _uploadTimeout => Duration(seconds: _uploadTimeoutSeconds);
  Duration get _studyReportTimeout => Duration(seconds: _studyReportTimeoutSeconds);
  Duration get _quizTimeout => Duration(seconds: _quizTimeoutSeconds);

  static const _tokenKey = 'shiye_token';

  static String get baseUrl => _baseUrl;

  String? _token;

  String? get token => _token;
  bool get isLoggedIn => _token != null;

  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;
  ApiClient._internal();

  /// 供测试子类化（桩掉接口调用）的公开构造（T4）
  ///
  /// 生产代码一律用单例 [ApiClient()]；测试里 `extends ApiClient`
  /// 并 `super.forTesting()` 即可覆盖接口方法做桩。
  ApiClient.forTesting();

  /// 从本地存储恢复 token
  Future<void> restoreToken() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString(_tokenKey);
  }

  /// 保存 token
  Future<void> _saveToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
  }

  /// 清除 token（登出）
  Future<void> clearToken() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
  }

  Map<String, String> get _headers => {
        if (_token != null) 'Authorization': 'Bearer $_token',
      };

  Uri _uri(String path) => Uri.parse('$_baseUrl$path');

  Future<Map<String, dynamic>> _get(String path, {Map<String, dynamic>? query}) async {
    final uri = Uri.parse('$_baseUrl$path').replace(queryParameters: query);
    try {
      final resp = await http.get(uri, headers: _headers).timeout(_normalTimeout);
      return _handle(resp);
    } catch (e) {
      throw ApiException(mapExceptionToMessage(e));
    }
  }

  Future<List<dynamic>> _getList(String path, {Map<String, dynamic>? query}) async {
    final uri = Uri.parse('$_baseUrl$path').replace(queryParameters: query);
    try {
      final resp = await http.get(uri, headers: _headers).timeout(_normalTimeout);
      if (resp.statusCode >= 400) throw ApiException(_parseError(resp));
      if (resp.body.isEmpty) return [];
      return jsonDecode(resp.body) as List;
    } catch (e) {
      // 已是 ApiException（来自 _parseError 分支）则原样抛
      if (e is ApiException) rethrow;
      throw ApiException(mapExceptionToMessage(e));
    }
  }

  Future<Map<String, dynamic>> _post(String path, {Map<String, dynamic>? body}) async {
    try {
      final resp = await http
          .post(
            _uri(path),
            headers: {..._headers, 'Content-Type': 'application/json'},
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(_normalTimeout);
      return _handle(resp);
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(mapExceptionToMessage(e));
    }
  }

  Future<Map<String, dynamic>> _patch(String path, {Map<String, dynamic>? body}) async {
    try {
      final resp = await http
          .patch(
            _uri(path),
            headers: {..._headers, 'Content-Type': 'application/json'},
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(_normalTimeout);
      return _handle(resp);
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(mapExceptionToMessage(e));
    }
  }

  Future<void> _delete(String path) async {
    try {
      final resp = await http.delete(_uri(path), headers: _headers).timeout(_normalTimeout);
      if (resp.statusCode >= 400) throw ApiException(_parseError(resp));
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(mapExceptionToMessage(e));
    }
  }

  Future<Map<String, dynamic>> _handle(http.Response resp) async {
    if (resp.statusCode >= 400) {
      throw ApiException(_parseError(resp), retryAfterSeconds: _parseRetryAfter(resp));
    }
    if (resp.body.isEmpty) return {};
    try {
      return jsonDecode(resp.body) as Map<String, dynamic>;
    } catch (e) {
      // 响应不是合法 JSON：T4-3 统一映射为「服务器返回数据异常」
      throw ApiException(mapExceptionToMessage(FormatException()));
    }
  }

  String _parseError(http.Response resp) {
    try {
      final body = jsonDecode(resp.body) as Map<String, dynamic>;
      return body['detail']?.toString() ?? '请求失败 (${resp.statusCode})';
    } catch (_) {
      return '请求失败 (${resp.statusCode})';
    }
  }

  /// 解析 429 响应体里的 `retry_after_seconds`（T7-2）
  ///
  /// 拿不到（字段缺失/非法/非数字）一律返回 null —— 调用方不得自造倒计时。
  int? _parseRetryAfter(http.Response resp) {
    try {
      final body = jsonDecode(resp.body) as Map<String, dynamic>;
      final v = body['retry_after_seconds'];
      if (v is num) return v.toInt();
      if (v is String) return int.tryParse(v);
      return null;
    } catch (_) {
      return null;
    }
  }

  // ====== 认证 ======

  Future<Map<String, dynamic>> devLogin(String openid, {String? nickname, String? inviteCode}) async {
    final data = await _post('/auth/dev-login', body: {
      'openid': openid,
      if (nickname != null) 'nickname': nickname,
      if (inviteCode != null) 'invite_code': inviteCode,
    });
    await _saveToken(data['access_token'] as String);
    return data;
  }

  Future<Map<String, dynamic>> wechatLogin(String code) async {
    final data = await _post('/auth/wechat', body: {'code': code});
    await _saveToken(data['access_token'] as String);
    return data;
  }

  Future<Map<String, dynamic>> getMe() => _get('/auth/me');

  Future<Map<String, dynamic>> updateMe({String? nickname, String? avatarUrl}) =>
      _patch('/auth/me', body: {
        if (nickname != null) 'nickname': nickname,
        if (avatarUrl != null) 'avatar_url': avatarUrl,
      });

  /// 注销账号（T12-6）：`DELETE /auth/me`
  ///
  /// 后端会删除该账号的**全部数据 + 图片文件**；成功后该 token 立即失效。
  /// 调用方应在成功后清除本地 token 并回到登录页。
  Future<void> deleteMe() async {
    try {
      final resp = await http.delete(_uri('/auth/me'), headers: _headers).timeout(_normalTimeout);
      await _handle(resp);
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(mapExceptionToMessage(e));
    }
  }

  // ====== 学科 ======

  Future<List<Map<String, dynamic>>> listSubjects() async {
    final data = await _getList('/subjects');
    return data.cast<Map<String, dynamic>>();
  }

  Future<List<Map<String, dynamic>>> listChapters(int subjectId) async {
    final data = await _getList('/subjects/$subjectId/chapters');
    return data.cast<Map<String, dynamic>>();
  }

  // T13-3：新建科目默认色 旧绿 → 主题蓝（与后端 DEFAULT_COLOR 保持一致）
  Future<Map<String, dynamic>> createSubject(String name, {String color = '#007AFF'}) =>
      _post('/subjects', body: {'name': name, 'color': color});

  Future<Map<String, dynamic>> updateSubject(int id, {String? name, String? color, int? sortOrder}) =>
      _patch('/subjects/$id', body: {
        if (name != null) 'name': name,
        if (color != null) 'color': color,
        if (sortOrder != null) 'sort_order': sortOrder,
      });

  Future<void> deleteSubject(int id) => _delete('/subjects/$id');

  // ====== 章 ======

  Future<Map<String, dynamic>> createChapter(int subjectId, String name) =>
      _post('/subjects/$subjectId/chapters', body: {'name': name});

  Future<void> deleteChapter(int subjectId, int chapterId) =>
      _delete('/subjects/$subjectId/chapters/$chapterId');

  // ====== 页 ======

  Future<Map<String, dynamic>> listPages({
    int? subjectId,
    int? chapterId,
    String? state,
    int page = 1,
    int size = 50,
  }) =>
      _get('/pages', query: {
        if (subjectId != null) 'subject_id': subjectId.toString(),
        if (chapterId != null) 'chapter_id': chapterId.toString(),
        if (state != null) 'state': state,
        'page': page.toString(),
        'size': size.toString(),
      });

  Future<Map<String, dynamic>> getPage(int id) => _get('/pages/$id');

  /// 单张上传（T4-2）：[onProgress] 回调按真实字节推进
  /// 参数 (已发送字节, 总字节)
  Future<Map<String, dynamic>> uploadPage(
    File image,
    int subjectId, {
    int? chapterId,
    void Function(int sent, int total)? onProgress,
  }) async {
    final req = http.MultipartRequest('POST', _uri('/pages'))
      ..headers.addAll(_headers)
      ..fields['subject_id'] = subjectId.toString();
    if (chapterId != null) req.fields['chapter_id'] = chapterId.toString();
    req.files.add(await http.MultipartFile.fromPath(
      'file',
      image.path,
      contentType: MediaType('image', 'jpeg'),
    ));
    final resp = await _sendMultipart(req, onProgress: onProgress);
    return _handle(resp);
  }

  /// 批量上传（T4-2）：返回每张完成状态；失败时抛异常由调用方决定保留哪些未上传图片
  /// 进度回调 [onProgress](已发送字节, 总字节, 当前第几张 1~N, 总张数 N)
  Future<List<Map<String, dynamic>>> uploadPagesBatch(
    List<File> images,
    int subjectId, {
    int? chapterId,
    void Function(int sent, int total, int current, int totalImages)? onProgress,
  }) async {
    final req = http.MultipartRequest('POST', _uri('/pages/batch'))
      ..headers.addAll(_headers)
      ..fields['subject_id'] = subjectId.toString();
    if (chapterId != null) req.fields['chapter_id'] = chapterId.toString();
    for (final img in images) {
      req.files.add(await http.MultipartFile.fromPath('files', img.path));
    }
    final resp = await _sendMultipart(
      req,
      onProgress: onProgress == null ? null : (sent, total) => onProgress(sent, total, 1, images.length),
    );
    try {
      final data = jsonDecode(resp.body) as Map<String, dynamic>;
      if (resp.statusCode >= 400) {
        throw ApiException(data['detail']?.toString() ?? '请求失败 (${resp.statusCode})');
      }
      return (data['pages'] as List).cast<Map<String, dynamic>>();
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(mapExceptionToMessage(FormatException()));
    }
  }

  /// 走 multipart 真实字节进度上传（T4-2 实现 A 方案）
  /// 拦截 [MultipartRequest.finalize] 字节流，统计已发送字节后经 StreamedRequest 发出
  Future<http.Response> _sendMultipart(
    http.MultipartRequest req, {
    void Function(int sent, int total)? onProgress,
  }) async {
    final totalBytes = req.contentLength;
    int sent = 0;
    final client = http.Client();
    try {
      // finalize 把 multipart 内容（含 boundary/字段/文件）编码为 ByteStream
      // 用 StreamedRequest 替代 MultipartRequest.send，以便在写出字节时回调进度
      final byteStream = req.finalize();
      final streamedReq = http.StreamedRequest(req.method, req.url)
        ..contentLength = totalBytes
        ..headers.addAll(req.headers);
      byteStream.listen(
        (chunk) {
          sent += chunk.length;
          onProgress?.call(sent, totalBytes);
          streamedReq.sink.add(chunk);
        },
        onError: streamedReq.sink.addError,
        onDone: streamedReq.sink.close,
        cancelOnError: true,
      );
      final streamResp = await client.send(streamedReq).timeout(_uploadTimeout);
      final resp = await http.Response.fromStream(streamResp);
      return resp;
    } on TimeoutException {
      throw ApiException('上传超时，请检查网络后重试');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(mapExceptionToMessage(e, isUpload: true));
    } finally {
      client.close();
    }
  }

  Future<Map<String, dynamic>> updatePage(
    int id, {
    String? title,
    int? subjectId,
    int? chapterId,
    String? ocrText,
    String? structuredText,
  }) =>
      _patch('/pages/$id', body: {
        if (title != null) 'title': title,
        if (subjectId != null) 'subject_id': subjectId,
        if (chapterId != null) 'chapter_id': chapterId,
        if (ocrText != null) 'ocr_text': ocrText,
        if (structuredText != null) 'structured_text': structuredText,
      });

  Future<void> deletePage(int id) => _delete('/pages/$id');

  Future<Map<String, dynamic>> reocrPage(int id) => _post('/pages/$id/reocr');

  Future<Map<String, dynamic>> organizePage(int id) =>
      _post('/pages/$id/organize');

  Future<Map<String, dynamic>> organizeChapter(int subjectId, int chapterId) =>
      _post('/subjects/$subjectId/chapters/$chapterId/organize');

  // ====== 搜索 ======

  Future<Map<String, dynamic>> search(String q, {int? subjectId}) =>
      _get('/search', query: {
        'q': q,
        if (subjectId != null) 'subject_id': subjectId.toString(),
      });

  // ====== AI 学情报告（T5） ======

  /// 生成学情报告（同步，服务端约 5~15s，用 60s 超时）
  Future<Map<String, dynamic>> studyReport({int? subjectId}) async {
    try {
      final resp = await http
          .post(
            _uri('/ai/study-report'),
            headers: {..._headers, 'Content-Type': 'application/json'},
            body: jsonEncode({'subject_id': subjectId}),
          )
          .timeout(_studyReportTimeout);
      return _handle(resp);
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(mapExceptionToMessage(e));
    }
  }

  // ====== AI 测评：出题 / 判分（T10，对接 T9 后端，接口契约不许改） ======

  /// 出题（T9 `POST /ai/quiz/generate`）。
  ///
  /// **不解析业务语义**，只返回后端原始 Map，由页面判断：
  /// - 空态 `{empty: true, reason: "..."}`（页面必须展示 `reason` 原文）
  /// - 成功 `{session_id, questions: [{question_id, seq, question, knowledge_point}]}`
  ///   —— 后端刻意**不返回参考答案**
  /// - 429 的 `retry_after_seconds` 已由 [_handle] 解析进 [ApiException.retryAfterSeconds]
  ///
  /// 超时沿用 [studyReport] 的同级长超时（同步 AI 调用约 5~15s）。
  Future<Map<String, dynamic>> generateQuiz({int? subjectId}) async {
    try {
      final resp = await http
          .post(
            _uri('/ai/quiz/generate'),
            headers: {..._headers, 'Content-Type': 'application/json'},
            body: jsonEncode({'subject_id': subjectId}),
          )
          .timeout(_quizTimeout);
      return _handle(resp);
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(mapExceptionToMessage(e));
    }
  }

  /// 判分（T9 `POST /ai/quiz/grade`）。
  ///
  /// [answers] 形如 `[{question_id, answer_text}]`；方法**只返回原始 Map**
  /// （成功含 `results` / `summary` / `suggestions`），是否判分完成由页面判断。
  /// 作答超长会由后端返回 422，页面需提前用 `maxLength` 拦截。
  Future<Map<String, dynamic>> gradeQuiz({
    required int sessionId,
    required List<Map<String, dynamic>> answers,
  }) async {
    try {
      final resp = await http
          .post(
            _uri('/ai/quiz/grade'),
            headers: {..._headers, 'Content-Type': 'application/json'},
            body: jsonEncode({'session_id': sessionId, 'answers': answers}),
          )
          .timeout(_quizTimeout);
      return _handle(resp);
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(mapExceptionToMessage(e));
    }
  }

  // ====== 导出（T11-A，新增接口，不改任何现有契约） ======

  /// 导出单页（`GET /pages/{id}/export?format=md|txt`）
  ///
  /// 返回**服务端真实产出的文件内容 + 文件名**（文件名按 RFC 5987 解析，中文不乱码）。
  /// - 该页没有任何文本 → 后端 400，[ApiException.message] 为后端中文原因
  /// - 跨用户 / 不存在 → 404
  Future<ExportFile> exportPage(int id, {String format = 'md'}) =>
      _exportGet('/pages/$id/export', format);

  /// 导出整章（`GET /subjects/{sid}/chapters/{cid}/export?format=md|txt`）
  ///
  /// 内容与「来源标注」全部由后端产出（前端不拼业务文案）；无文本 → 400，跨用户 → 404。
  Future<ExportFile> exportChapter(int subjectId, int chapterId, {String format = 'md'}) =>
      _exportGet('/subjects/$subjectId/chapters/$chapterId/export', format);

  Future<ExportFile> _exportGet(String path, String format) async {
    final uri = Uri.parse('$_baseUrl$path').replace(queryParameters: {'format': format});
    try {
      final resp = await http.get(uri, headers: _headers).timeout(_normalTimeout);
      if (resp.statusCode >= 400) {
        throw ApiException(_parseError(resp), retryAfterSeconds: _parseRetryAfter(resp));
      }
      return ExportFile(
        filename: _filenameFromDisposition(resp.headers['content-disposition'], format),
        content: utf8.decode(resp.bodyBytes),
      );
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(mapExceptionToMessage(e));
    }
  }

  /// 解析 `Content-Disposition`：优先 RFC 5987 的 `filename*=UTF-8''<pct>`，其次 `filename="…"`
  String _filenameFromDisposition(String? header, String format) {
    final fallback = 'export.$format';
    if (header == null || header.isEmpty) return fallback;
    final star = RegExp(r"filename\*\s*=\s*UTF-8''([^;]+)", caseSensitive: false).firstMatch(header);
    if (star != null) {
      try {
        final decoded = Uri.decodeComponent(star.group(1)!.trim());
        if (decoded.isNotEmpty) return decoded;
      } catch (_) {
        // 编码异常 → 退回 ASCII 分支
      }
    }
    final plain = RegExp(r'filename\s*=\s*"([^"]*)"', caseSensitive: false).firstMatch(header);
    if (plain != null && plain.group(1)!.trim().isNotEmpty) return plain.group(1)!.trim();
    return fallback;
  }
}

/// 统一异常 → 可操作中文文案（T4-3）
///
/// UI 层 catch (e) 应使用 `mapExceptionToMessage(e)` 而非拼 `'$e'`。
/// - [ApiException] 自身已含后端 detail 原文，直接透传
/// - [isUpload] 为 true 时返回「上传超时/上传失败」语义，否则「请求超时/操作失败」
String mapExceptionToMessage(Object e, {bool isUpload = false}) {
  // ApiException 优先：后端 4xx/5xx detail 已是中文可操作文案
  if (e is ApiException) return e.message;

  // http.ClientException（含 SocketException 等连接层失败）
  if (e is http.ClientException) {
    return '无法连接服务器，请检查网络或确认服务已启动';
  }
  if (e is SocketException) {
    return '无法连接服务器，请检查网络或确认服务已启动';
  }
  // TimeoutException（.timeout 抛出）
  if (e is TimeoutException) {
    return isUpload ? '上传超时，请检查网络后重试' : '请求超时，请检查网络后重试';
  }
  // FormatException：响应不是合法 JSON
  if (e is FormatException) {
    return '服务器返回数据异常';
  }
  // 其它：兜底通用文案 + debugPrint 记录原始异常便于排障
  debugPrint('[ApiClient] 未识别异常: $e');
  return isUpload ? '上传失败，请稍后重试' : '操作失败，请稍后重试';
}

class ApiException implements Exception {
  final String message;

  /// 429 限流时后端返回的剩余冷却秒数（T7-2）
  ///
  /// 可选，默认 null；只有后端真实返回 `retry_after_seconds` 时才有值。
  /// 为 null 时调用方不得自造倒计时，退化为只展示 [message]。
  final int? retryAfterSeconds;

  ApiException(this.message, {this.retryAfterSeconds});
  @override
  String toString() => message;
}

/// 导出结果（T11-A）：服务端真实产出的文件名 + 文件内容
///
/// [filename] 来自后端 `Content-Disposition`（RFC 5987 解码后），中文文件名不会乱码。
class ExportFile {
  final String filename;
  final String content;

  const ExportFile({required this.filename, required this.content});

  /// 内容字节数（UTF-8），用于结果展示
  int get byteLength => utf8.encode(content).length;
}
