"""topic_group lifecycle（theme_signature正規化 / posted-theme exclusion統合 /
mainline候補生成フィルタ）の検証スクリプト。pytest等の外部テストランナーには依存せず、
このリポジトリの既存スタイル（scripts/x_api_smoke_test.py等）に合わせ、
`python scripts/test_topic_group_lifecycle.py`で直接実行できるplain assertベースの
検証スクリプトとする。

外部AI呼び出し・外部API呼び出しは一切行わない（すべてin-memoryのpure function検証）。
production scoring/Gate A/thresholds/shipping decisionには一切触れない。

設計文書: ops/reports/topic_group_lifecycle_design_2026-08-31.md
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from topic_dedupe import build_theme_profile, theme_component_overlap_ratio
from posted_theme_registry import (
    PostedThemeEntry,
    check_posted_theme_guard,
)
from topic_group_state import (
    TopicGroupState,
    get_or_create_topic_group,
    record_mainline_attempt,
    record_publication,
    update_performance_band,
    passes_mainline_candidate_filter,
    TOPIC_GROUP_INITIAL_RETRY_BUDGET,
)

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


# ==============================================================================
# 検証1: theme_signature正規化関数の単体テスト（表記ゆれ吸収、最低5パターン）
# ==============================================================================
def test_1_theme_signature_normalization() -> None:
    print("\n=== 検証1: theme_signature正規化（表記ゆれ吸収5パターン） ===")
    base_text = (
        "ジム用はネックバンド型骨伝導。軽さでこれを選んだ。"
        "自宅ではATH-PRO5MK2を使っていて、用途ごとに使い分けている"
    )
    base = build_theme_profile([base_text])

    variants = {
        "1_語順違い": (
            "自宅ではATH-PRO5MK2を使っていて、ジム用はネックバンド型骨伝導。"
            "軽さでこれを選んだ。用途ごとに使い分けている"
        ),
        "2_送り仮名違い": (
            "ジム用はネックバンド型骨伝導。軽さでこれを選んだ。"
            "自宅ではATH-PRO5MK2を使っていて、用途ごとに使い分け方を変えてる"
        ),
        "3_型番大文字小文字違い": (
            "ジム用はネックバンド型骨伝導。軽さでこれを選んだ。"
            "自宅ではath-pro5mk2を使っていて、用途ごとに使い分けている"
        ),
        "4_カタカナ英語表記違い": (
            "ジム用はneckband型bone conduction。軽さでこれを選んだ。"
            "自宅ではATH-PRO5MK2を使っていて、用途ごとに使い分けている"
        ),
        "5_記号有無違い": (
            "ジム用はネックバンド型骨伝導。軽さでこれを選んだ。"
            "自宅ではATHPRO5MK2を使っていて、用途ごとに使い分けている"
        ),
    }
    for name, text in variants.items():
        profile = build_theme_profile([text])
        overlap = theme_component_overlap_ratio(base["theme_components"], profile["theme_components"])
        _check(f"normalization_{name}", overlap >= 0.9, f"overlap_ratio={overlap:.2f}")


# ==============================================================================
# 検証2: posted-theme exclusionがsignatureベースで機能することの統合テスト
# ==============================================================================
def test_2_posted_theme_exclusion_integration() -> None:
    print("\n=== 検証2: posted-theme exclusion 統合テスト（ATH-PRO5MK2×ジム用骨伝導の再流入） ===")
    source_text = (
        "RT @inno_pastime: オススメのネックバンド型ワイヤレス軟骨伝導ヘッドホン🎧\n"
        "マイク付きなのでヘッドセットになるのかな？\n軽量なのでジム用としても重宝してます。\n\n"
        "自宅用のヘッドホンもATH-PRO5MK2だったりと、\n地味にオーテクには足を向けて寝られなかったり…"
    )
    posted_draft = (
        "ジム用はネックバンド型骨伝導。軽さでこれを選んだ。"
        "自宅ではATH-PRO5MK2を使っていて、用途ごとに使い分けている"
    )
    profile = build_theme_profile([posted_draft, source_text])
    registry = [
        PostedThemeEntry(
            run_id="mainline-run-2026-08-29-001",
            published_at="2026-08-29",
            post_url="https://x.com/ritsu_opt/status/2093850848397033676?s=20",
            published_draft_id="gadget-mainline0829-H",
            source_post_id="2093229163213996215",
            target_layer="gadget",
            theme_signature=profile["theme_signature"],
            theme_key_terms=profile["theme_components"],
            topic_group=profile["topic_group"],
        )
    ]

    # 別source_post_id・別言い回しの再流入候補（実際に2026-08-31運用で観測されたケースを再現）
    new_candidate_text = (
        "RT @inno_pastime: オススメのネックバンド型ワイヤレス軟骨伝導ヘッドホン🎧\n"
        "マイク付きなのでヘッドセットになるのかな？\n軽量なのでジム用としても重宝してます。\n\n"
        "自宅用のヘッドホンもATH-PRO5MK2だったりと、\n地味にオーテクには足を向けて寝られなかったり…"
    )
    result = check_posted_theme_guard(
        candidate_source_post_id="9999999999999999999",  # 既知entryとは別のsource_post_id
        candidate_texts=[new_candidate_text],
        target_layer="gadget",
        registry=registry,
    )
    _check(
        "posted_theme_reincursion_blocked",
        result["block_mainline"] is True and result["posted_theme_match_type"] in ("exact_source_match", "high_theme_similarity"),
        f"match_type={result['posted_theme_match_type']}, block_mainline={result['block_mainline']}",
    )
    _check("posted_theme_route_to_research", result["route_to_research"] is True)

    # 非投稿の新規テーマは通過することも合わせて確認（false positiveの過剰さを検出する）
    unrelated_result = check_posted_theme_guard(
        candidate_source_post_id="1111111111111111111",
        candidate_texts=["会議中はTeamsの接続トラブルが多いので、マイク性能重視でAirPods Proに落ち着いた"],
        target_layer="gadget",
        registry=registry,
    )
    _check("non_posted_theme_passes", unrelated_result["block_mainline"] is False)


# ==============================================================================
# 検証3: mainline候補生成フィルタが5条件（出典タスクの原文は「4条件」と表記だが
# 実際には5節列挙——docstring参照）すべてを正しく適用することのテスト
# ==============================================================================
def test_3_mainline_candidate_filter() -> None:
    print("\n=== 検証3: mainline候補生成フィルタ（各条件を単独でFalseにしたケース） ===")

    def fresh_state(**overrides) -> TopicGroupState:
        store: dict[str, TopicGroupState] = {}
        state = get_or_create_topic_group(store, "test-topic-group", "test-signature")
        for k, v in overrides.items():
            setattr(state, k, v)
        return state

    # 全条件OKなら通過する
    ok_state = fresh_state()
    r = passes_mainline_candidate_filter(ok_state, posted_theme_blocked=False, exploration_quota_remaining=True)
    _check("filter_all_conditions_ok_passes", r["passes"] is True, str(r))

    # 条件1: topic_status != active
    s1 = fresh_state(topic_status="exhausted")
    r1 = passes_mainline_candidate_filter(s1, posted_theme_blocked=False, exploration_quota_remaining=True)
    _check("filter_condition1_topic_status_blocks", r1["passes"] is False and not r1["topic_status_ok"], str(r1))

    # 条件2: posted_theme_blocked=True
    s2 = fresh_state()
    r2 = passes_mainline_candidate_filter(s2, posted_theme_blocked=True, exploration_quota_remaining=True)
    _check("filter_condition2_posted_theme_blocks", r2["passes"] is False and not r2["posted_theme_ok"], str(r2))

    # 条件3: retry_budget == 0
    s3 = fresh_state(topic_retry_budget=0)
    r3 = passes_mainline_candidate_filter(s3, posted_theme_blocked=False, exploration_quota_remaining=True)
    _check("filter_condition3_retry_budget_blocks", r3["passes"] is False and not r3["retry_budget_ok"], str(r3))

    # 条件4: cooldown中
    s4 = fresh_state(topic_cooldown_until="2099-12-31")
    r4 = passes_mainline_candidate_filter(s4, posted_theme_blocked=False, exploration_quota_remaining=True, today=date(2026, 8, 31))
    _check("filter_condition4_cooldown_blocks", r4["passes"] is False and not r4["cooldown_ok"], str(r4))

    # 条件5: exploration quota超過
    s5 = fresh_state()
    r5 = passes_mainline_candidate_filter(s5, posted_theme_blocked=False, exploration_quota_remaining=False)
    _check("filter_condition5_exploration_quota_blocks", r5["passes"] is False and not r5["exploration_quota_ok"], str(r5))


# ==============================================================================
# 検証: retry_budget消費による「不発テーマの延命」防止（record_mainline_attempt）
# ==============================================================================
def test_retry_budget_exhaustion() -> None:
    print("\n=== 追加検証: retry_budget消費でexhausted状態へ遷移する ===")
    store: dict[str, TopicGroupState] = {}
    state = get_or_create_topic_group(store, "test-topic-group-2", "test-signature-2")
    _check("initial_retry_budget", state.topic_retry_budget == TOPIC_GROUP_INITIAL_RETRY_BUDGET)

    for _ in range(TOPIC_GROUP_INITIAL_RETRY_BUDGET):
        record_mainline_attempt(state, succeeded=False)
    _check("exhausted_after_budget_depleted", state.topic_status == "exhausted" and state.topic_retry_budget == 0)
    _check("route_to_research_only_on_exhaustion", state.route_to_research_only is True)

    # succeeded=Trueでは消費しないことも確認
    store2: dict[str, TopicGroupState] = {}
    state2 = get_or_create_topic_group(store2, "test-topic-group-3", "test-signature-3")
    record_mainline_attempt(state2, succeeded=True)
    _check("succeeded_attempt_does_not_consume_budget", state2.topic_retry_budget == TOPIC_GROUP_INITIAL_RETRY_BUDGET)


# ==============================================================================
# 検証: record_publication / update_performance_band（フィードバック接続）
# ==============================================================================
def test_publication_and_performance_feedback() -> None:
    print("\n=== 追加検証: 実投稿・実績値フィードバックのライフサイクル遷移 ===")
    store: dict[str, TopicGroupState] = {}
    state = get_or_create_topic_group(store, "test-topic-group-4", "test-signature-4")
    record_publication(state, published_at="2026-08-29")
    _check("published_status", state.topic_status == "published")
    _check("retired_from_mainline_on_publish", state.topic_retired_from_mainline is True)
    _check("route_to_research_only_on_publish", state.route_to_research_only is True)
    _check("cooldown_until_set", state.topic_cooldown_until == "2026-09-19")  # +21日

    update_performance_band(state, impression_count=10)
    _check("performance_band_low_for_small_impressions", state.topic_performance_band == "low")

    update_performance_band(state, impression_count=None)
    _check("performance_band_unknown_when_no_data", state.topic_performance_band == "unknown")


# ==============================================================================
# 検証4/5は本スクリプト単体では完結しない（Gate A回帰・backfill非破壊は別途
# inspect.getsource()比較・git diffで確認する。詳細はops/reports/
# topic_group_lifecycle_design_2026-08-31.mdの「検証結果」節を参照）。
# ==============================================================================

if __name__ == "__main__":
    test_1_theme_signature_normalization()
    test_2_posted_theme_exclusion_integration()
    test_3_mainline_candidate_filter()
    test_retry_budget_exhaustion()
    test_publication_and_performance_feedback()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
