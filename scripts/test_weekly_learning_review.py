"""weekly_learning_review（既存の週次集計）と、新設のtopic_group分裂検出
（GOV-20260901-TOPIC-GROUP-SPLIT-DETECTION-01）の検証スクリプト。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイル
（scripts/test_topic_group_lifecycle.py等）に合わせ、
`python scripts/test_weekly_learning_review.py`で直接実行できるplain assert
ベースの検証スクリプトとする。

外部AI呼び出し・外部API呼び出しは一切行わない。
production scoring/Gate A/thresholds/shipping decisionには一切触れない。
build_topic_group()のグルーピングロジック本体はここでは変更しない
（既に保存済みのtheme_signature/topic_group_idの組を検出するのみ）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from topic_group_state import (
    TopicGroupState,
    get_or_create_topic_group,
    record_topic_group_run_observed,
    load_topic_group_state_store,
    detect_theme_signature_splits,
)
from weekly_learning_review import (
    aggregate_weekly_learning_review,
    render_weekly_learning_review_markdown,
)

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


_SAMPLE_MINIMAL_RUN_LOGS = [
    {"run_id": "r1", "mainline_status": "completed", "used_fallback_source": False, "source_post_id": "s1"},
    {"run_id": "r2", "mainline_status": "closed_incomplete", "used_fallback_source": True, "source_post_id": "s2"},
]
_SAMPLE_ENRICHMENT_RECORDS = [
    {"run_id": "r1", "enrichment_status": "completed", "structure_hook_divergence": False},
]


# ==============================================================================
# 検証: 既存のweekly_learning_review集計・レンダリングが無変更で動作すること（回帰確認）
# ==============================================================================
def test_existing_aggregation_unaffected() -> None:
    print("\n=== 回帰確認: topic_group_store未指定時の既存集計動作 ===")
    review = aggregate_weekly_learning_review(
        minimal_run_logs=_SAMPLE_MINIMAL_RUN_LOGS,
        enrichment_records=_SAMPLE_ENRICHMENT_RECORDS,
        period_start="2026-08-25",
        period_end="2026-08-31",
    )
    _check("total_run_count", review.total_run_count == 2)
    _check("mainline_completed_count", review.mainline_completed_count == 1)
    _check("mainline_closed_incomplete_count", review.mainline_closed_incomplete_count == 1)
    _check("fallback_source_used_count", review.fallback_source_used_count == 1)
    _check("topic_group_signature_splits_empty_by_default", review.topic_group_signature_splits == [])

    md = render_weekly_learning_review_markdown(review, title="回帰確認レビュー")
    for existing_heading in [
        "## 1. 今週の本線運用状況",
        "## 2. enrichment実行状況",
        "## 3. divergence発生状況",
        "## 4. human vs structure/hook傾向",
        "## 5. contamination / fallback / source variability",
        "## 6. 次週の研究フォーカス",
        "## 7. one_line_takeaway",
    ]:
        _check(f"existing_section_present[{existing_heading}]", existing_heading in md)
    _check("no_split_case_message_present", "分裂は検出されなかった" in md)


# ==============================================================================
# 検証: 意図的に分裂させたテストケースで検出が機能すること
# ==============================================================================
def test_detects_intentional_split() -> None:
    print("\n=== 検証: 意図的なtheme_signature分裂の検出 ===")
    store: dict[str, TopicGroupState] = {}
    s1 = get_or_create_topic_group(store, "tg-split-A", "shared-signature-x")
    s2 = get_or_create_topic_group(store, "tg-split-B", "shared-signature-x")
    for _ in range(5):
        record_topic_group_run_observed(s1)
    for _ in range(2):
        record_topic_group_run_observed(s2)
    # 分裂していない別テーマも同居させ、誤検出しないことを確認する
    s3 = get_or_create_topic_group(store, "tg-unrelated", "unrelated-signature-y")
    record_topic_group_run_observed(s3)

    splits = detect_theme_signature_splits(store)
    _check("split_count", len(splits) == 1, str(splits))
    if splits:
        split = splits[0]
        _check("split_type_is_exact", split["split_type"] == "exact_signature_match")
        _check("split_signature", split["theme_signature"] == "shared-signature-x")
        _check("split_group_ids", sorted(split["topic_group_ids"]) == ["tg-split-A", "tg-split-B"])
        _check("split_combined_run_count", split["combined_mainline_run_count"] == 7, str(split))

    # storeがdetect_theme_signature_splits呼び出し前後で不変であること（read-only性の確認）
    _check("store_unchanged_after_detection", store["tg-split-A"].mainline_run_count == 5)
    _check("store_unchanged_after_detection_b", store["tg-split-B"].mainline_run_count == 2)

    review = aggregate_weekly_learning_review(
        minimal_run_logs=_SAMPLE_MINIMAL_RUN_LOGS,
        enrichment_records=_SAMPLE_ENRICHMENT_RECORDS,
        topic_group_store=store,
    )
    _check("review_contains_split", len(review.topic_group_signature_splits) == 1)
    md = render_weekly_learning_review_markdown(review, title="分裂検出レビュー")
    _check("markdown_contains_signature", "shared-signature-x" in md)
    _check("markdown_contains_both_group_ids", "tg-split-A" in md and "tg-split-B" in md)
    _check("markdown_contains_combined_count", "実質露出回数" in md and "7" in md)


# ==============================================================================
# 検証: theme_signatureが完全一致ではないが近縁（near-duplicate）な分裂ケースの検出
# ==============================================================================
def test_detects_near_duplicate_split() -> None:
    print("\n=== 検証: near-duplicate signatureによる分裂検出 ===")
    store: dict[str, TopicGroupState] = {}
    s1 = get_or_create_topic_group(store, "tg-near-A", "product-x__gym__call-quality__bone-vs-sealed")
    s2 = get_or_create_topic_group(
        store, "tg-near-B", "product-x__gym__call-quality__bone-vs-sealed__split-settled"
    )
    record_topic_group_run_observed(s1)
    record_topic_group_run_observed(s1)
    record_topic_group_run_observed(s2)
    # 無関係なsignatureは巻き込まれないことも確認する
    s3 = get_or_create_topic_group(store, "tg-far", "totally-unrelated-product__office__price")
    record_topic_group_run_observed(s3)

    splits = detect_theme_signature_splits(store)
    _check("near_duplicate_split_count", len(splits) == 1, str(splits))
    if splits:
        split = splits[0]
        _check("near_duplicate_split_type", split["split_type"] == "near_duplicate_signature")
        _check("near_duplicate_similarity_ge_threshold", split["similarity"] >= 0.6, str(split["similarity"]))
        _check("near_duplicate_group_ids", sorted(split["topic_group_ids"]) == ["tg-near-A", "tg-near-B"])
        _check("near_duplicate_combined_run_count", split["combined_mainline_run_count"] == 3, str(split))


# ==============================================================================
# 検証: 分裂がない正常ケースでは何も報告されないこと
# ==============================================================================
def test_no_split_reports_nothing() -> None:
    print("\n=== 検証: 分裂が無い正常ケース ===")
    store: dict[str, TopicGroupState] = {}
    get_or_create_topic_group(store, "tg-solo-A", "solo-signature")
    get_or_create_topic_group(store, "tg-solo-B", "another-solo-signature")
    splits = detect_theme_signature_splits(store)
    _check("no_split_detected", splits == [], str(splits))


# ==============================================================================
# 検証: 実データ（ATH-PRO5MK2×ジム用骨伝導、backfillで確認済みの実分裂ケース）の再確認
# ==============================================================================
def test_real_backfilled_data_split_case() -> None:
    print("\n=== 検証: 実データ再現（backfill済みtopic_group_stateからの検出） ===")
    repo_root = Path(__file__).resolve().parent.parent
    state_path = repo_root / "ops" / "reports" / "topic_group_state_2026-09-01.json"
    if not state_path.exists():
        _check("real_data_file_exists", False, f"{state_path} が見つからない（backfill未実行の可能性）")
        return
    store = load_topic_group_state_store(state_path)
    splits = detect_theme_signature_splits(store)
    _check("real_data_split_detected", len(splits) == 1, str(splits))
    if splits:
        found = splits[0]
        # 実データの2エントリはtheme_signatureも互いに異なる（"__split-settled"タグ1つ分の差）ため、
        # exact_signature_matchではなくnear_duplicate_signatureとして検出されるのが正しい。
        # これは本タスクの依頼文とのdocumented discrepancy（コード内docstring参照）。
        _check("real_data_split_type_is_near_duplicate", found["split_type"] == "near_duplicate_signature", str(found))
        ids = sorted(found["topic_group_ids"])
        _check(
            "real_data_expected_ids",
            ids == [
                "ath-pro5mk2-bone-conduction-neckband__call-quality-lightness",
                "ath-pro5mk2-bone-conduction-neckband__call-quality-lightness-split-use",
            ],
            str(ids),
        )
        _check(
            "real_data_combined_run_count_matches_known_7_runs",
            found["combined_mainline_run_count"] == 7,
            str(found["combined_mainline_run_count"]),
        )
        _check("real_data_similarity_above_threshold", found["similarity"] is not None and found["similarity"] >= 0.6, str(found["similarity"]))


if __name__ == "__main__":
    test_existing_aggregation_unaffected()
    test_detects_intentional_split()
    test_detects_near_duplicate_split()
    test_no_split_reports_nothing()
    test_real_backfilled_data_split_case()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
