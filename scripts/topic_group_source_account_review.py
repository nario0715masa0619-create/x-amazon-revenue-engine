"""proposed topic_groupの由来投稿者が、企業アカウント関連の要確認状態
（pending_review/excluded）にあるかどうかを調べ、人間向けの注意喚起メッセージを
組み立てるpure-ish helper（2026-09-04新設）。

list_proposed_topic_groups.py / promote_topic_group.py の両方から共有で使う
（重複実装を避けるため）。topic_groupの昇格・却下判定ロジック自体には一切触れない
（表示用の警告メッセージを作るだけ）。

外部AI・外部API呼び出しは一切行わない。ローカルファイル（累積ストア・
watched_account_state.json）の読み取りのみ。
"""

from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from watched_account_state import load_watched_account_state_store


def _lookup_author_id_by_post_id(post_id: str, cumulative_jsonl_path: Path) -> str | None:
    """累積ストア（ops/data/x_api_phase1_cumulative.jsonl）からpost_id→author_idを
    逆引きする。見つからない/ファイルが無い場合はNoneを返す（安全側フォールバック）。
    """
    if not cumulative_jsonl_path.exists():
        return None
    with cumulative_jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("id") == post_id:
                return record.get("author_id")
    return None


def get_account_review_warning_for_topic_group(
    source_diversity_tag: str | None,
    cumulative_jsonl_path: Path,
    watched_account_state_path: Path,
) -> str | None:
    """proposed topic_groupのsource_diversity_tag（由来投稿のpost_id）から投稿者
    author_idを逆引きし、watched_account_state.json上で"pending_review"
    （企業アカウントの可能性で要人間確認）または"excluded"（既に企業アカウントとして
    除外済み）の場合、表示用の警告メッセージを返す。該当なし・判定材料不足の場合は
    Noneを返す。
    """
    if not source_diversity_tag:
        return None
    author_id = _lookup_author_id_by_post_id(source_diversity_tag, cumulative_jsonl_path)
    if not author_id:
        return None
    store = load_watched_account_state_store(watched_account_state_path)
    state = store.get(author_id)
    if state is None:
        return None
    if state.watch_status == "pending_review":
        return (
            f"⚠️ 要人間確認: 投稿者(author_id={author_id})が企業アカウントの可能性で"
            f"保留中（理由: {state.pending_review_reason}）"
        )
    if state.watch_status == "excluded":
        return f"⚠️ 投稿者(author_id={author_id})は既に企業アカウント等として除外済み（理由: {state.excluded_reason}）"
    return None
