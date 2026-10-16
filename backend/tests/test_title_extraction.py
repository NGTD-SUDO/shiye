"""T6-1 标题抽取纯函数测试（表驱动）"""
import pytest

from app.services.title_extractor import extract_title, is_noise_line, is_noise_title

# 任务书给的真实第 1 页 OCR 文本（10 行，前 6 行是状态栏噪声）
REAL_OCR = """10:49:24
280
5G
KB's
96%
818
如果两个角的和等于90°(直角),就说其中每一个角是另一个角的余角.
余角的性质:同角(等角)的余角相等)
几何语言:"""


# ==================== is_noise_line ====================

@pytest.mark.parametrize("line", [
    # 时间（半角/全角冒号、带秒不带秒）
    "10:49:24", "10:49", "10：49：24", "10：49",
    # 纯数字
    "280", "818", "96", "5",
    # 纯数字 + 单位/符号
    "96%", "1/9", "3 / 5", "818-280",
    # 网络/速度/信号
    "5G", "4G", "3G", "KB's", "KB/s", "MB/s", "WiFi", "WLAN", "LTE",
    "充电", "信号", "飞行模式",
    # 页码/表头
    "No.", "No", "Date", "date",
    # 过短 / 标点 / 单字母
    "a", "-", "?", "x", "---",
])
def test_is_noise_line_true(line):
    assert is_noise_line(line), f"{line!r} 应判为噪声"


@pytest.mark.parametrize("line", [
    "如果两个角的和等于90°",
    "余角的性质",
    "几何语言",
    "hello world",
    "导数与极值",
    "如果两个角的和等于90°(直角)",
    # T6 一审补：正文内容词必须保留（关键词不得全行匹配误伤）
    "信号与系统第一章",
    "模拟信号与数字信号",
    "5G通信原理",
    "3GPP协议",
    "增长率%计算",
    "采样定理与频谱",
])
def test_is_noise_line_false(line):
    assert not is_noise_line(line), f"{line!r} 不应判为噪声"


# ==================== extract_title ====================

def test_extract_title_real_page():
    """真实第 1 页文本 → 应得到真正的第一句内容（截断 40 字内）"""
    result = extract_title(REAL_OCR)
    assert result.startswith("如果两个角的和等于90°")
    assert len(result) <= 40


def test_extract_title_chinese_priority():
    """中文优先：跳过前面的英文/噪声，返回第一条中文行"""
    assert extract_title("10:49:24\nhello\n如果两个角的和等于90°").startswith("如果两个角")


def test_extract_title_fallback_non_chinese():
    """全无中文 → 退回第一条非噪声行"""
    assert extract_title("10:49:24\n280\nhello world") == "hello world"


def test_extract_title_all_noise_empty():
    """全部是噪声 → 返回空串（不许兜底）"""
    assert extract_title("10:49:24\n280\n5G\n96%") == ""


def test_extract_title_strips_list_markers():
    assert extract_title("1. 余角的性质") == "余角的性质"
    assert extract_title("（1）余角的性质") == "余角的性质"
    assert extract_title("- 余角的性质") == "余角的性质"


def test_extract_title_truncates_40():
    long_line = "很长的中文标题" * 10  # 70 字
    assert len(extract_title(long_line)) == 40


# ==================== is_noise_title ====================

def test_is_noise_title_empty():
    assert is_noise_title("", REAL_OCR) is True
    assert is_noise_title("   ", REAL_OCR) is True


def test_is_noise_title_time_noise():
    assert is_noise_title("10:49:24", REAL_OCR) is True


def test_is_noise_title_normal_kept():
    assert is_noise_title("余角的性质", REAL_OCR) is False
    assert is_noise_title("如果两个角的和等于90°", REAL_OCR) is False


def test_is_noise_title_keyword_title_kept():
    """T6 一审补：用户手改的含关键词标题永不被覆盖（保守判据，不复用关键词）"""
    assert is_noise_title("信号与系统", REAL_OCR) is False
    assert is_noise_title("5G通信原理", REAL_OCR) is False
    assert is_noise_title("增长率%计算", REAL_OCR) is False
    assert is_noise_title("我手动起的标题——别覆盖我", REAL_OCR) is False
