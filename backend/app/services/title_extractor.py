"""标题抽取纯函数（T6-1）

从 OCR 文本里抽一条有意义的标题：跳过状态栏噪声 + 中文优先。
全部为纯函数、无副作用、可直接单测。

铁律：标题只能来自该页真实 OCR 文本；没有可用行就返回空串，绝不用文件名/时间戳兜底。
"""
import re

# 电量/网络/速度/信号 关键词（忽略大小写匹配）
_NETWORK_NOISE = re.compile(r"%|KB/s|KB's|MB/s|5G|4G|3G|WiFi|WLAN|LTE|充电|信号|飞行模式", re.IGNORECASE)

# 时间：10:49:24 / 10:49 / 10：49：24（半角/全角冒号、带秒不带秒）
_TIME = re.compile(r"^[0-9]{1,2}[:：][0-9]{2}([:：][0-9]{2})?$")

# 纯数字（1~4 位）
_PURE_DIGITS = re.compile(r"^[0-9]{1,4}$")

# 纯数字 + 单位/符号（电量 96%、页码 1/9、818-280 等）
_DIGITS_SYMBOLS = re.compile(r"^[0-9\s.,%:：\-—+/]+$")

# 页码/表头：No. / No / Date
_PAGE_HEADER = re.compile(r"^No\.?$|^Date$", re.IGNORECASE)

# 数字/数字：1/9 或 3 / 5
_RATIO = re.compile(r"^[0-9]+\s*/\s*[0-9]+$")

# 只由标点组成（如 ---、……、？？）
_PUNCT_ONLY = re.compile(r"^[\W_]+$")

# 数字类噪声（纯数字+符号 / 比例）长度上限：整行超长不判噪声，避免数学内容长串误判
_DIGIT_NOISE_MAX_LEN = 8
# 网络/状态栏关键词噪声长度上限：整行过长不判噪声
_NETWORK_NOISE_MAX_LEN = 8


def _has_chinese(s: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in s)


def _count_chinese(s: str) -> int:
    return sum(1 for c in s if "\u4e00" <= c <= "\u9fff")


def is_noise_line(line: str) -> bool:
    """判定单行是否为状态栏噪声（时间/纯数字/网络速度/页码/过短等）。"""
    line = (line or "").strip()
    if not line:
        return True

    if _TIME.fullmatch(line):
        return True
    if _PURE_DIGITS.fullmatch(line):
        return True
    # 纯数字+符号（电量 96%、页码 1/9）：只在整行很短时判噪声，避免数学内容长串误判
    if len(line) <= _DIGIT_NOISE_MAX_LEN and _DIGITS_SYMBOLS.fullmatch(line):
        return True
    # 网络/状态栏关键词：仅当「整行就是状态栏形态」才判噪声——
    # 整行较短且去掉关键词后剩余不含中文，避免「信号与系统」「5G通信原理」等正文内容词被误判
    if len(line) <= _NETWORK_NOISE_MAX_LEN and _NETWORK_NOISE.search(line):
        rest = _NETWORK_NOISE.sub("", line)
        if not _has_chinese(rest):
            return True
    if _PAGE_HEADER.fullmatch(line):
        return True
    # 比例（1/9）：只在整行很短时判噪声
    if len(line) <= _DIGIT_NOISE_MAX_LEN and _RATIO.fullmatch(line):
        return True
    # 过短：去空白后长度 < 2
    if len(line) < 2:
        return True
    # 只由标点组成
    if _PUNCT_ONLY.fullmatch(line):
        return True
    return False


def _strip_list_marker(line: str) -> str:
    """去掉行首的常见列表符号（1. /（1）/ - 等），保留内容本身。"""
    line = line.strip()
    line = re.sub(r"^[（(][0-9]+[）)][、.：: ]*", "", line)  # （1）/ (1)
    line = re.sub(r"^[0-9]+[、.：:][ ]*", "", line)  # 1. / 1、
    line = re.sub(r"^[-•*·●◦★][ ]*", "", line)  # - / • / *
    return line.strip()


def extract_title(ocr_text: str, max_len: int = 40) -> str:
    """从 OCR 文本抽取标题。

    第一遍：返回第一条含 ≥2 个中文字符的非噪声行（中文优先）。
    第二遍：若全无中文，退回第一条非噪声行。
    都没有则返回空串。截断到 max_len（不追加省略号）。
    """
    if not ocr_text:
        return ""

    lines = [_strip_list_marker(l) for l in ocr_text.splitlines()]
    lines = [l for l in lines if l]  # 去掉空行

    # 第一遍：中文优先
    for line in lines:
        if not is_noise_line(line) and _count_chinese(line) >= 2:
            return line[:max_len]
    # 第二遍：退回第一条非噪声行
    for line in lines:
        if not is_noise_line(line):
            return line[:max_len]
    return ""


def is_noise_title(title: str, ocr_text: str) -> bool:
    """判断「现有标题是否为噪声」，供存量页重取标题用（保守，绝不复用关键词规则）。

    返回 True 表示该标题是噪声，需要重算；返回 False 表示标题有意义，保留（不覆盖用户手改）。

    保守判据只用「空 / 时间 / 纯数字 / 纯符号 / 去空白后 <2 字」，
    不带网络/状态栏关键词 —— 这样「信号与系统」「5G通信原理」「增长率%计算」等
    用户手改的标题永不会被覆盖。
    """
    t = (title or "").strip()
    # 标题为空 → 视为噪声（可尝试重取）
    if not t:
        return True
    # 时间（10:49:24）
    if _TIME.fullmatch(t):
        return True
    # 纯数字（280 / 818）
    if _PURE_DIGITS.fullmatch(t):
        return True
    # 纯符号（---）
    if _PUNCT_ONLY.fullmatch(t):
        return True
    # 去空白后 < 2 字
    if len(t) < 2:
        return True
    return False
