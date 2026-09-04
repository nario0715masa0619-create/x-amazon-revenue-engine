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
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from company_account_detector import detect_company_account_signal
from watched_account_state import (
    create_pending_review_watched_account,
    load_watched_account_state_store,
    register_or_reactivate_watched_account,
    save_watched_account_state_store,
)
from watched_account_store import append_new_watched_accounts

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PRE_TEACHER_CANDIDATE_PATH = _REPO_ROOT / "outputs" / "x_api_phase2" / "pre_teacher_candidate.json"
_WATCHED_ACCOUNTS_LOG_PATH = _REPO_ROOT / "ops" / "data" / "watched_accounts.jsonl"
_WATCHED_ACCOUNT_STATE_PATH = _REPO_ROOT / "ops" / "data" / "watched_account_state.json"
_USERS_BATCH_URL = "https://api.x.com/2/users"
_API_TIMEOUT_SECONDS = 30


def _load_bearer_token() -> str | None:
    """.env（プロジェクトルート）からX_BEARER_TOKENを読み込む。無ければos.environへ
    フォールバック（x_api_deepdive_collect.py等、既存スクリプトと同じパターン）。
    """
    try:
        from dotenv import load_dotenv

        load_dotenv(_REPO_ROOT / ".env")
    except ImportError:
        pass
    token = os.environ.get("X_BEARER_TOKEN", "").strip()
    return token or None


def _fetch_users_batch(token: str, author_ids: list[str]) -> dict[str, dict]:
    """GET /2/users?ids=...でuser情報をまとめて取得する（最大100件/リクエスト、
    企業アカウント判定に使うためverified_type/nameを要求する）。

    企業アカウント判定はteacher判定・登録フロー全体を止めてはならないbest-effortの
    追加チェックのため、失敗時（ネットワーク障害・レート制限等）は例外を送出せず
    空dictを返す——呼び出し側はこの場合、全候補を通常どおり登録する
    （判定不能時は通常登録を継続する、というdetect_company_account_signal()と
    同じ「疑わしきは人間確認へ」方針の裏返し: 判定材料そのものが無ければブロックしない）。
    """
    if not author_ids:
        return {}
    headers = {"Authorization": f"Bearer {token}"}
    params = {"ids": ",".join(author_ids), "user.fields": "verified_type,name"}
    try:
        response = requests.get(_USERS_BATCH_URL, headers=headers, params=params, timeout=_API_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001 - best-effort、失敗しても登録フローは止めない
        print(
            f"警告: 企業アカウント判定用のユーザー情報取得に失敗しました（{exc}）。"
            "判定をスキップし、通常の登録フローを継続します。",
            file=sys.stderr,
        )
        return {}
    return {u["id"]: u for u in data.get("data", []) if u.get("id")}


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

    # 企業アカウント判定（2026-09-04追加）: storeに未登録（＝このバッチで初めて
    # 監視対象になり得る）author_idのみ対象とする。既存active/graduated/excluded/
    # pending_reviewは対象外——既に人間の意思決定を経由済みか、この機能導入前から
    # 実運用されている個人アカウントのため、毎回チェックし直す必要はない。
    candidate_author_ids = [aid for aid in seen_author_ids_in_batch if aid not in store]
    user_info_by_author_id: dict[str, dict] = {}
    token = _load_bearer_token()
    if token and candidate_author_ids:
        user_info_by_author_id = _fetch_users_batch(token, candidate_author_ids)
    elif candidate_author_ids:
        print(
            "警告: X_BEARER_TOKENが見つからないため、企業アカウント判定をスキップします。"
            "通常の登録フローを継続します。",
            file=sys.stderr,
        )

    log_candidates_by_author_id = {c["author_id"]: c for c in log_candidates}

    reactivated: list[str] = []
    newly_registered: list[str] = []
    skipped_special_status: list[tuple[str, str]] = []
    pending_company_review: list[str] = []

    for author_id in seen_author_ids_in_batch:
        was_known = author_id in store
        if was_known and store[author_id].watch_status in ("excluded", "pending_review"):
            skipped_special_status.append((author_id, store[author_id].watch_status))
            continue

        if not was_known:
            signal = detect_company_account_signal(user_info_by_author_id.get(author_id))
            if signal["is_flagged"]:
                record = log_candidates_by_author_id.get(author_id, {})
                reason = "; ".join(signal["reasons"])
                create_pending_review_watched_account(store, author_id, reason=reason, detected_at=observed_at)
                pending_company_review.append(author_id)
                print(
                    f"[要人間確認] author_id={author_id}: 企業アカウントの可能性のため"
                    f"active登録を保留しました（理由: {reason}、"
                    f"post_id={record.get('first_seen_as_teacher_post_id')}）"
                )
                continue

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
    print(f"企業アカウント要人間確認（active登録を保留）: {len(pending_company_review)}件 {pending_company_review}")
    print(f"除外/保留中のためスキップ: {len(skipped_special_status)}件 {skipped_special_status}")
    print(f"保存先: {_WATCHED_ACCOUNTS_LOG_PATH} / {_WATCHED_ACCOUNT_STATE_PATH}")


if __name__ == "__main__":
    main()
