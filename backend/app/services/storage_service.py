"""图片存储：落盘、缩略图生成、路径安全校验

上传安全：
- 文件头 magic 校验（只接受真实 JPEG/PNG/WEBP/BMP）
- 像素上限（单边 ≤ 12000，总像素 ≤ 40_000_000）
- DecompressionBombError 捕获
- 无「原样落盘」兜底分支（非图片一律 400）
- validate_image_bytes 为纯函数，可直接单测
"""
import io
import logging
import uuid
from pathlib import Path

from PIL import Image, ImageOps

from app.config import MAX_UPLOAD_BYTES, UPLOAD_DIR

_logger = logging.getLogger(__name__)

_THUMB_MAX_EDGE = 480

# 像素上限
_MAX_SINGLE_EDGE = 12000
_MAX_TOTAL_PIXELS = 40_000_000

# 文件头 magic（前 12 字节足够判断）
_MAGIC = {
    b"\xff\xd8\xff": "JPEG",
    b"\x89PNG\r\n\x1a\n": "PNG",
    b"RIFF": "WEBP",  # RIFF....WEBP
    b"BM": "BMP",
}


def path_for(key: str) -> Path:
    """把存储 key 映射为绝对路径，防目录穿越"""
    if not key or key.startswith(("/", "\\")) or ".." in key.split("/"):
        raise ValueError(f"非法的存储 key: {key}")
    path = (UPLOAD_DIR / key).resolve()
    if not str(path).startswith(str(UPLOAD_DIR.resolve())):
        raise ValueError(f"非法的存储 key: {key}")
    return path


def validate_image_bytes(data: bytes) -> None:
    """纯函数：校验图片字节是否合法（magic + 像素 + 解压炸弹）

    不落盘、无副作用，可直接单测。
    - 空/超限 → ValueError
    - 非图片 magic → ValueError（带「不支持的文件格式」）
    - 像素超限 → ValueError（带实际尺寸）
    - 解压炸弹 → ValueError
    """
    if not data:
        raise ValueError("空文件")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("文件超过 20MB 限制")

    # 文件头 magic 校验（前 12 字节）
    head = data[:12]
    fmt = None
    for magic, name in _MAGIC.items():
        if head.startswith(magic):
            fmt = name
            break
    if fmt is None:
        raise ValueError("不支持的文件格式，请上传图片（JPEG/PNG/WEBP/BMP）")

    # 设置 DecompressionBomb 阈值（Pillow 基于 header size 检查）
    Image.MAX_IMAGE_PIXELS = _MAX_TOTAL_PIXELS

    # 先 open 拿 size 做像素预校验，避免触发解压炸弹时拿不到尺寸
    try:
        img = Image.open(io.BytesIO(data))
        w, h = img.size
    except Image.DecompressionBombError as e:
        # open 阶段 Pillow 基于 header size 检查 MAX_IMAGE_PIXELS，超限即抛
        raise ValueError(f"图片尺寸过大（解压炸弹风险）: {e}") from e
    except (Image.UnidentifiedImageError, OSError) as e:
        raise ValueError(f"图片解析失败（不支持的文件格式，请上传图片）: {e}") from e

    # 像素校验（单边/总像素）
    if w > _MAX_SINGLE_EDGE or h > _MAX_SINGLE_EDGE:
        raise ValueError(f"图片尺寸过大（{w}x{h}，单边不超过 {_MAX_SINGLE_EDGE}）")
    if w * h > _MAX_TOTAL_PIXELS:
        raise ValueError(f"图片尺寸过大（{w}x{h}，总像素 {w * h} 超过 {_MAX_TOTAL_PIXELS}）")

    # 真正解码像素数据，可能再次触发 DecompressionBombError（header size 伪造场景）
    try:
        img.load()
    except Image.DecompressionBombError as e:
        raise ValueError(f"图片尺寸过大（解压炸弹风险，{w}x{h}）: {e}") from e
    except (Image.UnidentifiedImageError, OSError) as e:
        raise ValueError(f"图片解析失败（不支持的文件格式，请上传图片）: {e}") from e


def _save_processed(
    user_id: int, base_name: str, img: Image.Image, quality: int = 88
) -> dict:
    """把已打开的图片以 JPEG 落盘（原图）并生成缩略图，返回 key 信息"""
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    width, height = img.size

    folder = UPLOAD_DIR / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)

    orig_key = f"{user_id}/{base_name}.jpg"
    img.save(folder / f"{base_name}.jpg", "JPEG", quality=quality)

    thumb = img.copy()
    thumb.thumbnail((_THUMB_MAX_EDGE, _THUMB_MAX_EDGE), Image.LANCZOS)
    thumb_key = f"{user_id}/{base_name}_thumb.jpg"
    thumb.save(folder / f"{base_name}_thumb.jpg", "JPEG", quality=82)

    return {
        "image_key": orig_key,
        "thumb_key": thumb_key,
        "width": width,
        "height": height,
    }


def save_image_bytes(user_id: int, data: bytes, filename: str) -> dict:
    """保存上传的图片。先 validate_image_bytes 校验，再归一化为 JPEG + 缩略图。

    非图片/像素超限/解压炸弹一律抛 ValueError（由路由转 400），
    不再有「原样落盘」兜底分支。
    """
    validate_image_bytes(data)  # 可能抛 ValueError

    base_name = uuid.uuid4().hex
    Image.MAX_IMAGE_PIXELS = _MAX_TOTAL_PIXELS
    img = Image.open(io.BytesIO(data))
    img.load()
    return _save_processed(user_id, base_name, img)


def delete_keys(keys: list[str | None]) -> None:
    """删除一组存储文件，忽略不存在的文件"""
    for key in keys:
        if not key:
            continue
        try:
            path_for(key).unlink(missing_ok=True)
        except ValueError:
            continue
