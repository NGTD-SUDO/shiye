/// 数据模型 — 搜索结果
library;

/// 与 note_page.dart 同思路：后端已返回签名 thumb_url，
/// 此处只做 baseUrl 拼接，缺失时为 null。
String? _resolveThumbUrl(dynamic raw, String baseUrl) {
  if (raw == null) return null;
  final s = raw.toString();
  if (s.isEmpty) return null;
  if (s.startsWith('http://') || s.startsWith('https://')) return s;
  if (s.startsWith('/')) return '$baseUrl$s';
  return '$baseUrl/$s';
}

class SearchResult {
  final int pageId;
  final String title;
  final int subjectId;
  final String subjectName;
  final String? thumbKey;
  final String? thumbUrl;
  final String ocrState;
  final String snippet;

  SearchResult({
    required this.pageId,
    required this.title,
    required this.subjectId,
    required this.subjectName,
    this.thumbKey,
    this.thumbUrl,
    required this.ocrState,
    required this.snippet,
  });

  factory SearchResult.fromJson(Map<String, dynamic> json, String baseUrl) {
    final thumbKey = json['thumb_key'] as String?;
    return SearchResult(
      pageId: json['page_id'] as int,
      title: json['title'] as String? ?? '',
      subjectId: json['subject_id'] as int,
      subjectName: json['subject_name'] as String? ?? '',
      thumbKey: thumbKey,
      // 后端在 thumb_key 为 null 时已返回 thumb_url=null，这里二次兜底
      thumbUrl: thumbKey == null ? null : _resolveThumbUrl(json['thumb_url'], baseUrl),
      ocrState: json['ocr_state'] as String? ?? '',
      snippet: json['snippet'] as String? ?? '',
    );
  }
}
