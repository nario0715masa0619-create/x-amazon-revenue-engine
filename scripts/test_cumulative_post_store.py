"""cumulative_post_store.pyの検証スクリプト（累積ストアへの追記ロジック）。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイル
（scripts/test_topic_group_lifecycle.py等）に合わせ、
`python scripts/test_cumulative_post_store.py`で直接実行できるplain assert
ベースの検証スクリプトとする。

外部AI呼び出し・外部API呼び出しは一切行わない。Gate A/thresholds/shipping decision、
_apply_engagement_gate()、topic_groupのライフサイクル管理ロジックには一切触れない。
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cumulative_post_store import (
    append_new_posts,
    load_all_cumulative_posts,
    load_existing_post_ids,
)

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


def _post(post_id: str, text: str = "サンプル本文", **overrides) -> dict:
    base = {
        "id": post_id,
        "text": text,
        "author_id": "author-1",
        "created_at": "2026-09-02T00:00:00.000Z",
        "lang": "ja",
        "like_count": 1,
        "reply_count": 0,
        "repost_count": 0,
        "quote_count": 0,
        "impression_count": 50,
        "bookmark_count": 0,
        "query_source": ["test query"],
        "retrieved_at": "2026-09-02T00:00:00.000Z",
        "text_hash": f"hash-{post_id}",
        "duplicate_count_by_text": 1,
    }
    base.update(overrides)
    return base


def test_new_posts_only_appended() -> None:
    print("\n=== 検証1: 新規post_idのみ追加されること ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "cumulative.jsonl"
        posts = [_post("p1"), _post("p2"), _post("p3")]
        result = append_new_posts(store_path, posts, collected_at="2026-09-02T00:00:00Z")
        _check("appended_count_matches_new_posts", result["appended_count"] == 3, str(result))
        _check("skipped_duplicate_count_zero_on_first_run", result["skipped_duplicate_count"] == 0, str(result))
        _check("total_before_zero_on_first_run", result["total_before"] == 0, str(result))
        _check("total_after_matches_appended", result["total_after"] == 3, str(result))

        ids = load_existing_post_ids(store_path)
        _check("all_three_ids_present", ids == {"p1", "p2", "p3"}, str(ids))


def test_duplicate_post_ids_skipped_across_runs() -> None:
    print("\n=== 検証2: 既存post_idの重複が次回実行でスキップされること ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "cumulative.jsonl"
        append_new_posts(store_path, [_post("p1"), _post("p2")], collected_at="2026-09-02T00:00:00Z")

        # 2回目の実行: p2は重複、p3は新規
        result2 = append_new_posts(store_path, [_post("p2"), _post("p3")], collected_at="2026-09-03T00:00:00Z")
        _check("second_run_appended_only_new", result2["appended_count"] == 1, str(result2))
        _check("second_run_skipped_duplicate", result2["skipped_duplicate_count"] == 1, str(result2))
        _check("second_run_total_before_matches_first_run", result2["total_before"] == 2, str(result2))
        _check("second_run_total_after", result2["total_after"] == 3, str(result2))

        ids = load_existing_post_ids(store_path)
        _check("cumulative_ids_after_two_runs", ids == {"p1", "p2", "p3"}, str(ids))


def test_duplicate_within_same_batch_skipped() -> None:
    print("\n=== 検証3: 同一バッチ内での重複post_idもスキップされること ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "cumulative.jsonl"
        # 同一post_idが1バッチ内に2回含まれるケース（実運用ではあまり無いが防御的に確認）
        result = append_new_posts(store_path, [_post("p1"), _post("p1")], collected_at="2026-09-02T00:00:00Z")
        _check("batch_internal_duplicate_appended_once", result["appended_count"] == 1, str(result))
        _check("batch_internal_duplicate_skipped_once", result["skipped_duplicate_count"] == 1, str(result))


def test_text_field_excluded_from_persisted_record() -> None:
    print("\n=== 検証4: 投稿本文(text)が累積ストアへ書き込まれないこと（プライバシー配慮） ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "cumulative.jsonl"
        append_new_posts(
            store_path,
            [_post("p1", text="これは絶対に保存されてはいけない投稿本文です")],
            collected_at="2026-09-02T00:00:00Z",
        )
        raw_content = store_path.read_text(encoding="utf-8")
        _check(
            "raw_text_not_present_in_file",
            "これは絶対に保存されてはいけない投稿本文です" not in raw_content,
            "本文が累積ストアのファイル内容に含まれていないこと",
        )
        records = load_all_cumulative_posts(store_path)
        _check("text_key_absent_from_record", "text" not in records[0], str(records[0].keys()))
        _check("text_hash_still_present", records[0].get("text_hash") == "hash-p1", str(records[0]))
        _check(
            "cumulative_first_seen_at_recorded",
            records[0].get("cumulative_first_seen_at") == "2026-09-02T00:00:00Z",
            str(records[0]),
        )


def test_empty_batch_does_not_create_empty_writes() -> None:
    print("\n=== 検証5: 追記対象が0件の場合はファイル書き込みを行わないこと ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "cumulative.jsonl"
        append_new_posts(store_path, [_post("p1")], collected_at="2026-09-02T00:00:00Z")
        mtime_before = store_path.stat().st_mtime_ns

        result = append_new_posts(store_path, [_post("p1")], collected_at="2026-09-03T00:00:00Z")
        _check("all_duplicate_batch_appends_zero", result["appended_count"] == 0, str(result))
        mtime_after = store_path.stat().st_mtime_ns
        _check("file_not_rewritten_when_nothing_new", mtime_before == mtime_after)


def test_missing_store_file_returns_empty_set() -> None:
    print("\n=== 検証6: 累積ストアが未作成の場合は空集合を返すこと（初回実行の安全側フォールバック） ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "does_not_exist.jsonl"
        ids = load_existing_post_ids(store_path)
        _check("empty_set_when_file_missing", ids == set(), str(ids))


if __name__ == "__main__":
    test_new_posts_only_appended()
    test_duplicate_post_ids_skipped_across_runs()
    test_duplicate_within_same_batch_skipped()
    test_text_field_excluded_from_persisted_record()
    test_empty_batch_does_not_create_empty_writes()
    test_missing_store_file_returns_empty_set()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
