/// 数据模型 — 笔记页
library;

/// 后端返回的图片 URL 可能是相对路径（以 / 开头）或绝对 URL；
/// 缺失时退化为空字符串，由 UI 走失败/空态分支。
String _resolveUrl(dynamic raw, String baseUrl) {
  if (raw == null) return '';
  final s = raw.toString();
  if (s.isEmpty) return '';
  if (s.startsWith('http://') || s.startsWith('https://')) return s;
  if (s.startsWith('/')) return '$baseUrl$s';
  return '$baseUrl/$s';
}

class NotePage {
  final int id;
  final int subjectId;
  final String? subjectName;
  final int? chapterId;
  final String? chapterName;
  final String title;
  final String imageKey;
  final String? thumbKey;
  final String imageUrl;
  final String? thumbUrl;
  final int? width;
  final int? height;
  final String ocrText;
  final String ocrState;
  final String? ocrError;
  final double? ocrConf;
  final String? structuredText;
  final int? pageNo;
  final String createdAt;
  final String? updatedAt;

  NotePage({
    required this.id,
    required this.subjectId,
    this.subjectName,
    this.chapterId,
    this.chapterName,
    required this.title,
    required this.imageKey,
    this.thumbKey,
    required this.imageUrl,
    this.thumbUrl,
    this.width,
    this.height,
    required this.ocrText,
    required this.ocrState,
    this.ocrError,
    this.ocrConf,
    this.structuredText,
    this.pageNo,
    required this.createdAt,
    this.updatedAt,
  });

  factory NotePage.fromJson(Map<String, dynamic> json, String baseUrl) {
    // 后端已返回签名 URL（image_url / thumb_url）；此处只做 baseUrl 拼接，
    // 不再自行拼 /files/{key}，避免破坏单一事实来源。
    // 后端字段缺失时 imageUrl 退化为空字符串、thumbUrl 为 null。
    return NotePage(
      id: json['id'] as int,
      subjectId: json['subject_id'] as int,
      subjectName: json['subject_name'] as String?,
      chapterId: json['chapter_id'] as int?,
      chapterName: json['chapter_name'] as String?,
      title: json['title'] as String? ?? '',
      imageKey: json['image_key'] as String,
      thumbKey: json['thumb_key'] as String?,
      imageUrl: _resolveUrl(json['image_url'], baseUrl),
      thumbUrl: json['thumb_key'] == null
          ? null
          : _resolveUrl(json['thumb_url'], baseUrl),
      width: json['width'] as int?,
      height: json['height'] as int?,
      ocrText: json['ocr_text'] as String? ?? '',
      ocrState: json['ocr_state'] as String? ?? 'pending',
      ocrError: json['ocr_error'] as String?,
      ocrConf: (json['ocr_conf'] as num?)?.toDouble(),
      structuredText: json['structured_text'] as String?,
      pageNo: json['page_no'] as int?,
      createdAt: json['created_at'] as String? ?? '',
      updatedAt: json['updated_at'] as String?,
    );
  }

  bool get isDone => ocrState == 'done';
  bool get isFailed => ocrState == 'failed';
  bool get isProcessing => ocrState == 'processing' || ocrState == 'pending';

  NotePage copyWith({
    int? id,
    int? subjectId,
    String? subjectName,
    int? chapterId,
    String? chapterName,
    String? title,
    String? imageKey,
    String? thumbKey,
    String? imageUrl,
    String? thumbUrl,
    int? width,
    int? height,
    String? ocrText,
    String? ocrState,
    String? ocrError,
    double? ocrConf,
    int? pageNo,
    String? createdAt,
    String? updatedAt,
    String? structuredText,
  }) {
    return NotePage(
      id: id ?? this.id,
      subjectId: subjectId ?? this.subjectId,
      subjectName: subjectName ?? this.subjectName,
      chapterId: chapterId ?? this.chapterId,
      chapterName: chapterName ?? this.chapterName,
      title: title ?? this.title,
      imageKey: imageKey ?? this.imageKey,
      thumbKey: thumbKey ?? this.thumbKey,
      imageUrl: imageUrl ?? this.imageUrl,
      thumbUrl: thumbUrl ?? this.thumbUrl,
      width: width ?? this.width,
      height: height ?? this.height,
      ocrText: ocrText ?? this.ocrText,
      ocrState: ocrState ?? this.ocrState,
      ocrError: ocrError ?? this.ocrError,
      ocrConf: ocrConf ?? this.ocrConf,
      pageNo: pageNo ?? this.pageNo,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      structuredText: structuredText ?? this.structuredText,
    );
  }
}
