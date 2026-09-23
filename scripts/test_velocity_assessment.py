"""velocity判定・outcome_confirmed（post_outcome判定の早期指標/最終確定フラグ分離、
2026-09-23追加、GOV-20260923-VELOCITY-ASSESSMENT-01）の検証スクリプト。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイルに合わせ、
`python scripts/test_velocity_assessment.py`で直接実行できるplain assertベースの
検証スクリプトとする。

外部API呼び出しは一切行わない。Gate A/thresholds/shipping decision・
classify_post_outcome()本体・has_ever_won/latest_post_outcomeの算出方法・
cooldown可変ロジック・retry_budget消費ロジックには一切触れない
（純粋な追加フィールドの検証のみ）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from topic_group_state import (
    compute_velocity_assessment,
    update_velocity_and_confirmation,
    get_or_create_topic_group,
    VELOCITY_ASSESSMENT_MIN_HOURS,
    VELOCITY_ASSESSMENT_MAX_HOURS,
    VELOCITY_HIGH_THRESHOLD,
    VELOCITY_NORMAL_THRESHOLD,
    OUTCOME_CONFIRMATION_MIN_HOURS,
)

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


def test_1_compute_velocity_assessment_bands() -> None:
    print("\n=== 検証1: compute_velocity_assessment()の帯判定（high/normal/low） ===")
    high = compute_velocity_assessment(impression_count=170, elapsed_hours=36.9)
    _check("high_velocity_detected", high is not None and high["velocity_assessment"] == "high_velocity", str(high))
    _check("high_velocity_rate", high is not None and abs(high["velocity_impression_rate"] - 170 / 36.9) < 1e-6)

    normal = compute_velocity_assessment(impression_count=62, elapsed_hours=71.9)
    _check("normal_velocity_detected", normal is not None and normal["velocity_assessment"] == "normal_velocity", str(normal))

    low = compute_velocity_assessment(impression_count=17, elapsed_hours=27.1)
    _check("low_velocity_detected", low is not None and low["velocity_assessment"] == "low_velocity", str(low))

    # 境界値（閾値ちょうど）
    boundary_high = compute_velocity_assessment(impression_count=int(VELOCITY_HIGH_THRESHOLD * 48), elapsed_hours=48)
    _check("boundary_high_is_high_velocity", boundary_high is not None and boundary_high["velocity_assessment"] == "high_velocity", str(boundary_high))

    # 48h時点でちょうど0.7/hとなる34imp（34/48=0.7083...>=0.7）を使う
    # （0.7*48=33.6をint()で切り捨てると33imp/48h=0.6875<0.7となり境界を跨いでしまうため、
    # 切り捨てず実際に閾値以上になる値を明示的に選ぶ）
    boundary_normal = compute_velocity_assessment(impression_count=34, elapsed_hours=48)
    _check("boundary_normal_is_normal_velocity", boundary_normal is not None and boundary_normal["velocity_assessment"] == "normal_velocity", str(boundary_normal))


def test_2_window_boundaries() -> None:
    print("\n=== 検証2: velocity判定窓（24-72h）の境界確認 ===")
    below_window = compute_velocity_assessment(impression_count=100, elapsed_hours=VELOCITY_ASSESSMENT_MIN_HOURS - 0.1)
    _check("below_window_returns_none", below_window is None, str(below_window))

    above_window = compute_velocity_assessment(impression_count=100, elapsed_hours=VELOCITY_ASSESSMENT_MAX_HOURS + 0.1)
    _check("above_window_returns_none", above_window is None, str(above_window))

    exactly_min = compute_velocity_assessment(impression_count=100, elapsed_hours=VELOCITY_ASSESSMENT_MIN_HOURS)
    _check("exactly_min_hours_included", exactly_min is not None, str(exactly_min))

    exactly_max = compute_velocity_assessment(impression_count=100, elapsed_hours=VELOCITY_ASSESSMENT_MAX_HOURS)
    _check("exactly_max_hours_included", exactly_max is not None, str(exactly_max))


def test_3_update_velocity_and_confirmation_within_window() -> None:
    print("\n=== 検証3: update_velocity_and_confirmation()、窓内の計測でフィールドが更新されること ===")
    store: dict = {}
    state = get_or_create_topic_group(store, "tg-velocity-test-1", "sig-velocity-test-1")
    _check("initial_velocity_assessment_is_unknown", state.velocity_assessment == "unknown")
    _check("initial_velocity_rate_is_none", state.velocity_impression_rate is None)
    _check("initial_outcome_confirmed_is_false", state.outcome_confirmed is False)

    update_velocity_and_confirmation(state, impression_count=164, elapsed_hours=61.9)
    _check("velocity_assessment_updated", state.velocity_assessment == "high_velocity", state.velocity_assessment)
    _check("velocity_rate_updated", state.velocity_impression_rate is not None and abs(state.velocity_impression_rate - 164 / 61.9) < 1e-6)
    _check("velocity_assessed_at_hours_recorded", state.velocity_assessed_at_hours == 61.9)
    _check("outcome_confirmed_still_false_below_336h", state.outcome_confirmed is False)


def test_4_update_velocity_and_confirmation_outside_window_no_overwrite() -> None:
    print("\n=== 検証4: 窓外の計測ではvelocity関連フィールドが上書きされないこと ===")
    store: dict = {}
    state = get_or_create_topic_group(store, "tg-velocity-test-2", "sig-velocity-test-2")
    update_velocity_and_confirmation(state, impression_count=170, elapsed_hours=36.9)
    _check("first_update_sets_high_velocity", state.velocity_assessment == "high_velocity")

    # 窓外（376.7h）の計測を後から反映しても、velocity関連フィールドは変わらないはず
    update_velocity_and_confirmation(state, impression_count=281, elapsed_hours=376.7)
    _check("velocity_assessment_unchanged_after_out_of_window_update", state.velocity_assessment == "high_velocity", state.velocity_assessment)
    _check("velocity_assessed_at_hours_unchanged", state.velocity_assessed_at_hours == 36.9, state.velocity_assessed_at_hours)


def test_5_outcome_confirmed_336h_threshold() -> None:
    print("\n=== 検証5: outcome_confirmedが336h(14日)閾値で正しく確定すること ===")
    store: dict = {}
    state = get_or_create_topic_group(store, "tg-velocity-test-3", "sig-velocity-test-3")

    update_velocity_and_confirmation(state, impression_count=100, elapsed_hours=OUTCOME_CONFIRMATION_MIN_HOURS - 1)
    _check("not_confirmed_below_threshold", state.outcome_confirmed is False)

    update_velocity_and_confirmation(state, impression_count=100, elapsed_hours=OUTCOME_CONFIRMATION_MIN_HOURS)
    _check("confirmed_at_exact_threshold", state.outcome_confirmed is True)


def test_6_outcome_confirmed_is_monotonic() -> None:
    print("\n=== 検証6: outcome_confirmedは一度Trueになったら後退しないこと ===")
    store: dict = {}
    state = get_or_create_topic_group(store, "tg-velocity-test-4", "sig-velocity-test-4")
    update_velocity_and_confirmation(state, impression_count=100, elapsed_hours=400)
    _check("confirmed_after_long_elapsed", state.outcome_confirmed is True)

    # その後、短いelapsed_hoursで再度呼ばれてもFalseへ戻らないこと
    update_velocity_and_confirmation(state, impression_count=50, elapsed_hours=30)
    _check("stays_confirmed_after_later_short_elapsed_call", state.outcome_confirmed is True)


def test_7_elapsed_hours_none_no_change() -> None:
    print("\n=== 検証7: elapsed_hours=Noneの場合、velocity/outcome_confirmedいずれも変更されないこと（既存呼び出し元との後方互換） ===")
    store: dict = {}
    state = get_or_create_topic_group(store, "tg-velocity-test-5", "sig-velocity-test-5")
    update_velocity_and_confirmation(state, impression_count=100, elapsed_hours=None)
    _check("velocity_assessment_stays_unknown", state.velocity_assessment == "unknown")
    _check("velocity_rate_stays_none", state.velocity_impression_rate is None)
    _check("outcome_confirmed_stays_false", state.outcome_confirmed is False)


def test_8_existing_fields_untouched() -> None:
    print("\n=== 検証8: 既存フィールド（has_ever_won/latest_post_outcome/topic_performance_band）が無変更のままであること ===")
    from topic_group_state import record_post_outcome, update_performance_band

    store: dict = {}
    state = get_or_create_topic_group(store, "tg-velocity-test-6", "sig-velocity-test-6")
    update_performance_band(state, impression_count=281)
    record_post_outcome(state, "win")
    before_band = state.topic_performance_band
    before_outcome = state.latest_post_outcome
    before_ever_won = state.has_ever_won

    update_velocity_and_confirmation(state, impression_count=281, elapsed_hours=36.9)

    _check("performance_band_unchanged", state.topic_performance_band == before_band, state.topic_performance_band)
    _check("latest_post_outcome_unchanged", state.latest_post_outcome == before_outcome, state.latest_post_outcome)
    _check("has_ever_won_unchanged", state.has_ever_won == before_ever_won, state.has_ever_won)


if __name__ == "__main__":
    test_1_compute_velocity_assessment_bands()
    test_2_window_boundaries()
    test_3_update_velocity_and_confirmation_within_window()
    test_4_update_velocity_and_confirmation_outside_window_no_overwrite()
    test_5_outcome_confirmed_336h_threshold()
    test_6_outcome_confirmed_is_monotonic()
    test_7_elapsed_hours_none_no_change()
    test_8_existing_fields_untouched()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
