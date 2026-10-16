/// 数据模型 — 学科
library;

class Subject {
  final int id;
  final String name;
  final String color;
  final String icon;
  final int sortOrder;
  final int pageCount;
  final int doneCount;
  final int chapterCount;

  Subject({
    required this.id,
    required this.name,
    required this.color,
    required this.icon,
    required this.sortOrder,
    required this.pageCount,
    required this.doneCount,
    required this.chapterCount,
  });

  factory Subject.fromJson(Map<String, dynamic> json) {
    return Subject(
      id: json['id'] as int,
      name: json['name'] as String,
      // T13-3：兜底色 旧绿 → 主题蓝（与前后端默认色一致）
      color: json['color'] as String? ?? '#007AFF',
      icon: json['icon'] as String? ?? 'book',
      sortOrder: json['sort_order'] as int? ?? 0,
      pageCount: json['page_count'] as int? ?? 0,
      doneCount: json['done_count'] as int? ?? 0,
      chapterCount: json['chapter_count'] as int? ?? 0,
    );
  }

  /// 进度比例（0.0 ~ 1.0）
  double get progress => pageCount > 0 ? doneCount / pageCount : 0;
}
