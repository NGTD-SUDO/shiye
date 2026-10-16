"""DeepSeek AI 实现（OpenAI 兼容 API）"""
import httpx

from app.ai.base import AiProvider
from app.ai.quiz import parse_grade_json, parse_quiz_json
from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

SYSTEM_PROMPT = """你是一个专业的笔记整理助手。用户会提供 OCR 识别出的笔记文本，你的任务是：

1. **纠错**：根据上下文修正 OCR 形近字错误（如「体私」→「体积」、「抹钝」→「二面角」、「单顽式」→「单项式」），但不要添加原文没有的内容。
2. **排版**：将文本整理为结构化的 Markdown 大纲：
   - 用 `# 标题` 表示主题
   - 用 `## 小节` 表示分点
   - 用 `- 要点` 或 `1. 步骤` 列出知识点
3. **公式**：数学公式用 `$...$`（行内）或 `$$...$$`（块级）包裹。
4. **底线**：不得编造原文没有的知识点；不确定的内容标注 `[?]`。

只输出整理后的 Markdown，不要输出解释、前言或后记。"""

# 学情报告 system prompt（T9-2 重构：三段式诊断，删「概况」「参考页」段）
STUDY_REPORT_SYSTEM_PROMPT = """你是一个学习情况诊断助手。用户会提供学习统计、近 30 天记录趋势、笔记页标题与「页内容摘要」（笔记正文前 120 字；不含图片、不含完整正文）。请据此生成一份**具体、可执行**的诊断报告：

## 一、学习内容判断
- 依据「页内容摘要」判断该用户**正在学的具体知识点 / 主题**（例如「余角与补角的性质」「唯物辩证法的三大规律」），用条目列出。
- **每一条都必须能在正文摘要里找到依据**（可引用页标题或正文片段）；**找不到依据的一律不许写**。
- 只写具体知识点，**不要**用「数学」「政治」这类学科名代替知识点。

## 二、学习薄弱点
- 只依据内容本身（正文摘要 / 页标题）指出可能的知识薄弱点或易错处；**不得**把工程指标（识别失败页、未分章、完成率）当作学习薄弱点。

## 三、针对性提升方案
- 每条方案必须**对应上面某一个薄弱点**，并**引用具体页标题或正文片段作为依据**。

硬约束（违反视为无效报告）：
1. **禁止通用话术**：不得出现「建立章节结构」「合理分配时间」「保持记录习惯」「利用优势」「建议定期复习」这类放到谁身上都成立的话。
2. 每条建议都必须有具体依据（页标题或正文片段）；给不出依据就不要写。
3. **数据不足要如实说明**：若正文摘要太少或太零碎，直接写明「记录较少，判断可能不准」，**不许硬编结论**。
4. 只依据提供的材料，不得编造统计数字或知识点。
5. 报告末尾必须单独一行写「（仅供参考）」。
6. 用 Markdown 输出，结构清晰。"""

# 出题 system prompt（T9-3）：要求严格 JSON，便于后端解析为纯数据
QUIZ_GENERATE_SYSTEM_PROMPT = """你是一个出题助手。用户会提供某学科的笔记统计与「页内容摘要」（笔记正文前 120 字），请依据这些笔记内容出题，用来推测学生当前水平。

要求：
1. 只依据提供的笔记内容出题，**不得**考查材料里没有出现过的知识点。
2. 题量与难度要求见用户消息。
3. 每道题都必须对应笔记内容里的具体知识点。

只输出**严格 JSON**（可放在 ```json 代码块中），不要输出任何解释、前言或后记。JSON 结构：
{"questions": [{"question": "题干", "reference_answer": "参考答案", "knowledge_point": "考查的知识点"}]}"""

# 判分 system prompt（T9-3）：必须基于用户真实作答，给针对性方案
QUIZ_GRADE_SYSTEM_PROMPT = """你是一个阅卷助手。用户会提供若干道题、每题参考答案，以及学生的**真实作答**。请逐题判分并给出诊断。

要求：
1. **判分必须基于学生实际写下的内容**；作答为空、答非所问或明显错误 → `is_correct` 为 false。
2. `comment` 必须针对该学生这一次的作答（指出对在哪、错在哪），**严禁**给与作答无关的「标准答案式」套话点评。
3. `mastery` 取 `good` / `partial` / `weak` 之一。
4. `suggestions` 中**每条**都要对应一个薄弱考点（掌握程度非 good 的考点），并给出具体可执行的改进动作。

只输出**严格 JSON**（可放在 ```json 代码块中），不要输出任何解释或多余文字。JSON 结构：
{"results": [{"is_correct": true, "comment": "针对该作答的点评", "knowledge_point": "考点", "mastery": "good"}], "summary": "总体诊断", "suggestions": ["针对薄弱考点的具体方案"]}"""


