"""watched_account_store.py / watched_account_state.py の検証スクリプト
（登録・卒業・復帰の状態遷移）。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイル
（scripts/test_topic_group_lifecycle.py等）に合わせ、
`python scripts/test_watched_account_lifecycle.py`で直接実行できるplain assert
ベースの検証スクリプトとする。

外部AI呼び出し・外部API呼び出しは一切行わない。Gate A/thresholds/shipping decision、
_apply_engagement_gate()、topic_groupのライフサイクル管理ロジックには一切触れない。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from watched_account_state import (
    GRADUATION_THRESHOLD_CONSECUTIVE_UNPRODUCTIVE_RUNS,
    WatchedAccountState,
    active_author_ids,
    load_watched_account_state_store,
    record_deepdive_run_result,
    register_or_reactivate_watched_account,
    save_watched_account_state_store,
)
from watched_account_store import append_new_watched_accounts, load_existing_watched_author_ids

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


def test_new_registration_creates_active_state() -> None:
    print("\n=== 検証1: 未登録author_idの新規登録がactiveで作成されること ===")
    store: dict[str, WatchedAccountState] = {}
    state = register_or_reactivate_watched_account(store, "author-1", observed_at="2026-09-02T00:00:00Z")
    _check("watch_status_active", state.watch_status == "active", state.watch_status)
    _check("teacher_count_is_1", state.teacher_count == 1, str(state.teacher_count))
    _check("first_registered_at_set", state.first_registered_at == "2026-09-02T00:00:00Z")
    _check("stored_in_dict", "author-1" in store)


def test_repeat_observation_increments_teacher_count_stays_active() -> None:
    print("\n=== 検証2: 既存activeアカウントの再観測でteacher_countのみ加算されること ===")
    store: dict[str, WatchedAccountState] = {}
    register_or_reactivate_watched_account(store, "author-1", observed_at="2026-09-01T00:00:00Z")
    state = register_or_reactivate_watched_account(store, "author-1", observed_at="2026-09-02T00:00:00Z")
    _check("teacher_count_is_2", state.teacher_count == 2, str(state.teacher_count))
    _check("watch_status_still_active", state.watch_status == "active")
    _check("last_teacher_at_updated", state.last_teacher_at == "2026-09-02T00:00:00Z")


def test_graduation_after_consecutive_unproductive_runs() -> None:
    print("\n=== 検証3: 連続不発でgraduatedへ遷移すること ===")
    store: dict[str, WatchedAccountState] = {}
    state = register_or_reactivate_watched_account(store, "author-1", observed_at="2026-09-01T00:00:00Z")

    for i in range(GRADUATION_THRESHOLD_CONSECUTIVE_UNPRODUCTIVE_RUNS - 1):
        record_deepdive_run_result(state, found_new_pre_teacher_candidate=False, since_id=None, checked_at=f"run-{i}")
    _check(
        "still_active_before_threshold",
        state.watch_status == "active",
        f"consecutive={state.consecutive_unproductive_deepdive_runs}",
    )

    record_deepdive_run_result(state, found_new_pre_teacher_candidate=False, since_id=None, checked_at="run-final")
    _check(
        "graduated_at_threshold",
        state.watch_status == "graduated",
        f"consecutive={state.consecutive_unproductive_deepdive_runs}",
    )
    _check(
        "consecutive_count_matches_threshold",
        state.consecutive_unproductive_deepdive_runs == GRADUATION_THRESHOLD_CONSECUTIVE_UNPRODUCTIVE_RUNS,
    )


def test_productive_run_resets_unproductive_counter() -> None:
    print("\n=== 検証4: 深掘りでpre_teacher_candidateが見つかると不発カウンタがリセットされること ===")
    store: dict[str, WatchedAccountState] = {}
    state = register_or_reactivate_watched_account(store, "author-1", observed_at="2026-09-01T00:00:00Z")

    for i in range(3):
        record_deepdive_run_result(state, found_new_pre_teacher_candidate=False, since_id=None, checked_at=f"run-{i}")
    _check("counter_at_3", state.consecutive_unproductive_deepdive_runs == 3)

    record_deepdive_run_result(state, found_new_pre_teacher_candidate=True, since_id="12345", checked_at="run-productive")
    _check("counter_reset_to_0", state.consecutive_unproductive_deepdive_runs == 0)
    _check("still_active", state.watch_status == "active")
    _check("since_id_updated", state.last_deepdive_since_id == "12345")


def test_since_id_preserved_when_no_new_posts() -> None:
    print("\n=== 検証5: 新規投稿0件のrunではsince_idが据え置かれること ===")
    store: dict[str, WatchedAccountState] = {}
    state = register_or_reactivate_watched_account(store, "author-1", observed_at="2026-09-01T00:00:00Z")
    record_deepdive_run_result(state, found_new_pre_teacher_candidate=True, since_id="100", checked_at="run-1")
    record_deepdive_run_result(state, found_new_pre_teacher_candidate=False, since_id=None, checked_at="run-2")
    _check("since_id_still_100", state.last_deepdive_since_id == "100", state.last_deepdive_since_id)


def test_reactivation_from_graduated_on_new_teacher_observation() -> None:
    print("\n=== 検証6: graduatedアカウントが日次キーワード収集で再度teacher観測された場合、自動復帰すること ===")
    store: dict[str, WatchedAccountState] = {}
    state = register_or_reactivate_watched_account(store, "author-1", observed_at="2026-09-01T00:00:00Z")
    for i in range(GRADUATION_THRESHOLD_CONSECUTIVE_UNPRODUCTIVE_RUNS):
        record_deepdive_run_result(state, found_new_pre_teacher_candidate=False, since_id=None, checked_at=f"run-{i}")
    _check("graduated_before_reactivation", state.watch_status == "graduated")

    reactivated_state = register_or_reactivate_watched_account(store, "author-1", observed_at="2026-10-01T00:00:00Z")
    _check("reactivated_to_active", reactivated_state.watch_status == "active", reactivated_state.watch_status)
    _check("unproductive_counter_reset_on_reactivation", reactivated_state.consecutive_unproductive_deepdive_runs == 0)
    _check("teacher_count_incremented_on_reactivation", reactivated_state.teacher_count == 2, str(reactivated_state.teacher_count))


def test_active_author_ids_filters_graduated() -> None:
    print("\n=== 検証7: active_author_ids()がgraduatedを除外すること ===")
    store: dict[str, WatchedAccountState] = {}
    register_or_reactivate_watched_account(store, "author-active", observed_at="2026-09-01T00:00:00Z")
    graduated_state = register_or_reactivate_watched_account(store, "author-graduated", observed_at="2026-09-01T00:00:00Z")
    for i in range(GRADUATION_THRESHOLD_CONSECUTIVE_UNPRODUCTIVE_RUNS):
        record_deepdive_run_result(graduated_state, found_new_pre_teacher_candidate=False, since_id=None, checked_at=f"run-{i}")

    targets = active_author_ids(store)
    _check("only_active_included", targets == ["author-active"], str(targets))


def test_state_store_save_load_roundtrip() -> None:
    print("\n=== 検証8: 状態ストアのsave/loadが往復して同一内容を復元できること ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "watched_account_state.json"
        store: dict[str, WatchedAccountState] = {}
        register_or_reactivate_watched_account(store, "author-1", observed_at="2026-09-01T00:00:00Z")
        save_watched_account_state_store(store, state_path)

        reloaded = load_watched_account_state_store(state_path)
        _check("reloaded_has_same_key", "author-1" in reloaded)
        _check(
            "reloaded_state_matches",
            reloaded["author-1"].teacher_count == 1 and reloaded["author-1"].watch_status == "active",
        )


def test_missing_state_store_returns_empty_dict() -> None:
    print("\n=== 検証9: 状態ストアが未作成の場合は空dictを返すこと（初回実行の安全側フォールバック） ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        missing_path = Path(tmpdir) / "does_not_exist.json"
        store = load_watched_account_state_store(missing_path)
        _check("empty_dict_when_missing", store == {}, str(store))


def test_watched_accounts_log_new_only_appended() -> None:
    print("\n=== 検証10: 登録イベントログへ新規author_idのみ追記されること ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "watched_accounts.jsonl"
        candidates = [
            {"author_id": "a1", "first_seen_as_teacher_post_id": "p1", "first_seen_as_teacher_query_source": ["q1"]},
            {"author_id": "a2", "first_seen_as_teacher_post_id": "p2", "first_seen_as_teacher_query_source": ["q2"]},
        ]
        result = append_new_watched_accounts(log_path, candidates, registered_at="2026-09-02T00:00:00Z")
        _check("appended_count_2", result["appended_count"] == 2, str(result))
        _check("total_after_2", result["total_after"] == 2, str(result))

        ids = load_existing_watched_author_ids(log_path)
        _check("both_ids_present", ids == {"a1", "a2"}, str(ids))


def test_watched_accounts_log_dedup_across_runs() -> None:
    print("\n=== 検証11: 既存author_idの重複が次回実行でスキップされること ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "watched_accounts.jsonl"
        append_new_watched_accounts(
            log_path,
            [{"author_id": "a1", "first_seen_as_teacher_post_id": "p1", "first_seen_as_teacher_query_source": ["q1"]}],
            registered_at="2026-09-01T00:00:00Z",
        )
        result2 = append_new_watched_accounts(
            log_path,
            [
                {"author_id": "a1", "first_seen_as_teacher_post_id": "p1b", "first_seen_as_teacher_query_source": ["q1b"]},
                {"author_id": "a2", "first_seen_as_teacher_post_id": "p2", "first_seen_as_teacher_query_source": ["q2"]},
            ],
            registered_at="2026-09-02T00:00:00Z",
        )
        _check("second_run_appended_only_new", result2["appended_count"] == 1, str(result2))
        _check("second_run_skipped_duplicate", result2["skipped_duplicate_count"] == 1, str(result2))


def test_watched_accounts_log_schema_excludes_text() -> None:
    print("\n=== 検証12: 登録イベントログのレコードにtext相当のフィールドが一切含まれないこと ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "watched_accounts.jsonl"
        append_new_watched_accounts(
            log_path,
            [{"author_id": "a1", "first_seen_as_teacher_post_id": "p1", "first_seen_as_teacher_query_source": ["q1"]}],
            registered_at="2026-09-01T00:00:00Z",
        )
        line = log_path.read_text(encoding="utf-8").strip()
        record = json.loads(line)
        expected_keys = {"author_id", "first_seen_as_teacher_post_id", "first_seen_as_teacher_query_source", "registered_at"}
        _check("record_keys_match_documented_schema", set(record.keys()) == expected_keys, str(record.keys()))
        _check("no_text_field", "text" not in record and "text_hash" not in record)


if __name__ == "__main__":
    test_new_registration_creates_active_state()
    test_repeat_observation_increments_teacher_count_stays_active()
    test_graduation_after_consecutive_unproductive_runs()
    test_productive_run_resets_unproductive_counter()
    test_since_id_preserved_when_no_new_posts()
    test_reactivation_from_graduated_on_new_teacher_observation()
    test_active_author_ids_filters_graduated()
    test_state_store_save_load_roundtrip()
    test_missing_state_store_returns_empty_dict()
    test_watched_accounts_log_new_only_appended()
    test_watched_accounts_log_dedup_across_runs()
    test_watched_accounts_log_schema_excludes_text()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
