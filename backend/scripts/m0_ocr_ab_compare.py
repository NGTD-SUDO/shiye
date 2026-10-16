"""M0 A/B 对照：RapidOCR vs 百度手写识别

对样本目录中的图片依次用两个引擎识别，输出每页的
[耗时/置信度/字数/文本预览] 对照表，并保存 CSV。

用法（需先配置百度凭据到 .env 或环境变量）：
    python scripts/m0_ocr_ab_compare.py <样本目录> [--out docs/m0/m0_ab_report.csv]

百度凭据通过环境变量 SHIYE_BAIDU_API_KEY / SHIYE_BAIDU_SECRET_KEY 注入。
"""
import argparse
import csv
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ocr.rapidocr_impl import RapidOcrProvider  # noqa: E402
from app.ocr.baidu_impl import BaiduOcrProvider  # noqa: E402

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
PREVIEW_LEN = 50


def _recognize(provider, path: Path, retries: int = 3) -> tuple[float, float | None, int, str]:
    start = time.perf_counter()
    last_exc = None
    for attempt in range(retries):
        try:
            result = provider.recognize(path)
            elapsed = time.perf_counter() - start
            return elapsed, result.conf, len(result.text.strip()), result.text or ""
        except Exception as exc:
            last_exc = exc
            time.sleep(1.0 * (attempt + 1))
    raise last_exc


def main() -> None:
    parser = argparse.ArgumentParser(description="M0 OCR A/B 对照：RapidOCR vs 百度手写")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None, help="只测前 N 张（可选）")
    args = parser.parse_args()

    if not args.folder.is_dir():
        print(f"目录不存在: {args.folder}")
        sys.exit(1)

    images = sorted(p for p in args.folder.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if args.limit:
        images = images[: args.limit]
    if not images:
        print("无图片")
        sys.exit(1)

    print(f"共 {len(images)} 张图片，开始 A/B 对照...\n")
    print(f"{'文件名':<32} {'Rapid耗时':>8} {'Rapid置信':>8} {'百度耗时':>8} {'百度置信':>8}")
    print("-" * 80)

    rapid = RapidOcrProvider()
    baidu = BaiduOcrProvider()
    rows: list[dict] = []
    r_confs, b_confs = [], []

    for img in images:
        try:
            r_time, r_conf, r_chars, r_text = _recognize(rapid, img)
            b_time, b_conf, b_chars, b_text = _recognize(baidu, img)
            time.sleep(0.6)  # 百度免费版 QPS 限流，间隔规避
        except Exception as exc:
            print(f"[{img.name}] 失败: {exc}")
            time.sleep(0.6)
            continue

        if r_conf is not None:
            r_confs.append(r_conf)
        if b_conf is not None:
            b_confs.append(b_conf)

        print(
            f"{img.name[:30]:<32} "
            f"{r_time:>7.1f}s {r_conf or 0:>7.3f}  "
            f"{b_time:>7.1f}s {b_conf or 0:>7.3f}"
        )
        rows.append(
            {
                "file": img.name,
                "rapid_time": round(r_time, 2),
                "rapid_conf": round(r_conf, 3) if r_conf else "",
                "rapid_chars": r_chars,
                "rapid_text": r_text[:200].replace("\n", " ⏎ "),
                "baidu_time": round(b_time, 2),
                "baidu_conf": round(b_conf, 3) if b_conf else "",
                "baidu_chars": b_chars,
                "baidu_text": b_text[:200].replace("\n", " ⏎ "),
            }
        )

    print("\n" + "=" * 80)
    if r_confs:
        print(f"RapidOCR  平均置信 {sum(r_confs)/len(r_confs):.3f}")
    if b_confs:
        print(f"百度手写   平均置信 {sum(b_confs)/len(b_confs):.3f}")

    out = args.out or (args.folder.parent / "m0_ab_report.csv")
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "file", "rapid_time", "rapid_conf", "rapid_chars", "rapid_text",
            "baidu_time", "baidu_conf", "baidu_chars", "baidu_text",
        ])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n报告: {out}")


if __name__ == "__main__":
    main()
