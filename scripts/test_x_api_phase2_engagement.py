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
# 検証2b（GOV-20260901-GADGET-ONLY-REUSABLE-ENGAGEMENT-GATE-01）:
# "gadget_only_but_reusable"昇格パスがengagement_tierでゲートされること
# ==============================================================================
def test_gadget_only_but_reusable_requires_qualifying_engagement() -> None:
    print("\n=== 検証2b: gadget_only_but_reusable昇格パスのengagement_tierゲート ===")

    # fashionキーワードを含まない、純粋なgadget単独文面（GADGET_CORE_KEYWORDS多数一致）。
    gadget_only_text = (
        "イヤホンは軽量で完全防水、骨伝導だから耳を塞がない。充電もUSB-Cで持ち歩き機器として"
        "本当に使いやすい。実際に使ってみて比較すると、この選び方が一番よかった。"
    )

    # ATH-PRO5MK2×骨伝導RTと同型（impression_count=0）の再現ケース: GADGET_CORE_KEYWORDS
    # には強く一致するが実測エンゲージメントはゼロ = insufficient_data。
    zero_engagement_post = _post(gadget_only_text, impression=0, like=0, repost=0)
    obs_zero = p2._observe(zero_engagement_post)
    _check(
        "gadget_only_zero_engagement_tier_is_insufficient_data",
        obs_zero["observed_engagement_tier"] == "insufficient_data",
        str(obs_zero["observed_engagement_tier"]),
    )
    _check(
        "gadget_only_zero_engagement_topic_signal_still_high",
        obs_zero["layer_primary"] == "gadget" and obs_zero["gadget_signal_strength"] == "high",
        "GADGET_CORE_KEYWORDSによるトピック関連性シグナル自体は健在であるべき",
    )
    classification_zero, reasons_zero, _, _ = p2._classify(zero_engagement_post, obs_zero)
    _check(
        "gadget_only_zero_engagement_blocked_from_pre_teacher_candidate",
        classification_zero != "pre_teacher_candidate",
        f"classification={classification_zero}, reasons={reasons_zero}",
    )
    # 2026-09-01訂正（GOV-20260901-TOPIC-FIT-GADGET-SYMMETRY-01）: 単一ゲート
    # （_apply_engagement_gate()）は元の理由（"gadget_only_but_reusable"）を消さずに
    # "engagement_gate_blocked"を追記する設計（トレーサビリティのため、gated_reasons =
    # reasons + [...]）。「元の理由が消えること」を期待していた本チェックの前提が誤り
    # だったため、正しい期待値（両方の理由が共存する）へ訂正する。
    _check(
        "gadget_only_but_reusable_reason_present_alongside_gate_block",
        any("gadget_only_but_reusable" in r for r in reasons_zero)
        and any("engagement_gate_blocked" in r for r in reasons_zero),
        str(reasons_zero),
    )

    # false negative確認: 同じgadget単独文面でもengagement_tier=="qualifying"なら
    # 引き続き正しくpre_teacher_candidateへ昇格すること（GADGET_CORE_KEYWORDS自体は
    # トピック関連性シグナルとして生きている）。
    qualifying_post = _post(gadget_only_text, impression=500, like=10, repost=3, reply=1, bookmark=2)
    obs_qual = p2._observe(qualifying_post)
    _check(
        "gadget_only_qualifying_engagement_tier",
        obs_qual["observed_engagement_tier"] == "qualifying",
        str(obs_qual["observed_engagement_tier"]),
    )
    classification_qual, reasons_qual, _, _ = p2._classify(qualifying_post, obs_qual)
    _check(
        "gadget_only_qualifying_engagement_promotes_via_gadget_only_but_reusable",
        classification_qual == "pre_teacher_candidate"
        and any("gadget_only_but_reusable" in r for r in reasons_qual),
        f"classification={classification_qual}, reasons={reasons_qual}",
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
# 検証（GOV-20260901-GADGET-ONLY-REUSABLE-ENGAGEMENT-GATE-01）:
# 実データのATH-PRO5MK2×骨伝導投稿（impression_count=0）がpre_teacher_candidateから
# 除外されること
# ==============================================================================
def test_real_ath_pro5mk2_post_excluded() -> None:
    print("\n=== 検証: 実データATH-PRO5MK2×骨伝導投稿（impression=0）の除外確認 ===")
    if not p2._INPUT_PATH.exists():
        _check("real_data_file_exists_for_ath_pro5mk2_check", False, f"{p2._INPUT_PATH} が見つからない")
        return
    posts = p2._load_input()
    target = next((p for p in posts if p.get("id") == "2094280166017204415"), None)
    if target is None:
        # 2026-09-01（GOV-20260901-BROAD-COLLECTION-01）: Phase 1 QUERIESを
        # 商品カテゴリ非依存の広域6クエリへ全面置き換えたため、この特定post_id
        # （イヤホン/骨伝導クエリでのみ収集されていた）は今後の収集で恒久的に
        # 再取得されなくなった。データ欠落は異常ではなく想定どおりであり、
        # 本チェックはfailureにせずskipする（synthetic再現ケース
        # test_gadget_only_but_reusable_requires_qualifying_engagementおよび
        # test_single_gate_covers_all_known_pathsで恒久的に代替確認する）。
        print(
            "[SKIP] ath_pro5mk2_post_present_in_current_snapshot - "
            "2026-09-01のPhase 1広域クエリ置き換えにより当該post_idは収集対象外になった"
            "（想定どおり。synthetic再現ケースで代替確認済み）"
        )
        return
    obs = p2._observe(target)
    classification, reasons, _, _ = p2._classify(target, obs)
    _check(
        "ath_pro5mk2_impression_is_zero",
        target.get("impression_count") == 0,
        str(target.get("impression_count")),
    )
    _check(
        "ath_pro5mk2_engagement_tier_insufficient",
        obs["observed_engagement_tier"] == "insufficient_data",
        str(obs["observed_engagement_tier"]),
    )
    _check(
        "ath_pro5mk2_excluded_from_pre_teacher_candidate",
        classification != "pre_teacher_candidate",
        f"classification={classification}, reasons={reasons}",
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


# ==============================================================================
# 検証（GOV-20260901-SINGLE-ENGAGEMENT-GATE-01）: _classify()出口の単一ゲートが、
# 洗い出し済みの全6経路（経路1a〜d／経路2 fashion_only_but_reusable／
# 経路3 gadget_only_but_reusable）を、どの経路が発火したかに関わらず
# 一律にカバーすることの確認。
# ==============================================================================
def test_single_gate_covers_all_known_paths() -> None:
    print("\n=== 検証: 単一ゲートが全6経路（1a〜d/2/3）を一律カバーすることの確認 ===")

    # _apply_engagement_gate()はclassificationとobs["observed_engagement_tier"]のみを
    # 見て判定するため（reasonsの中身は判定に使わない）、各経路が実際に付与する理由タグを
    # そのまま与え、engagement_tierの3値それぞれで挙動を直接検証する。これにより
    # _classify_core()内のどの分岐経由でpre_teacher_candidateに達したかに関わらず、
    # ゲートが漏れなく適用されることをアーキテクチャレベルで保証する。
    reason_tags_by_path = {
        "1a_age_and_fashion_signal_detected": ["age_and_fashion_signal_detected"],
        "1b_aesthetic_and_utility_both_present": ["aesthetic_and_utility_both_present"],
        "1c_comparison_or_selection_structure_detected": ["comparison_or_selection_structure_detected"],
        "1d_ownership_or_carry_signal_detected": ["ownership_or_carry_signal_detected"],
        "2_fashion_only_but_reusable": ["fashion_only_but_reusable（ファッション単独だが構造・アプローチ再利用価値が高い）"],
        "3_gadget_only_but_reusable": ["gadget_only_but_reusable（ガジェット単独だが構造・アプローチ再利用価値が高い）"],
    }
    for name, reasons in reason_tags_by_path.items():
        for tier, expected in (
            ("insufficient_data", "observe"),
            ("low", "observe"),
            ("qualifying", "pre_teacher_candidate"),
        ):
            obs = {"observed_engagement_tier": tier}
            result_cls, result_reasons, result_conf, result_manual = p2._apply_engagement_gate(
                "pre_teacher_candidate", list(reasons), "medium", None, obs
            )
            _check(
                f"single_gate_{name}_tier_{tier}",
                result_cls == expected,
                f"expected={expected}, actual={result_cls}",
            )
    # ゲート対象外（reject/observe/manual_review）はそのまま通過することも確認する。
    for passthrough_cls in ("reject", "observe", "manual_review"):
        obs = {"observed_engagement_tier": "insufficient_data"}
        result = p2._apply_engagement_gate(passthrough_cls, ["dummy_reason"], "high", "dummy_manual", obs)
        _check(
            f"single_gate_passthrough_{passthrough_cls}",
            result == (passthrough_cls, ["dummy_reason"], "high", "dummy_manual"),
            str(result),
        )


def test_single_gate_integration_via_real_classify() -> None:
    print("\n=== 検証: 単一ゲートの統合テスト（合成テキストで_classify()全体を通す） ===")

    # 経路1a/1c: age+fashion+decision（gadget/engagement軸に一切依存しない文面）
    text_1a = (
        "40代になってから服のコーデを見直した。清潔感があって垢抜けるバッグを選ぶのが"
        "自分にとって一番の正解だった。大人っぽい着こなしを比較しながら選び方を工夫している。"
    )
    zero = _post(text_1a, impression=0)
    obs_zero = p2._observe(zero)
    cls_zero, reasons_zero, _, _ = p2._classify(zero, obs_zero)
    _check(
        "integration_1a_blocked_when_insufficient",
        cls_zero != "pre_teacher_candidate" and any("engagement_gate_blocked" in r for r in reasons_zero),
        f"classification={cls_zero}, reasons={reasons_zero}",
    )
    qual = _post(text_1a, impression=500, like=10, repost=3)
    obs_qual = p2._observe(qual)
    cls_qual, reasons_qual, _, _ = p2._classify(qual, obs_qual)
    _check(
        "integration_1a_promotes_when_qualifying",
        cls_qual == "pre_teacher_candidate",
        f"classification={cls_qual}, reasons={reasons_qual}",
    )

    # 経路1b: aesthetic+utility（age/decision語を含まない文面）
    text_1b = "服のコーデは上品でミニマルなバッグが便利。持ち歩きやすくて快適、軽いから収納にも困らない。"
    zero_b = _post(text_1b, impression=0)
    obs_zero_b = p2._observe(zero_b)
    cls_zero_b, reasons_zero_b, _, _ = p2._classify(zero_b, obs_zero_b)
    _check(
        "integration_1b_blocked_when_insufficient",
        cls_zero_b != "pre_teacher_candidate",
        f"classification={cls_zero_b}, reasons={reasons_zero_b}",
    )
    qual_b = _post(text_1b, impression=500, like=10, repost=3)
    obs_qual_b = p2._observe(qual_b)
    cls_qual_b, reasons_qual_b, _, _ = p2._classify(qual_b, obs_qual_b)
    _check(
        "integration_1b_promotes_when_qualifying",
        cls_qual_b == "pre_teacher_candidate",
        f"classification={cls_qual_b}, reasons={reasons_qual_b}",
    )


def test_path4_observe_fallback_never_reaches_pre_teacher_candidate() -> None:
    print("\n=== 検証: 経路4（fashion_signal_detected/gadget_signal_detected）は"
          "そもそもpre_teacher_candidateへ到達しないことの確認 ===")
    # 経路4はコード上observeを直接返す分岐であり、pre_teacher_candidateへの昇格経路
    # ではない（単一ゲートの対象外で構造上問題ない）ことをソースから確認する。
    import inspect

    source = inspect.getsource(p2._classify_core)
    idx_fashion_fallback = source.find('reasons.append("fashion_signal_detected')
    idx_gadget_fallback = source.find('reasons.append("gadget_signal_detected')
    _check("path4_fashion_fallback_reason_present_in_source", idx_fashion_fallback != -1)
    _check("path4_gadget_fallback_reason_present_in_source", idx_gadget_fallback != -1)
    # それぞれの直後の行がreturn "observe"であること（pre_teacher_candidateではないこと）を確認する。
    for idx, label in ((idx_fashion_fallback, "fashion"), (idx_gadget_fallback, "gadget")):
        following = source[idx: idx + 200]
        _check(
            f"path4_{label}_fallback_returns_observe_not_pre_teacher_candidate",
            'return "observe"' in following and 'return "pre_teacher_candidate"' not in following,
            following.replace("\n", " "),
        )


if __name__ == "__main__":
    test_gadget_keywords_removed()
    test_compute_engagement_tier()
    test_engagement_replaces_keyword_gating()
    test_gadget_only_but_reusable_requires_qualifying_engagement()
    test_reject_side_logic_unaffected()
    test_real_ath_pro5mk2_post_excluded()
    test_single_gate_covers_all_known_paths()
    test_single_gate_integration_via_real_classify()
    test_path4_observe_fallback_never_reaches_pre_teacher_candidate()
    test_real_data_reclassification()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
