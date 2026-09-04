"""topic_group_source_account_review.py（proposed topic_group一覧への企業アカウント
警告表示）の検証スクリプト。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイルに合わせ、
`python scripts/test_topic_group_source_account_review.py`で直接実行できる
plain assertベースの検証スクリプトとする。

外部API呼び出しは一切行わない。ローカルの一時ファイルのみ使用する。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from topic_group_source_account_review import get_account_review_warning_for_topic_group
from watched_account_state import (
    WatchedAccountState,
    create_pending_review_watched_account,
    exclude_watched_account,
    register_or_reactivate_watched_account,
    save_watched_account_state_store,
)

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


def _write_cumulative_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def test_pending_review_author_produces_warning() -> None:
    print("\n=== 検証1: pending_review状態の投稿者に由来するtopic_groupに警告が出ること ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        cumulative_path = Path(tmpdir) / "cumulative.jsonl"
        state_path = Path(tmpdir) / "watched_account_state.json"
        _write_cumulative_jsonl(cumulative_path, [{"id": "post-1", "author_id": "author-company"}])

        store: dict[str, WatchedAccountState] = {}
        create_pending_review_watched_account(
            store, "author-company", reason="verified_type=business", detected_at="2026-09-04T00:00:00Z"
        )
        save_watched_account_state_store(store, state_path)

        warning = get_account_review_warning_for_topic_group("post-1", cumulative_path, state_path)
        _check("warning_present", warning is not None, str(warning))
        _check("warning_mentions_pending_review", warning is not None and "要人間確認" in warning)


def test_excluded_author_produces_warning() -> None:
    print("\n=== 検証2: excluded状態の投稿者に由来するtopic_groupに警告が出ること ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        cumulative_path = Path(tmpdir) / "cumulative.jsonl"
        state_path = Path(tmpdir) / "watched_account_state.json"
        _write_cumulative_jsonl(cumulative_path, [{"id": "post-1", "author_id": "author-company"}])

        store: dict[str, WatchedAccountState] = {}
        state = register_or_reactivate_watched_account(store, "author-company", observed_at="2026-09-01T00:00:00Z")
        exclude_watched_account(state, reason="企業公式アカウントのため")
        save_watched_account_state_store(store, state_path)

        warning = get_account_review_warning_for_topic_group("post-1", cumulative_path, state_path)
        _check("warning_present", warning is not None, str(warning))
        _check("warning_mentions_excluded", warning is not None and "除外済み" in warning)


def test_active_author_produces_no_warning() -> None:
    print("\n=== 検証3: active状態の投稿者（既存個人アカウント相当）には警告が出ないこと（回帰確認） ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        cumulative_path = Path(tmpdir) / "cumulative.jsonl"
        state_path = Path(tmpdir) / "watched_account_state.json"
        _write_cumulative_jsonl(cumulative_path, [{"id": "post-1", "author_id": "author-individual"}])

        store: dict[str, WatchedAccountState] = {}
        register_or_reactivate_watched_account(store, "author-individual", observed_at="2026-09-01T00:00:00Z")
        save_watched_account_state_store(store, state_path)

        warning = get_account_review_warning_for_topic_group("post-1", cumulative_path, state_path)
        _check("no_warning", warning is None, str(warning))


def test_unknown_post_id_produces_no_warning() -> None:
    print("\n=== 検証4: 累積ストアに存在しないpost_idの場合はNoneを返すこと（安全側フォールバック） ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        cumulative_path = Path(tmpdir) / "cumulative.jsonl"
        state_path = Path(tmpdir) / "watched_account_state.json"
        _write_cumulative_jsonl(cumulative_path, [{"id": "post-1", "author_id": "author-individual"}])
        save_watched_account_state_store({}, state_path)

        warning = get_account_review_warning_for_topic_group("post-does-not-exist", cumulative_path, state_path)
        _check("no_warning", warning is None, str(warning))


def test_none_source_diversity_tag_produces_no_warning() -> None:
    print("\n=== 検証5: source_diversity_tagがNoneの場合はNoneを返すこと ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        cumulative_path = Path(tmpdir) / "cumulative.jsonl"
        state_path = Path(tmpdir) / "watched_account_state.json"
        warning = get_account_review_warning_for_topic_group(None, cumulative_path, state_path)
        _check("no_warning", warning is None, str(warning))


if __name__ == "__main__":
    test_pending_review_author_produces_warning()
    test_excluded_author_produces_warning()
    test_active_author_produces_no_warning()
    test_unknown_post_id_produces_no_warning()
    test_none_source_diversity_tag_produces_no_warning()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
