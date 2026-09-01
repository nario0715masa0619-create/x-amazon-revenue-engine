"""post_outcome.classify_post_outcome()（勝ち投稿判定の正本）と、
topic_group_state / post_generation_pipelineへの配線（retry_budget消費・cooldown
可変・候補フィルタ除外）の検証スクリプト。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイル
（scripts/test_topic_group_lifecycle.py等）に合わせ、
`python scripts/test_post_outcome.py`で直接実行できるplain assertベースの
検証スクリプトとする。

外部AI呼び出し・外部API呼び出しは一切行わない。production scoring/Gate A/
thresholds/shipping decisionには一切触れない。TEACHER_FLOOR/SHIP_THRESHOLD/
STRONG_SHIP_THRESHOLDも変更しない。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from post_outcome import (
    classify_post_outcome,
    MIN_SAMPLE_IMPRESSIONS_THRESHOLD,
    WIN_IMPRESSION_THRESHOLD,
)
from topic_group_state import (
    TopicGroupState,
    get_or_create_topic_group,
    record_mainline_attempt,
    record_publication,
    record_post_outcome,
    passes_mainline_candidate_filter,
    NEVER_WON_RETRY_BUDGET_PENALTY_MULTIPLIER,
    NEVER_WON_MAX_RUN_COUNT_WITHOUT_WIN,
    WIN_COOLDOWN_DIVISOR,
    TOPIC_GROUP_COOLDOWN_DAYS,
)

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


def _pm(impression_count, like=0, reply=0, retweet=0, quote=0, bookmark=0) -> dict:
    return {
        "impression_count": impression_count,
        "like_count": like,
        "reply_count": reply,
        "retweet_count": retweet,
        "quote_count": quote,
        "bookmark_count": bookmark,
    }


# ==============================================================================
# 検証1: classify_post_outcome()の4パターン（win/neutral/loss/insufficient_data）+境界値
# ==============================================================================
def test_classify_post_outcome_four_patterns() -> None:
    print("\n=== 検証1: classify_post_outcome() 4パターン + 境界値 ===")

    r_none = classify_post_outcome(None)
    _check("insufficient_data_when_public_metrics_none", r_none.outcome == "insufficient_data", str(r_none))

    r_failed = classify_post_outcome(_pm(500, like=10), fetch_status="failed_non_blocking")
    _check("insufficient_data_when_fetch_failed", r_failed.outcome == "insufficient_data", str(r_failed))

    r_tiny = classify_post_outcome(_pm(10))
    _check(
        "insufficient_data_for_tiny_sample",
        r_tiny.outcome == "insufficient_data" and r_tiny.impression_count == 10,
        str(r_tiny),
    )

    r_boundary_below = classify_post_outcome(_pm(MIN_SAMPLE_IMPRESSIONS_THRESHOLD - 1, like=5))
    _check(
        "boundary_just_below_min_sample_is_insufficient",
        r_boundary_below.outcome == "insufficient_data",
        str(r_boundary_below),
    )

    r_boundary_at = classify_post_outcome(_pm(MIN_SAMPLE_IMPRESSIONS_THRESHOLD, like=1))
    _check(
        "boundary_at_min_sample_is_judged",
        r_boundary_at.outcome in ("neutral", "win", "loss"),
        str(r_boundary_at),
    )

    r_zero_engagement = classify_post_outcome(_pm(300))
    _check(
        "loss_when_zero_engagement_even_with_high_impressions",
        r_zero_engagement.outcome == "loss",
        str(r_zero_engagement),
    )

    r_neutral = classify_post_outcome(_pm(100, like=3))
    _check(
        "neutral_between_min_sample_and_win_threshold",
        r_neutral.outcome == "neutral",
        str(r_neutral),
    )

    r_win = classify_post_outcome(_pm(WIN_IMPRESSION_THRESHOLD, like=10))
    _check(
        "win_at_win_threshold_with_engagement",
        r_win.outcome == "win",
        str(r_win),
    )

    r_win_below_boundary = classify_post_outcome(_pm(WIN_IMPRESSION_THRESHOLD - 1, like=10))
    _check(
        "boundary_just_below_win_threshold_is_neutral",
        r_win_below_boundary.outcome == "neutral",
        str(r_win_below_boundary),
    )

    r_affiliate = classify_post_outcome(_pm(10), affiliate_metrics={"conversions": 1})
    _check(
        "affiliate_override_wins_even_with_tiny_impressions",
        r_affiliate.outcome == "win" and r_affiliate.used_affiliate_override is True,
        str(r_affiliate),
    )

    r_affiliate_zero = classify_post_outcome(_pm(300), affiliate_metrics={"conversions": 0})
    _check(
        "affiliate_zero_does_not_override",
        r_affiliate_zero.outcome == "loss" and r_affiliate_zero.used_affiliate_override is False,
        str(r_affiliate_zero),
    )


# ==============================================================================
# 検証2: 実データ（現状唯一の実測ケース、impression=10, engagement全て0）を流す
# ==============================================================================
def test_real_post_analytics_case() -> None:
    print("\n=== 検証2: 実データ（mainline-run-2026-08-29-001の実測post_analytics）===")
    repo_root = Path(__file__).resolve().parent.parent
    path = repo_root / "ops" / "reports" / "post_analytics_2026-08-31_mainline-run-2026-08-29-001.json"
    if not path.exists():
        _check("real_post_analytics_file_exists", False, f"{path} が見つからない")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    result = classify_post_outcome(data.get("public_metrics"), fetch_status=data.get("fetch_status"))
    print(f"    real data: impression_count={data['public_metrics']['impression_count']}, "
          f"engagement_total={result.engagement_total}, outcome={result.outcome}")
    print(f"    reason: {result.reason}")
    _check(
        "real_data_classified_as_insufficient_data",
        result.outcome == "insufficient_data",
        (
            f"impression_count={data['public_metrics']['impression_count']} は"
            f"MIN_SAMPLE_IMPRESSIONS_THRESHOLD({MIN_SAMPLE_IMPRESSIONS_THRESHOLD})未満のため"
        ),
    )


# ==============================================================================
# 検証3: retry_budget消費・cooldown可変・候補フィルタ除外の統合テスト
# ==============================================================================
def test_never_won_retry_budget_penalty() -> None:
    print("\n=== 検証3a: win実績なしのretry_budget消費ペナルティ ===")
    store: dict[str, TopicGroupState] = {}
    state = get_or_create_topic_group(store, "tg-penalty-test", "sig-penalty-test")
    initial_budget = state.topic_retry_budget
    record_mainline_attempt(state, succeeded=False)
    _check(
        "never_won_consumes_penalty_multiplier",
        state.topic_retry_budget == max(0, initial_budget - NEVER_WON_RETRY_BUDGET_PENALTY_MULTIPLIER),
        f"budget={state.topic_retry_budget}",
    )

    store2: dict[str, TopicGroupState] = {}
    state2 = get_or_create_topic_group(store2, "tg-penalty-test-won", "sig-penalty-test-won")
    initial_budget2 = state2.topic_retry_budget
    record_post_outcome(state2, "win")
    record_mainline_attempt(state2, succeeded=False)
    _check(
        "has_ever_won_consumes_only_one",
        state2.topic_retry_budget == max(0, initial_budget2 - 1),
        f"budget={state2.topic_retry_budget}",
    )


def test_cooldown_varies_by_outcome() -> None:
    print("\n=== 検証3b: cooldown期間のwin/loss可変ロジック ===")
    store: dict[str, TopicGroupState] = {}
    state_win = get_or_create_topic_group(store, "tg-cooldown-win", "sig-cooldown-win")
    record_publication(state_win, published_at="2026-08-01", latest_outcome="win")
    expected_win_days = max(1, TOPIC_GROUP_COOLDOWN_DAYS // WIN_COOLDOWN_DIVISOR)
    _check(
        "win_shortens_cooldown",
        state_win.topic_cooldown_until is not None,
        f"cooldown_until={state_win.topic_cooldown_until} (expected +{expected_win_days}d from 2026-08-01)",
    )

    store2: dict[str, TopicGroupState] = {}
    state_loss = get_or_create_topic_group(store2, "tg-cooldown-loss", "sig-cooldown-loss")
    record_publication(state_loss, published_at="2026-08-01", latest_outcome="loss")
    _check("loss_retires_immediately", state_loss.topic_status == "retired", str(state_loss.topic_status))
    _check("loss_sets_no_cooldown_until", state_loss.topic_cooldown_until is None, str(state_loss.topic_cooldown_until))

    store3: dict[str, TopicGroupState] = {}
    state_default = get_or_create_topic_group(store3, "tg-cooldown-default", "sig-cooldown-default")
    record_publication(state_default, published_at="2026-08-01")
    _check(
        "default_none_outcome_keeps_existing_cooldown_behavior",
        state_default.topic_status == "published" and state_default.topic_cooldown_until == "2026-08-22",
        str((state_default.topic_status, state_default.topic_cooldown_until)),
    )


def test_never_won_candidate_filter_exclusion() -> None:
    print("\n=== 検証3c: win実績なしtopic_groupのmainline_run_count超過による候補除外 ===")
    store: dict[str, TopicGroupState] = {}
    state = get_or_create_topic_group(store, "tg-never-won-exhausted", "sig-never-won-exhausted")
    state.mainline_run_count = NEVER_WON_MAX_RUN_COUNT_WITHOUT_WIN + 1
    r = passes_mainline_candidate_filter(state, posted_theme_blocked=False, exploration_quota_remaining=True)
    _check(
        "excluded_when_never_won_and_run_count_exceeds_limit",
        r["passes"] is False and r["never_won_exhausted_ok"] is False,
        str(r),
    )

    store2: dict[str, TopicGroupState] = {}
    state2 = get_or_create_topic_group(store2, "tg-never-won-not-yet", "sig-never-won-not-yet")
    state2.mainline_run_count = NEVER_WON_MAX_RUN_COUNT_WITHOUT_WIN
    r2 = passes_mainline_candidate_filter(state2, posted_theme_blocked=False, exploration_quota_remaining=True)
    _check(
        "not_excluded_at_exact_boundary",
        r2["passes"] is True and r2["never_won_exhausted_ok"] is True,
        str(r2),
    )

    store3: dict[str, TopicGroupState] = {}
    state3 = get_or_create_topic_group(store3, "tg-won-not-exhausted", "sig-won-not-exhausted")
    record_post_outcome(state3, "win")
    state3.mainline_run_count = NEVER_WON_MAX_RUN_COUNT_WITHOUT_WIN + 10
    r3 = passes_mainline_candidate_filter(state3, posted_theme_blocked=False, exploration_quota_remaining=True)
    _check(
        "won_topic_group_not_excluded_regardless_of_run_count",
        r3["passes"] is True and r3["never_won_exhausted_ok"] is True,
        str(r3),
    )


def test_real_data_never_won_exclusion() -> None:
    print("\n=== 検証3d: 実データ（ATH-PRO5MK2テーマ系列）の候補除外再現 ===")
    from topic_group_state import load_topic_group_state_store

    repo_root = Path(__file__).resolve().parent.parent
    state_path = repo_root / "ops" / "reports" / "topic_group_state_2026-09-01.json"
    if not state_path.exists():
        _check("real_topic_group_state_file_exists", False, f"{state_path} が見つからない")
        return
    store = load_topic_group_state_store(state_path)
    published_id = "ath-pro5mk2-bone-conduction-neckband__call-quality-lightness-split-use"
    state = store.get(published_id)
    if state is None:
        _check("real_published_topic_group_found", False, f"{published_id} がstoreに無い")
        return
    r = passes_mainline_candidate_filter(state, posted_theme_blocked=False, exploration_quota_remaining=True)
    _check(
        "real_never_won_topic_group_excluded",
        r["passes"] is False and r["never_won_exhausted_ok"] is False,
        f"mainline_run_count={state.mainline_run_count}, has_ever_won={state.has_ever_won}, filter={r}",
    )


if __name__ == "__main__":
    test_classify_post_outcome_four_patterns()
    test_real_post_analytics_case()
    test_never_won_retry_budget_penalty()
    test_cooldown_varies_by_outcome()
    test_never_won_candidate_filter_exclusion()
    test_real_data_never_won_exclusion()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
