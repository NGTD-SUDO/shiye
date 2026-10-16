"""应用配置"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# 数据库（默认 SQLite 文件 backend/shiye.db）
DATABASE_URL = _env("SHIYE_DATABASE_URL", f"sqlite:///{BASE_DIR / 'shiye.db'}")

# JWT
SECRET_KEY = _env("SHIYE_SECRET_KEY", "dev-secret-change-me")  # 仅本地默认值，生产必须用环境变量覆盖
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(_env("SHIYE_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 30)))

# 图片签名 URL 有效期（秒）：图片访问支持签名 URL，默认 15 分钟
FILE_URL_TTL_SECONDS = int(_env("SHIYE_FILE_TTL_SECONDS", "900"))

# 微信开放平台（未配置时 /auth/wechat 返回 503，开发用 dev-login）
WECHAT_APPID = _env("SHIYE_WECHAT_APPID", "")
WECHAT_SECRET = _env("SHIYE_WECHAT_SECRET", "")

# 开发模式开关：true 时开放 POST /auth/dev-login（生产/公网必须 false）
DEV_MODE = _env("SHIYE_DEV_MODE", "false").lower() in ("1", "true", "yes")

# 内测邀请码：非空时 dev-login 必须带此码（常量时间比较）；为空则免码（仅本地开发）
INVITE_CODE = _env("SHIYE_INVITE_CODE", "")

# CORS 白名单：逗号分隔的 origin 列表；为空则不注册 CORS 中间件（App 原生 HTTP 不受影响）
CORS_ALLOW_ORIGINS = _env("SHIYE_CORS_ORIGINS", "")

# 日志级别（DEBUG/INFO/WARNING/ERROR）
LOG_LEVEL = _env("SHIYE_LOG_LEVEL", "INFO").upper()

# 图片存储目录
UPLOAD_DIR = Path(_env("SHIYE_STORAGE_DIR", str(BASE_DIR / "storage")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# OCR 引擎：baidu（百度手写 API，默认）| rapidocr（本地免费，需装 requirements-rapidocr.txt）| none
# M0 实测结论（33 张真实手写笔记 A/B 对照）：百度平均置信 0.947~0.997（均值 0.982），内容基本正确；
# RapidOCR 平均置信 0.640~0.779（均值 0.705），乱字明显（立体几何→立体n付）。详见 docs/m0-ocr-选型结论.md
OCR_PROVIDER = _env("SHIYE_OCR", "baidu")

# OCR 请求超时秒数（百度 token 换取与识别请求共用）
OCR_TIMEOUT_SECONDS = int(_env("SHIYE_OCR_TIMEOUT_SECONDS", "30"))

# 百度智能云 OCR（手写文字识别 https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting）
BAIDU_API_KEY = _env("SHIYE_BAIDU_API_KEY", "")
BAIDU_SECRET_KEY = _env("SHIYE_BAIDU_SECRET_KEY", "")

# 上传限制：单张 20MB、批量一次最多 20 张
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_BATCH_FILES = 20

# AI 笔记整理（DeepSeek，OpenAI 兼容 API）
DEEPSEEK_API_KEY = _env("SHIYE_DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = _env("SHIYE_DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = _env("SHIYE_DEEPSEEK_MODEL", "deepseek-chat")

# AI 学情报告限流：每用户冷却秒数（默认 300 = 5 分钟）
STUDY_REPORT_COOLDOWN_SECONDS = int(_env("SHIYE_STUDY_REPORT_COOLDOWN_SECONDS", "300"))

# AI 测评（出题）限流：每用户冷却秒数（默认 60 = 1 分钟；与学情报告独立）
QUIZ_COOLDOWN_SECONDS = int(_env("SHIYE_QUIZ_COOLDOWN_SECONDS", "60"))

# 运行时配置校验阈值
_MIN_SECRET_KEY_LEN = 32

_logger = logging.getLogger("app.config")


def validate_runtime_config() -> None:
    """运行时配置校验：在 main.py lifespan 启动时调用（create_all 之前）

    - DEV_MODE=true → 不抛错，但用 logging.warning 打印醒目中文警告
    - DEV_MODE=false → SECRET_KEY 为空、等于默认值、或长度 < 32 → 抛 RuntimeError
    """
    # OCR 配置校验（T3-2）：无论 DEV_MODE 都执行
    # OCR 配置错会让所有上传页静默 failed，开发模式也不应豁免
    _validate_ocr_config()

    if DEV_MODE:
        if not SECRET_KEY or SECRET_KEY == "dev-secret-change-me" or len(SECRET_KEY) < _MIN_SECRET_KEY_LEN:
            _logger.warning(
                "⚠️ 当前使用开发默认密钥，仅限本地调试。"
                "公网/生产必须设置 SHIYE_SECRET_KEY 为 ≥%d 位随机字符串，"
                "生成命令：python -c \"import secrets;print(secrets.token_urlsafe(48))\"",
                _MIN_SECRET_KEY_LEN,
            )
        return

    # DEV_MODE=false → 强制校验 SECRET_KEY
    problems = []
    if not SECRET_KEY:
        problems.append("SECRET_KEY 为空")
    elif SECRET_KEY == "dev-secret-change-me":
        problems.append("SECRET_KEY 仍为默认值 dev-secret-change-me")
    elif len(SECRET_KEY) < _MIN_SECRET_KEY_LEN:
        problems.append(f"SECRET_KEY 长度不足（{len(SECRET_KEY)} < {_MIN_SECRET_KEY_LEN}）")

    if problems:
        raise RuntimeError(
            "配置校验失败：" + "；".join(problems) + "。"
            f"请用以下命令生成强密钥并写入环境变量 SHIYE_SECRET_KEY："
            f"python -c \"import secrets;print(secrets.token_urlsafe(48))\""
        )


def _validate_ocr_config() -> None:
    """OCR 配置校验：配置错就不许起，别再静默标 failed

    - none -> 不抛，warning 提示 OCR 已禁用
    - baidu -> 缺 key 抛 RuntimeError（含缺失变量名 + 申请指引 + 临时关闭提示）
    - rapidocr -> 缺依赖抛 RuntimeError（含安装命令 + 300MB 提示）
    - 其它值 -> 抛 RuntimeError 列出合法取值
    """
    import importlib.util

    if OCR_PROVIDER == "none":
        _logger.warning("OCR 已禁用（SHIYE_OCR=none），上传的页不会识别")
        return

    if OCR_PROVIDER == "baidu":
        missing = []
        if not BAIDU_API_KEY:
            missing.append("SHIYE_BAIDU_API_KEY")
        if not BAIDU_SECRET_KEY:
            missing.append("SHIYE_BAIDU_SECRET_KEY")
        if missing:
            raise RuntimeError(
                "OCR=baidu 但缺少百度凭据：" + "、".join(missing) + "。"
                "请在百度智能云控制台「文字识别」应用获取 API Key/Secret Key"
                "（https://console.bce.baidu.com/ai/），写入对应环境变量。"
                "要临时关掉 OCR 可设 SHIYE_OCR=none。"
            )
        return

    if OCR_PROVIDER == "rapidocr":
        if importlib.util.find_spec("rapidocr_onnxruntime") is None:
            raise RuntimeError(
                "OCR=rapidocr 但未安装依赖 rapidocr_onnxruntime。"
                "请运行 pip install -r requirements-rapidocr.txt 安装（需下载约 300MB 模型）。"
                "要临时关掉 OCR 可设 SHIYE_OCR=none。"
            )
        return

    raise RuntimeError(
        "OCR 配置非法：SHIYE_OCR=" + repr(OCR_PROVIDER) + "，合法取值为 baidu|rapidocr|none。"
    )
