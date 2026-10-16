"""图片 URL 签名/校验：S3 风格短时签名 URL

安全设计：
- sign_url 产出相对路径 `/files/{key}?e={exp}&s={sig}`，HMAC-SHA256
- 被签载荷用 JSON 编码 {"u":user_id,"k":key,"e":exp}，避免分隔符歧义
- verify 常量时间比较（hmac.compare_digest），留 60 秒时钟偏差余量
- TTL 下限 60 秒，配置非法时抛错（不静默签发立刻失效的链接）
- SECRET_KEY 绝不出现在任何 URL 或响应体里
- 签名 URL 语义：**持有即授权**（15 分钟内任何人拿到链接均可访问），
  泄露应对：缩短 TTL / 刷新列表即失效（旧 e 过期返回 403，前端重新拉接口拿新签名）
"""
import hmac
import json
import time

from app.config import FILE_URL_TTL_SECONDS, SECRET_KEY

_MIN_TTL = 60  # TTL 下限：低于此值会抛错，防止静默签发立刻失效的链接


def _sig_payload(user_id: int, key: str, exp: int) -> bytes:
    """构造被签内容：JSON 编码，避免 key 含分隔符时的歧义"""
    return json.dumps(
        {"u": user_id, "k": key, "e": exp},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _compute_sig(user_id: int, key: str, exp: int) -> str:
    """HMAC-SHA256，输出 64 位 hex"""
    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        _sig_payload(user_id, key, exp),
        "sha256",
    ).hexdigest()


def sign_url(key: str, user_id: int, ttl_seconds: int | None = None) -> str:
    """生成签名相对路径：/files/{key}?e={exp}&s={sig}

    - key 里的 `/` 不做 URL 编码（否则路由 {key:path} 匹配不到）
    - ttl_seconds 为 None 时用配置默认值；低于 60 秒会抛 ValueError
    - ttl 为负数时显式允许（用于测试过期场景），不抛错
    """
    if ttl_seconds is None:
        ttl_seconds = FILE_URL_TTL_SECONDS
    # 正数 TTL 必须不低于下限；负数（测试用）放行
    if ttl_seconds >= 0 and ttl_seconds < _MIN_TTL:
        raise ValueError(
            f"FILE_URL_TTL_SECONDS 必须 >= {_MIN_TTL} 秒，当前为 {ttl_seconds}"
        )
    exp = int(time.time()) + int(ttl_seconds)
    sig = _compute_sig(user_id, key, exp)
    return f"/files/{key}?e={exp}&s={sig}"


def verify(key: str, user_id: int, exp: str | int, sig: str) -> bool:
    """校验签名是否有效且未过期

    - 常量时间比较（hmac.compare_digest）
    - 留 60 秒时钟偏差余量（exp 后 60s 内仍放行）
    - 被签内容绑定 user_id + key + exp，任一不一致都会失败
    """
    try:
        exp_int = int(exp)
    except (TypeError, ValueError):
        return False
    # 过期判断：当前时间 > exp + 60s 宽限 → 失败
    if time.time() > exp_int + 60:
        return False
    expected = _compute_sig(user_id, key, exp_int)
    try:
        return hmac.compare_digest(expected, str(sig))
    except Exception:
        return False
