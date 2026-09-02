"""pre_teacher_candidate確定済みの投稿者を、深掘り監視対象アカウントへ自動登録するCLI。

x_api_phase2_classify.pyが出力した outputs/x_api_phase2/pre_teacher_candidate.json を
**読み取り専用で参照するだけ**の独立した後段ステップ（scripts/accumulate_phase1_collection.py
が既存パイプラインの出力を読み取り専用で参照し別ファイルへ追記するのと同じ設計パターン）。

_classify()/_classify_core()/_apply_engagement_gate()本体には一切手を入れない
（importも呼び出しも行わない。このスクリプトはPhase 2の出力ファイルを読むだけで、
分類ロジック自体には触れない）。

**運用上の既知の制約**: 現時点でこのスクリプトを自動実行するworkflowステップは無い
（.github/workflows/phase1_daily_collection.yml本体を変更しない、という制約があるため。
詳細はops/reports/teacher_account_deepdive_design_2026-09-01.mdの実装時の報告を参照）。
当面は、ローカルでx_api_phase2_classify.pyを実行した直後に手動でこのスクリプトを実行する
運用を想定する。

使い方:
    python scripts/register_watched_accounts.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from watched_account_state import (
    load_watched_account_state_store,
    register_or_reactivate_watched_account,
    save_watched_account_state_store,
)
from watched_account_store import append_new_watched_accounts

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PRE_TEACHER_CANDIDATE_PATH = _REPO_ROOT / "outputs" / "x_api_phase2" / "pre_teacher_candidate.json"
_WATCHED_ACCOUNTS_LOG_PATH = _REPO_ROOT / "ops" / "data" / "watched_accounts.jsonl"
_WATCHED_ACCOUNT_STATE_PATH = _REPO_ROOT / "ops" / "data" / "watched_account_state.json"


def main() -> None:
    if not _PRE_TEACHER_CANDIDATE_PATH.exists():
        print(
            f"警告: {_PRE_TEACHER_CANDIDATE_PATH} が見つかりません。登録は行いません。",
            file=sys.stderr,
        )
        sys.exit(1)

    records = json.loads(_PRE_TEACHER_CANDIDATE_PATH.read_text(encoding="utf-8"))
    observed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 登録イベントログ用: author_id初出時のみ1件（post_id/query_source付き）。
    # 同一バッチ内に同じauthor_idの複数レコードがあっても最初の1件のみ使う
    # （append_new_watched_accounts()自体もauthor_id基準でdedupするが、渡す候補も
    # 1 author_id=1候補に絞っておくことでログの意味を明確にする）。
    seen_author_ids_in_batch: set[str] = set()
    log_candidates: list[dict] = []
    for record in records:
        author_id = record.get("author_id")
        if not author_id or author_id in seen_author_ids_in_batch:
            continue
        seen_author_ids_in_batch.add(author_id)
        log_candidates.append(
            {
                "author_id": author_id,
                "first_seen_as_teacher_post_id": record.get("post_id"),
                "first_seen_as_teacher_query_source": record.get("query_source"),
            }
        )

    log_result = append_new_watched_accounts(_WATCHED_ACCOUNTS_LOG_PATH, log_candidates, registered_at=observed_at)

    # 状態ストア更新: 新規登録・既存active観測・graduatedからの復帰をすべて反映する。
    # ログ側のdedup（初出のみ）とは独立に、このバッチで観測された全author_idについて
    # teacher_count加算・復帰判定を行う（同じauthor_idが複数post_idでヒットしていても
    # 1バッチ内では1回のみ加算する＝ログ側と同じseen_author_ids_in_batchを再利用する）。
    store = load_watched_account_state_store(_WATCHED_ACCOUNT_STATE_PATH)
    reactivated: list[str] = []
    newly_registered: list[str] = []
    for author_id in seen_author_ids_in_batch:
        was_known = author_id in store
        was_graduated = was_known and store[author_id].watch_status == "graduated"
        register_or_reactivate_watched_account(store, author_id, observed_at=observed_at)
        if not was_known:
            newly_registered.append(author_id)
        elif was_graduated:
            reactivated.append(author_id)

    save_watched_account_state_store(store, _WATCHED_ACCOUNT_STATE_PATH)

    print(f"pre_teacher_candidate件数: {len(records)}件（ユニークauthor_id: {len(seen_author_ids_in_batch)}件）")
    print(f"登録イベントログ追記: 新規{log_result['appended_count']}件、既存スキップ{log_result['skipped_duplicate_count']}件")
    print(f"状態ストア: 新規登録{len(newly_registered)}件、graduatedからの復帰{len(reactivated)}件")
    print(f"保存先: {_WATCHED_ACCOUNTS_LOG_PATH} / {_WATCHED_ACCOUNT_STATE_PATH}")


if __name__ == "__main__":
    main()
