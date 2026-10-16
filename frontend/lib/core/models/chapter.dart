/// 数据模型 — 章
library;

class Chapter {
  final int id;
  final int subjectId;
  final String name;
  final int sortOrder;
  final int pageCount;

  Chapter({
    required this.id,
    required this.subjectId,
    required this.name,
    required this.sortOrder,
    required this.pageCount,
  });

  factory Chapter.fromJson(Map<String, dynamic> json) {
    return Chapter(
      id: json['id'] as int,
      subjectId: json['subject_id'] as int,
      name: json['name'] as String,
      sortOrder: json['sort_order'] as int? ?? 0,
      pageCount: json['page_count'] as int? ?? 0,
    );
  }
}
