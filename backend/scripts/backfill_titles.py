"""T6-2 存量页重取标题脚本（默认 dry-run）

扫描所有 ocr_state='done' 且有 ocr_text 的页，用 is_noise_title 判定
只挑「噪声标题」的页重算（extract_title 从真实 OCR 文本抽取），
绝不用文件名/时间戳兜底，绝不无差别重算覆盖用户手改的有意义标题。

用法：
    python scripts/backfill_titles.py          # dry-run，只打印不改库
    python scripts/backfill_titles.py --apply  # 真正写库 + 同步 FTS
"""
import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import Session  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.page import OCR_DONE, Page  # noqa: E402
from app.services import fts  # noqa: E402
from app.services.title_extractor import extract_title, is_noise_title  # noqa: E402

TITLE_MAX_LEN = 40
MAX_EXAMPLES = 10


def backfill(db: Session, apply: bool = False) -> dict:
    """扫描并重算噪声标题。返回统计 dict（无副作用于 db，除非 apply=True）。

    判定只依据 is_noise_title（标题本身是否为噪声），因此不会碰用户手工改成的
    有意义标题。已知取舍：若用户手工把标题改成纯数字/时间这类噪声形态，会被覆盖——
    这是为清理 26/29 页时间戳噪声而接受的取舍（见变更说明）。
    """
    all_pages = db.query(Page).all()
    skipped = {"not_done": 0, "no_text": 0, "title_ok": 0}
    changed: list[tuple[int, str, str]] = []  # (page_id, old_title, new_title)

    for page in all_pages:
        if page.ocr_state != OCR_DONE:
            skipped["not_done"] += 1
            continue
        if not (page.ocr_text or "").strip():
            skipped["no_text"] += 1
            continue
        if not is_noise_title(page.title or "", page.ocr_text):
            skipped["title_ok"] += 1
            continue
        # 噪声标题 → 从真实 OCR 文本重取（无可用行则返回空串）
        new_title = extract_title(page.ocr_text, max_len=TITLE_MAX_LEN)
        if new_title == (page.title or ""):
            # 重算无变化（如空标题且 OCR 无可用行），不计入修改
            skipped["title_ok"] += 1
            continue
        changed.append((page.id, page.title or "", new_title))
        if apply:
            page.title = new_title
            # 改标题必须同步 FTS，否则搜索命不中
            fts.upsert_page(db, page.id, page.title, page.ocr_text)

    if apply:
        db.commit()

    return {
        "scanned": len(all_pages),
        "changed": len(changed),
        "examples": changed[:MAX_EXAMPLES],
        "skipped": skipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="存量页重取标题（默认 dry-run）")
    parser.add_argument("--apply", action="store_true", help="真正写库并同步 FTS（默认 dry-run）")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = backfill(db, apply=args.apply)
    finally:
        db.close()

    print(f"扫描页数：{result['scanned']}")
    print(f"命中噪声页数：{result['changed']}")
    print(
        "跳过：未完成 %d / 无文本 %d / 标题已正常 %d"
        % (result["skipped"]["not_done"], result["skipped"]["no_text"], result["skipped"]["title_ok"])
    )
    if result["examples"]:
        print("改前 → 改后（最多 10 条）：")
        for pid, old, new in result["examples"]:
            print(f"  [{pid}] {old!r} -> {new!r}")
    if args.apply:
        print("已应用（--apply）：标题与 FTS 已更新")
    else:
        print("（dry-run，未写库。加 --apply 才会真正修改）")


if __name__ == "__main__":
    main()
