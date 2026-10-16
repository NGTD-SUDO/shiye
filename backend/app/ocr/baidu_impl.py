"""百度智能云手写文字识别 API 实现

接口：POST https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting
鉴权：先用 API Key/Secret Key 换 access_token（有效期 30 天，本地缓存）
计费：按量计费，约 0.005 元/次，需在百度智能云控制台开通文字识别服务

T3-4：超时可配置（OCR_TIMEOUT_SECONDS）；错误码/异常映射为可操作中文文案。
"""
import base64
import time
from pathlib import Path

import httpx

from app.config import BAIDU_API_KEY, BAIDU_SECRET_KEY, OCR_TIMEOUT_SECONDS
from app.ocr.base import OcrProvider, OcrResult

_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
_HANDWRITING_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting"
_TOKEN_EXPIRE_SAFETY = 3600  # 提前 1 小时刷新，避免临界过期


def _map_baidu_error(error_code: int, error_msg: str) -> str:
    """把百度 error_code 映射为可操作中文文案（T3-4）

    - 110/111（token 无效/失效）-> 鉴权失败
    - 17/18/19（日/月配额、并发超限）-> 配额或并发超限
    - 其它 -> 保留 error_code + error_msg
    """
    if error_code in (110, 111):
        return (
            f"百度 OCR 鉴权失败（error_code={error_code}）：请检查 SHIYE_BAIDU_API_KEY / SHIYE_BAIDU_SECRET_KEY"
            f"是否正确且已开通文字识别服务"
        )
    if error_code in (17, 18, 19):
        return f"百度 OCR 调用配额或并发超限（error_code={error_code}），请稍后重试"
    return f"百度 OCR 错误 {error_code}: {error_msg}"


def _map_httpx_error(exc: Exception, timeout: int) -> str:
    """把 httpx 异常映射为可操作中文文案（T3-4）"""
    if isinstance(exc, httpx.TimeoutException):
        return f"请求百度 OCR 超时（{timeout}s），请检查网络后重试"
    if isinstance(exc, httpx.ConnectError):
        return "连接百度 OCR 失败，请检查服务器网络"
    return f"请求百度 OCR 网络异常: {exc}"


class BaiduOcrProvider(OcrProvider):
    """百度手写 OCR；懒加载 access_token 并缓存"""

    def __init__(self) -> None:
        if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
            raise RuntimeError(
                "未配置百度 OCR 凭据（SHIYE_BAIDU_API_KEY / SHIYE_BAIDU_SECRET_KEY）"
            )
        self._token: str | None = None
        self._token_expire_at: float = 0.0

    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expire_at:
            return self._token
        try:
            with httpx.Client(timeout=OCR_TIMEOUT_SECONDS) as client:
                resp = client.get(
                    _TOKEN_URL,
                    params={
                        "grant_type": "client_credentials",
                        "client_id": BAIDU_API_KEY,
                        "client_secret": BAIDU_SECRET_KEY,
                    },
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(_map_httpx_error(exc, OCR_TIMEOUT_SECONDS)) from exc
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"百度 access_token 获取失败: {data.get('error_description', data)}")
        self._token = data["access_token"]
        self._token_expire_at = now + int(data.get("expires_in", 2592000)) - _TOKEN_EXPIRE_SAFETY
        return self._token

    def recognize(self, image_path: Path) -> OcrResult:
        with image_path.open("rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("ascii")

        token = self._get_token()
        try:
            with httpx.Client(timeout=OCR_TIMEOUT_SECONDS) as client:
                resp = client.post(
                    _HANDWRITING_URL,
                    params={"access_token": token},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={"image": img_b64, "probability": "true"},
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(_map_httpx_error(exc, OCR_TIMEOUT_SECONDS)) from exc
        data = resp.json()

        if "error_code" in data:
            raise RuntimeError(_map_baidu_error(data["error_code"], data.get("error_msg", "")))

        words = [item.get("words", "") for item in data.get("words_result", [])]
        text = "\n".join(w for w in words if w)

        # 取每行 probability.average 的均值作为整页置信度
        confs: list[float] = []
        for item in data.get("words_result", []):
            prob = item.get("probability")
            if isinstance(prob, dict) and prob.get("average") is not None:
                try:
                    confs.append(float(prob["average"]))
                except (TypeError, ValueError):
                    pass
        avg_conf = (sum(confs) / len(confs)) if confs else None
        return OcrResult(text=text, conf=avg_conf)
