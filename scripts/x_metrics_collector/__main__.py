"""CLIエントリポイント。

使い方:
    python -m scripts.x_metrics_collector --post-id p-20260803-001 --dry-run
    python -m scripts.x_metrics_collector --post-id p-20260803-001
    python -m scripts.x_metrics_collector --all-pending

詳細な手順は scripts/x_metrics_collector/README.md を参照。
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from typing import Any

from .collector import CHECK_WINDOW, build_metrics_row, collect_for_post
from .config import Config, load_config
from .sheets_client import SheetsClient

_MIN_AGE = dt.timedelta(hours=24)


def _is_ready_for_collection(post: dict[str, Any], now: dt.datetime) -> bool:
    """posted_atから24時間以上経過しているかを判定する。

    posted_atが読めない場合は対象に含める（手動実行前提のため、判定を厳密にしすぎて
    取りこぼすより実行してみて人間の判断に委ねる方を優先する）。
    """
    posted_at_raw = post.get("posted_at")
    if not posted_at_raw:
        return False  # 未投稿（selected_for_postのみ等）は対象外
    try:
        posted_at = dt.datetime.fromisoformat(str(posted_at_raw))
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return True
    return (now - posted_at) >= _MIN_AGE


def _collect_and_write(
    post: dict[str, Any],
    sheets: SheetsClient,
    config: Config,
    now: dt.datetime,
    dry_run: bool,
) -> None:
    post_id = post.get("post_id", "")
    existing_rows = sheets.get_metrics_24h_rows()
    existing_idx = sheets.find_metrics_row_index(post_id, CHECK_WINDOW)
    existing_row = existing_rows[existing_idx - 2] if existing_idx else None

    if existing_row and existing_row.get("data_quality") == "manual":
        print(f"[skip] post_id={post_id} は手動入力(manual)のため上書きしません")
        return

    result = collect_for_post(post, config, now=now)
    row = build_metrics_row(
        result,
        existing_rows,
        existing_snapshot_id=existing_row.get("snapshot_id") if existing_row else None,
        now=now,
    )

    print(f"post_id={post_id} data_quality={row['data_quality']} notes={row['notes'] or '-'}")
    if dry_run:
        print("  (--dry-run のため書き込みは行いません)")
        print(f"  row = {row}")
        return

    sheets.upsert_metrics_row(row, existing_idx)
    action = "更新" if existing_idx else "追記"
    print(f"  metrics_24h へ{action}しました (snapshot_id={row['snapshot_id']})")


def _process_one(post_id_target: str, sheets: SheetsClient, config: Config, now: dt.datetime, dry_run: bool) -> None:
    posts = sheets.get_posts()
    target = next((p for p in posts if p.get("post_id") == post_id_target), None)
    if target is None:
        print(f"[skip] post_id={post_id_target} が posts シートに見つかりません", file=sys.stderr)
        return
    _collect_and_write(target, sheets, config, now, dry_run)


def _process_all_pending(sheets: SheetsClient, config: Config, now: dt.datetime, dry_run: bool) -> None:
    posts = sheets.get_posts()
    metrics_rows = sheets.get_metrics_24h_rows()
    done_post_ids = {
        row.get("post_id")
        for row in metrics_rows
        if row.get("check_window") == CHECK_WINDOW and row.get("data_quality") in ("ok", "manual")
    }
    targets = [
        p
        for p in posts
        if p.get("posted_url")
        and p.get("post_id") not in done_post_ids
        and _is_ready_for_collection(p, now)
    ]
    if not targets:
        print("処理対象なし（24時間未経過、またはすべて取得済みです）")
        return
    for post in targets:
        _collect_and_write(post, sheets, config, now, dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description="X 24時間後メトリクス半自動回収（最小実装）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--post-id", help="対象のpost_idを1件指定する")
    group.add_argument(
        "--all-pending",
        action="store_true",
        help="posted_atから24時間以上経過し、metrics_24hがok/manualでない投稿をまとめて処理する",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Sheetsへの書き込みを行わず、結果を表示するのみ"
    )
    args = parser.parse_args()

    config = load_config()
    sheets = SheetsClient(config)
    now = dt.datetime.now(dt.timezone.utc)

    if args.post_id:
        _process_one(args.post_id, sheets, config, now, args.dry_run)
    else:
        _process_all_pending(sheets, config, now, args.dry_run)


if __name__ == "__main__":
    main()
