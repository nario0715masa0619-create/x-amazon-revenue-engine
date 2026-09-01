"""Phase 1収集結果（outputs/x_api_phase1/merged_deduped.json）を
累積ストア（ops/data/x_api_phase1_cumulative.jsonl）へ追記するCLIラッパー。

.github/workflows/phase1_daily_collection.ymlから、
scripts/x_api_phase1_collect.py実行直後・scripts/x_api_phase2_classify.py実行前に
呼び出される想定（呼び出し順はどちらが先でも累積処理自体には影響しない。
merged_deduped.jsonを読み取り専用で参照するのみ）。

merged_deduped.json・Phase 2 classifyの入出力パスには一切書き込まない
（読み取り専用で参照するのみ）。

使い方:
    python scripts/accumulate_phase1_collection.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cumulative_post_store import append_new_posts

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MERGED_DEDUPED_PATH = _REPO_ROOT / "outputs" / "x_api_phase1" / "merged_deduped.json"
_CUMULATIVE_STORE_PATH = _REPO_ROOT / "ops" / "data" / "x_api_phase1_cumulative.jsonl"


def main() -> None:
    if not _MERGED_DEDUPED_PATH.exists():
        print(f"警告: {_MERGED_DEDUPED_PATH} が見つかりません。累積は行いません。", file=sys.stderr)
        sys.exit(1)

    posts = json.loads(_MERGED_DEDUPED_PATH.read_text(encoding="utf-8"))
    collected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = append_new_posts(_CUMULATIVE_STORE_PATH, posts, collected_at=collected_at)

    print(
        f"累積ストア更新: 新規追加={result['appended_count']}件, "
        f"重複スキップ={result['skipped_duplicate_count']}件, "
        f"累積総数={result['total_before']}→{result['total_after']}件"
    )
    print(f"保存先: {_CUMULATIVE_STORE_PATH}")


if __name__ == "__main__":
    main()
