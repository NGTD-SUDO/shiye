/// 上传进度纯函数（T4-2）
///
/// 从已发送字节与总字节计算 0~1 进度。
/// 保证：单调不减、完成时恰好为 1、总字节为 0 时不出现 NaN（返回 0）。
library;

/// 计算上传进度
///
/// - [sent] 已发送字节（累计，单调不减）
/// - [total] 总字节数
///
/// 返回值范围 [0.0, 1.0]：
/// - 总字节为 0 或负数时返回 0.0（避免 NaN，按任务书要求）
/// - 已发送超过总字节时返回 1.0（不应发生但保护性截断）
/// - 已发送为负数时按 0 处理
double uploadProgress(int sent, int total) {
  if (total <= 0) return 0.0;
  if (sent < 0) return 0.0;
  if (sent >= total) return 1.0;
  return sent / total;
}
