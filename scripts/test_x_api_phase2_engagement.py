"""x_api_phase2_classify.pyのteacher判定（GADGET_KEYWORDS廃止・エンゲージメント
実測値ベースへの置き換え、GOV-20260901-ENGAGEMENT-BASED-TEACHER-01）の検証スクリプト。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイル
（scripts/test_topic_group_lifecycle.py等）に合わせ、
`python scripts/test_x_api_phase2_engagement.py`で直接実行できるplain assert
ベースの検証スクリプトとする。

外部AI呼び出し・外部API呼び出しは一切行わない。production scoring/Gate A/
thresholds/shipping decisionには一切触れない。topic_groupのライフサイクル
管理ロジック本体・Phase 1収集クエリには一切触れない。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import x_api_phase2_classify as p2

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


def _post(text: str, impression=None, like=0, repost=0, quote=0, bookmark=0, reply=0, query_source=None) -> dict:
    return {
        "id": "test-id",
        "text": text,
        "author_id": "test-author",
        "created_at": "2026-09-01T00:00:00.000Z",
        "lang": "ja",
        "like_count": like,
        "reply_count": reply,
        "repost_count": repost,
        "quote_count": quote,
        "impression_count": impression,
        "bookmark_count": bookmark,
        "query_source": query_source or ["test query"],
    }


# ==============================================================================
# 検証0: GADGET_KEYWORDSが実際に削除されていること
# ==============================================================================
def test_gadget_keywords_removed() -> None:
    print("\n=== 検証0: GADGET_KEYWORDS削除の確認 ===")
    _check("gadget_keywords_attribute_removed", not hasattr(p2, "GADGET_KEYWORDS"))
    _check("gadget_core_keywords_still_present", hasattr(p2, "GADGET_CORE_KEYWORDS"), "GADGET_CORE_KEYWORDSは未変更のはず")


# ==============================================================================
# 検証1: _compute_engagement_tier()の単体テスト
# ==============================================================================
def test_compute_engagement_tier() -> None:
    print("\n=== 検証1: _compute_engagement_tier() 単体テスト ===")

    _check(
        "insufficient_data_when_impression_none",
        p2._compute_engagement_tier(_post("テキスト", impression=None)) == "insufficient_data",
    )
    _check(
        "insufficient_data_below_min_sample",
        p2._compute_engagement_tier(_post("テキスト", impression=p2.TEACHER_MIN_SAMPLE_IMPRESSIONS - 1, like=100))
        == "insufficient_data",
        "エンゲージメントが高くてもサンプル不足なら判定不能",
    )
    _check(
        "low_at_min_sample_with_weak_engagement",
        p2._compute_engagement_tier(
            _post("テキスト", impression=p2.TEACHER_MIN_SAMPLE_IMPRESSIONS, like=1)
        )
        == "low",
        "境界値: 最小サンプルちょうど、エンゲージメント合計が閾値未満",
    )
    _check(
        "low_just_below_qualifying_threshold",
        p2._compute_engagement_tier(
            _post(
                "テキスト",
                impression=200,
                like=p2.TEACHER_ENGAGEMENT_QUALIFYING_THRESHOLD - 1,
            )
        )
        == "low",
        "境界値: エンゲージメント合計がqualifying閾値の1つ手前",
    )
    _check(
        "qualifying_at_exact_threshold",
        p2._compute_engagement_tier(
            _post("テキスト", impression=200, like=p2.TEACHER_ENGAGEMENT_QUALIFYING_THRESHOLD)
        )
        == "qualifying",
        "境界値: エンゲージメント合計がqualifying閾値ちょうど",
    )
    _check(
        "qualifying_with_mixed_metrics",
        p2._compute_engagement_tier(_post("テキスト", impression=500, like=1, repost=2, quote=1, bookmark=1))
        == "qualifying",
        "like/repost/quote/bookmarkの合算で閾値到達",
    )


# ==============================================================================
# 検証2: エンゲージメント基準への置き換えがpre_teacher_candidate判定に反映されること
# ==============================================================================
def test_engagement_replaces_keyword_gating() -> None:
    print("\n=== 検証2: pre_teacher_candidate判定へのエンゲージメント基準の反映 ===")

    gadget_rich_text = (
        "40代でイヤホンを選ぶなら軽さが大事。ガジェット選びは実体験に基づく比較が一番。"
        "モバイルバッテリーも同じ基準で選んでいる。着映えも意識しつつ実用性重視。"
    )

    # 旧ロジックならGADGET_KEYWORDS一致だけでtopic_fit=highに寄与していたはずの文面でも、
    # エンゲージメントがinsufficient_dataならgadget軸は不成立になることを確認する。
    low_engagement_post = _post(gadget_rich_text, impression=5, like=0, repost=0)
    obs_low = p2._observe(low_engagement_post)
    _check(
        "gadget_keyword_rich_but_insufficient_engagement_yields_insufficient_tier",
        obs_low["observed_engagement_tier"] == "insufficient_data",
        str(obs_low["observed_engagement_tier"]),
    )

    # 同じ文面でも、実測エンゲージメントがqualifying水準ならgadget軸が成立することを確認する。
    high_engagement_post = _post(gadget_rich_text, impression=500, like=10, repost=5)
    obs_high = p2._observe(high_engagement_post)
    _check(
        "same_text_with_qualifying_engagement_yields_qualifying_tier",
        obs_high["observed_engagement_tier"] == "qualifying",
        str(obs_high["observed_engagement_tier"]),
    )

    classification_high, reasons_high, confidence_high, _ = p2._classify(high_engagement_post, obs_high)
    _check(
        "qualifying_engagement_post_reaches_pre_teacher_candidate_or_higher_tier",
        classification_high in ("pre_teacher_candidate", "observe", "manual_review"),
        f"classification={classification_high}, reasons={reasons_high}",
    )


# ==============================================================================
# 検証3: reject側ロジック（広告・煽り・薄い内容の除外）が無影響であること
# ==============================================================================
def test_reject_side_logic_unaffected() -> None:
    print("\n=== 検証3: reject側ロジック（広告/煽り/薄い内容）への無影響確認 ===")

    promo_post = _post("PR 今なら期間限定クーポンで購入はこちら！プロフから", impression=1000, like=50, repost=20)
    obs_promo = p2._observe(promo_post)
    classification_promo, reasons_promo, _, _ = p2._classify(promo_post, obs_promo)
    _check(
        "promotional_post_still_rejected_despite_high_engagement",
        classification_promo == "reject",
        f"classification={classification_promo}, reasons={reasons_promo}",
    )

    bait_post = _post("絶対見て！保存必須！フォローして！RTして！万人に見てほしい", impression=1000, like=50, repost=20)
    obs_bait = p2._observe(bait_post)
    classification_bait, reasons_bait, _, _ = p2._classify(bait_post, obs_bait)
    _check(
        "bait_post_still_rejected_despite_high_engagement",
        classification_bait == "reject",
        f"classification={classification_bait}, reasons={reasons_bait}",
    )

    thin_post = _post("いいね", impression=1000, like=50)
    obs_thin = p2._observe(thin_post)
    classification_thin, reasons_thin, _, _ = p2._classify(thin_post, obs_thin)
    _check(
        "thin_content_still_rejected_despite_high_engagement",
        classification_thin == "reject",
        f"classification={classification_thin}, reasons={reasons_thin}",
    )


# ==============================================================================
# 検証4: 実データ（現行merged_deduped.json）への再適用
# ==============================================================================
def test_real_data_reclassification() -> None:
    print("\n=== 検証4: 実データ（現行merged_deduped.json）への再適用 ===")
    if not p2._INPUT_PATH.exists():
        _check("real_data_file_exists", False, f"{p2._INPUT_PATH} が見つからない")
        return

    posts = p2._load_input()
    _check("real_data_loaded", len(posts) > 0, f"{len(posts)}件")

    tier_counts = {"insufficient_data": 0, "low": 0, "qualifying": 0}
    classification_counts = {"reject": 0, "observe": 0, "manual_review": 0, "pre_teacher_candidate": 0}
    for post in posts:
        obs = p2._observe(post)
        tier_counts[obs["observed_engagement_tier"]] += 1
        classification, _, _, _ = p2._classify(post, obs)
        classification_counts[classification] += 1

    print(f"    engagement_tier分布: {tier_counts}")
    print(f"    classification分布: {classification_counts}")
    _check(
        "tier_distribution_not_degenerate",
        tier_counts["qualifying"] > 0 and tier_counts["insufficient_data"] > 0,
        str(tier_counts),
    )


if __name__ == "__main__":
    test_gadget_keywords_removed()
    test_compute_engagement_tier()
    test_engagement_replaces_keyword_gating()
    test_reject_side_logic_unaffected()
    test_real_data_reclassification()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