class DeepSeekAiProvider(AiProvider):
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.base_url = base_url or DEEPSEEK_BASE_URL
        self.model = model or DEEPSEEK_MODEL

    def organize(self, text: str, scope: str) -> str:
        if not self.api_key:
            raise RuntimeError("DeepSeek API Key 未配置（SHIYE_DEEPSEEK_API_KEY）")
        if not text.strip():
            return ""

        user_msg = f"请整理以下笔记文本（{'单页' if scope == 'page' else '章节聚合'}）：\n\n{text}"
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    def study_report(self, payload: str) -> str:
        """生成学情报告（T5-2）：max_tokens 1500 / timeout 45s / temperature 0.3。

        失败映射为可操作中文错误，绝不返回编造内容。
        """
        if not self.api_key:
            raise RuntimeError("DeepSeek API Key 未配置（SHIYE_DEEPSEEK_API_KEY）")
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": STUDY_REPORT_SYSTEM_PROMPT},
                        {"role": "user", "content": payload},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1500,
                },
                timeout=45.0,
            )
        except httpx.TimeoutException as exc:
            raise RuntimeError("AI 报告生成超时（45s），请稍后重试") from exc
        except httpx.ConnectError as exc:
            raise RuntimeError("无法连接 AI 服务，请检查网络后重试") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"请求 AI 服务失败，请稍后重试（{exc}）") from exc

        if resp.status_code != 200:
            raise RuntimeError(f"AI 服务返回错误（HTTP {resp.status_code}），请稍后重试")
        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, ValueError) as exc:
            raise RuntimeError("AI 服务返回数据异常，请稍后重试") from exc

    def generate_quiz(self, payload: str, count: int) -> list[dict]:
        """出题（T9-3）：要求 AI 输出严格 JSON，解析失败抛中文错误。

        绝不返回半截 / 猜测的题目（AI 不可用或格式异常一律抛 RuntimeError）。
        """
        if not self.api_key:
            raise RuntimeError("DeepSeek API Key 未配置（SHIYE_DEEPSEEK_API_KEY）")
        user_msg = f"请依据以下笔记内容出 {count} 道题（由易到难）：\n\n{payload}"
        raw = self._chat(
            QUIZ_GENERATE_SYSTEM_PROMPT,
            user_msg,
            max_tokens=1500,
            timeout=45.0,
            timeout_label="45s",
        )
        return parse_quiz_json(raw, count)

    def grade_quiz(self, payload: str) -> dict:
        """判分（T9-3）：要求 AI 输出严格 JSON，解析失败抛中文错误。

        判分只基于 payload 里用户的真实作答；绝不返回编造的分数或半截数据。
        """
        if not self.api_key:
            raise RuntimeError("DeepSeek API Key 未配置（SHIYE_DEEPSEEK_API_KEY）")
        raw = self._chat(
            QUIZ_GRADE_SYSTEM_PROMPT,
            payload,
            max_tokens=2000,
            timeout=60.0,
            timeout_label="60s",
        )
        return parse_grade_json(raw)

    def _chat(
        self,
        system_prompt: str,
        user_msg: str,
        *,
        max_tokens: int,
        timeout: float,
        timeout_label: str,
    ) -> str:
        """统一的 chat/completions 调用 + 中文错误映射（沿用现有错误映射风格）。

        temperature 固定 0.2：出题 / 判分需要稳定、可复现。
        超时 / 连接失败 / HTTP 非 200 / 返回体异常一律抛可操作中文 RuntimeError。
        """
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.2,
                    "max_tokens": max_tokens,
                },
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"AI 服务响应超时（{timeout_label}），请稍后重试") from exc
        except httpx.ConnectError as exc:
            raise RuntimeError("无法连接 AI 服务，请检查网络后重试") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"请求 AI 服务失败，请稍后重试（{exc}）") from exc

        if resp.status_code != 200:
            raise RuntimeError(f"AI 服务返回错误（HTTP {resp.status_code}），请稍后重试")
        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, ValueError) as exc:
            raise RuntimeError("AI 服务返回数据异常，请稍后重试") from exc
