"""AI 引擎抽象层：可切换 DeepSeek / 其他 LLM"""
from abc import ABC, abstractmethod


class AiProvider(ABC):
    """LLM 提供者：整理笔记文本 + 生成学情报告 + 出题 / 判分"""

    @abstractmethod
    def organize(self, text: str, scope: str) -> str:
        """整理笔记文本。

        Args:
            text: OCR 识别出的原始文本
            scope: "page"（单页）或 "chapter"（章级聚合）

        Returns:
            整理后的 Markdown 文本
        """
        raise NotImplementedError

    @abstractmethod
    def study_report(self, payload: str) -> str:
        """生成 AI 学情报告（T5）。

        Args:
            payload: 已组装好的统计数字 + 趋势 + 学科/章名 + 页标题 + 页内容摘要

        Returns:
            学情报告 Markdown 文本（末尾须含「（仅供参考）」）
        """
        raise NotImplementedError

    @abstractmethod
    def generate_quiz(self, payload: str, count: int) -> list[dict]:
        """按笔记内容出题（T9-3）。

        Args:
            payload: 含正文摘要的内容 payload（见 `build_study_payload`）
            count: 出题数量

        Returns:
            纯数据列表，每项含 `question`(题干) / `reference_answer`(参考答案) /
            `knowledge_point`(考查知识点)。

        Raises:
            RuntimeError: 调用失败或 AI 输出无法解析为严格 JSON 时抛可操作中文错误；
                **绝不返回半截或猜测的题目**。
        """
        raise NotImplementedError

    @abstractmethod
    def grade_quiz(self, payload: str) -> dict:
        """按用户真实作答判分（T9-3）。

        Args:
            payload: 含题目、参考答案与用户作答的 payload（见 `build_grade_payload`）

        Returns:
            ``{"results": [{"is_correct": bool, "comment": str,
            "knowledge_point": str, "mastery": "good"|"partial"|"weak"}],
            "summary": str, "suggestions": [str]}``。

        Raises:
            RuntimeError: 调用失败或 AI 输出无法解析为严格 JSON 时抛可操作中文错误；
                **绝不返回编造的分数或半截数据**。
        """
        raise NotImplementedError
