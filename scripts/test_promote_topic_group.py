"""promote_topic_group.pyの検証スクリプト（昇格・却下・エラーハンドリング）。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイルに合わせ、
`python scripts/test_promote_topic_group.py`で直接実行できるplain assertベースの
検証スクリプトとする。本番ストア（ops/reports/topic_group_state_2026-08-31.json）は
一切書き換えない——全て検証専用の一時storeで完結させる。

Gate A/thresholds/shipping decision、既存のteacher判定・抽出ロジック本体、
promote_proposed_topic_group()本体には一切触れない。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from promote_topic_group import apply_promote_or_reject, resolve_proposed_target
from topic_group_state import (
    TopicGroupState,
    TopicGroupStateError,
    get_or_create_topic_group,
    list_proposed_topic_groups,
    passes_mainline_candidate_filter,
)

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


def test_resolve_proposed_target_success() -> None:
    print("\n=== 検証1: resolve_proposed_target()が'proposed'状態のtopic_groupを正しく返すこと ===")
    store: dict[str, TopicGroupState] = {}
    get_or_create_topic_group(store, "tg-resolve-ok", "sig-resolve-ok", initial_status="proposed")
    state = resolve_proposed_target(store, "tg-resolve-ok")
    _check("returns_correct_state", state.topic_group_id == "tg-resolve-ok")


def test_resolve_proposed_target_missing_id() -> None:
    print("\n=== 検証2: 存在しないtopic_group_idはTopicGroupStateErrorになること ===")
    store: dict[str, TopicGroupState] = {}
    raised = False
    try:
        resolve_proposed_target(store, "tg-does-not-exist")
    except TopicGroupStateError as exc:
        raised = True
        _check("error_message_mentions_id", "tg-does-not-exist" in str(exc), str(exc))
    _check("raises_on_missing_id", raised)


def test_resolve_proposed_target_non_proposed_status() -> None:
    print("\n=== 検証3: 'proposed'以外の状態はTopicGroupStateErrorになること ===")
    store: dict[str, TopicGroupState] = {}
    get_or_create_topic_group(store, "tg-already-active", "sig-already-active")  # デフォルトactive
    raised = False
    try:
        resolve_proposed_target(store, "tg-already-active")
    except TopicGroupStateError:
        raised = True
    _check("raises_on_non_proposed_status", raised)


def test_apply_promote() -> None:
    print("\n=== 検証4: 昇格の正常系（apply_promote_or_reject, reject=False） ===")
    store: dict[str, TopicGroupState] = {}
    get_or_create_topic_group(store, "tg-promote", "sig-promote", initial_status="proposed")
    state = apply_promote_or_reject(store, "tg-promote", reject=False)
    _check("status_is_active", state.topic_status == "active", state.topic_status)
    filter_result = passes_mainline_candidate_filter(state, posted_theme_blocked=False, exploration_quota_remaining=True)
    _check("passes_mainline_filter_after_promote", filter_result["passes"] is True)


def test_apply_reject() -> None:
    print("\n=== 検証5: 却下の正常系（apply_promote_or_reject, reject=True） ===")
    store: dict[str, TopicGroupState] = {}
    get_or_create_topic_group(store, "tg-reject", "sig-reject", initial_status="proposed")
    state = apply_promote_or_reject(store, "tg-reject", reject=True)
    _check("status_is_retired", state.topic_status == "retired", state.topic_status)
    _check("retired_from_mainline_flag_set", state.topic_retired_from_mainline is True)
    filter_result = passes_mainline_candidate_filter(state, posted_theme_blocked=False, exploration_quota_remaining=True)
    _check("fails_mainline_filter_after_reject", filter_result["passes"] is False, str(filter_result))


def test_end_to_end_list_promote_relist() -> None:
    print("\n=== 検証6: 一覧表示->昇格->再度一覧表示で対象がproposedから消えactiveになっていること ===")
    store: dict[str, TopicGroupState] = {}
    get_or_create_topic_group(store, "tg-e2e-a", "sig-e2e-a", initial_status="proposed")
    get_or_create_topic_group(store, "tg-e2e-b", "sig-e2e-b", initial_status="proposed")

    before = list_proposed_topic_groups(store)
    _check("both_proposed_before", {s.topic_group_id for s in before} == {"tg-e2e-a", "tg-e2e-b"}, str([s.topic_group_id for s in before]))

    resolve_proposed_target(store, "tg-e2e-a")  # 昇格前の存在確認ステップ相当
    apply_promote_or_reject(store, "tg-e2e-a", reject=False)

    after = list_proposed_topic_groups(store)
    _check("only_b_remains_proposed", [s.topic_group_id for s in after] == ["tg-e2e-b"], str([s.topic_group_id for s in after]))
    _check("a_is_now_active", store["tg-e2e-a"].topic_status == "active", store["tg-e2e-a"].topic_status)


if __name__ == "__main__":
    test_resolve_proposed_target_success()
    test_resolve_proposed_target_missing_id()
    test_resolve_proposed_target_non_proposed_status()
    test_apply_promote()
    test_apply_reject()
    test_end_to_end_list_promote_relist()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
