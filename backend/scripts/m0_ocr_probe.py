"""M0 技术验证：RapidOCR 手写笔记实测脚本

用法：
    python scripts/m0_ocr_probe.py <样本图片目录> [--out 报告.csv]

对目录下每张图片做一次识别，统计耗时 / 平均置信度 / 识别文本长度，
输出人眼可读的汇总（终端）并保存 CSV（默认写在样本目录同级的 m0_report.csv）。

判断依据（来自开发文档 6.2/6.3）：工整手写主观可读即认为基本可用；
识别质量差的页靠「校对闭环」兜底，最终选型结论请人工结合 CSV 每行文本评估。
"""
import argparse
import csv
import sys
import time
from pathlib import Path

# 允许从 backend/ 目录直接运行（python scripts/m0_ocr_probe.py）
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ocr.rapidocr_impl import RapidOcrProvider  # noqa: E402

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
PREVIEW_LEN = 60


def run(folder: Path, out_path: Path) -> int:
    images = sorted(
        p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS
    )
    if not images:
        print(f"目录中没有图片（支持 {sorted(IMAGE_EXTS)}）：{folder}")
        return 1

    print(f"共 {len(images)} 张图片待识别\n")
    provider = RapidOcrProvider()
    rows = []
    total_chars = 0
    for img in images:
        start = time.perf_counter()
        result = provider.recognize(img)
        elapsed = time.perf_counter() - start
        text = result.text or ""
        conf = result.conf if result.conf is not None else 0.0
        total_chars += len(text.strip())
        rows.append(
            {
                "file": img.name,
                "elapsed_s": round(elapsed, 2),
                "conf": round(conf, 3) if conf else "",
                "chars": len(text.strip()),
                "preview": text.strip()[:PREVIEW_LEN].replace("\n", " ⏎ "),
            }
        )
        print(
            f"[{img.name}] 耗时 {elapsed:5.1f}s  置信 {conf:.2f}  "
            f"文本 {len(text.strip()):4d} 字  {text.strip()[:PREVIEW_LEN]}"
        )

    avg_conf = sum(r["conf"] for r in rows if r["conf"] != "") / len(rows)
    avg_time = sum(r["elapsed_s"] for r in rows) / len(rows)
    print(
        f"\n汇总：{len(rows)} 张，平均耗时 {avg_time:.1f}s/张，"
        f"平均置信 {avg_conf:.3f}，总识别字数 {total_chars}"
    )

    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "elapsed_s", "conf", "chars", "preview"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n报告已保存：{out_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="RapidOCR 手写笔记 M0 实测")
    parser.add_argument("folder", type=Path, help="样本图片目录")
    parser.add_argument("--out", type=Path, default=None, help="CSV 报告路径（默认与样本目录同级）")
    args = parser.parse_args()
    if not args.folder.is_dir():
        print(f"目录不存在：{args.folder}")
        sys.exit(1)
    out = args.out or (args.folder.parent / "m0_report.csv")
    sys.exit(run(args.folder, out))


if __name__ == "__main__":
    main()
