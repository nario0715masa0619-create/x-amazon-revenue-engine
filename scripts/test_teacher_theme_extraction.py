"""teacher_theme_extraction.py / topic_group_state.py（"proposed"状態追加分）の検証スクリプト。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイル
（scripts/test_topic_group_lifecycle.py等）に合わせ、
`python scripts/test_teacher_theme_extraction.py`で直接実行できるplain assert
ベースの検証スクリプトとする。

外部AI呼び出し・外部API呼び出しは一切行わない。Gate A/thresholds/shipping decision、
_apply_engagement_gate()、_classify_core()、topic_groupの既存ライフサイクル関数
（record_mainline_attempt等）・候補フィルタ本体には一切触れない。

実データ検証について: 本ファイルのテキスト例は、2026-09-02実施の実データ検証
（watched_account_state.jsonに登録済みの6アカウントから実際に取得したpre_teacher_candidate
投稿、st_r0817/Daisuke__otoko/fukunokioku/ikaretemitai/shun_4colors由来）をそのまま
固定したものであり、実際に確認済みの抽出結果と一致することを回帰確認する。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from teacher_theme_extraction import (
    build_teacher_theme_profile,
    has_extractable_theme,
    register_proposed_topic_group_from_teacher_post,
)
from topic_group_state import (
    TopicGroupState,
    get_or_create_topic_group,
    passes_mainline_candidate_filter,
    promote_proposed_topic_group,
    TopicGroupStateError,
)

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


# 2026-09-02実データ検証で実際に取得・確認済みのteacher投稿本文（4件、抜粋）。
_REAL_TEACHER_TEXT_DENIM_WHITE_T = (
    "平野紫耀は現代最強のロールモデル。\n"
    "・白T×デニムの王道コーデ\n・色は3色以内でまとめる\n・ワイドデニムで今っぽさを出す"
    "\n・白Tはジャスト〜ややゆるめ\n・黒ブーツで全体を締める\n・ゴールドアクセは1点だけ"
)
_REAL_TEACHER_TEXT_AKANUKE = (
    "良かれと思ってやってる男磨き、半分はムダかもしれない。\n"
    "代表的な“やってはいけない垢抜け”。\n"
    "・筋トレ“だけ”頑張る（顔・髪・服と同時にやらないと効果が薄い）\n"
    "・垢抜ける前に、恋愛アプリや商材に課金"
)
_REAL_TEACHER_TEXT_MELT_MOUSE = (
    "この前見てきた「Melt Mouse」が遂に情報解禁！やっと言えた。\n"
    "見た目は本当にミニマルなんだけど、機能性はクリエイター向けの製品でトップレベルだと思います。"
)


def test_extraction_on_real_fashion_teacher_post() -> None:
    print("\n=== 検証1: 実データ（白T×デニムコーデ投稿）からのテーマ抽出 ===")
    profile = build_teacher_theme_profile(_REAL_TEACHER_TEXT_DENIM_WHITE_T)
    _check("product_contains_denim", "デニム" in profile["theme_components"]["product"])
    _check("product_contains_white_t", "白T" in profile["theme_components"]["product"])
    _check("has_extractable_theme", has_extractable_theme(profile))
    _check("topic_group_id_not_unclassified", profile["topic_group_id"] != "unclassified")


def test_extraction_on_real_akanuke_teacher_post() -> None:
    print("\n=== 検証2: 実データ（垢抜けアドバイス投稿）からのテーマ抽出 ===")
    profile = build_teacher_theme_profile(_REAL_TEACHER_TEXT_AKANUKE)
    _check("product_contains_akanuke", "垢抜け" in profile["theme_components"]["product"])
    _check("has_extractable_theme", has_extractable_theme(profile))


def test_extraction_fails_gracefully_on_unmatched_vocabulary() -> None:
    print("\n=== 検証3: 既存辞書に無い語彙のみの投稿（Melt Mouse）は抽出不能として扱われること ===")
    # 「マウス」はGADGET_CORE_KEYWORDS/FASHION_CORE_KEYWORDS_SPECIFICのいずれにも
    # 含まれない（既知の抽出精度の限界。実データ検証で確認済み）。
    profile = build_teacher_theme_profile(_REAL_TEACHER_TEXT_MELT_MOUSE)
    _check(
        "unclassified_for_out_of_dictionary_product",
        not has_extractable_theme(profile),
        f"topic_group_id={profile['topic_group_id']!r}（辞書外語彙のため抽出不能が期待値）",
    )


def test_register_creates_proposed_status() -> None:
    print("\n=== 検証4: 登録処理が'proposed'状態でtopic_groupを作成すること ===")
    store: dict[str, TopicGroupState] = {}
    result = register_proposed_topic_group_from_teacher_post(
        store, _REAL_TEACHER_TEXT_DENIM_WHITE_T, source_diversity_tag="test-post-1"
    )
    _check("registration_succeeded", result is not None)
    state, profile = result
    _check("status_is_proposed", state.topic_status == "proposed", state.topic_status)
    _check("stored_in_dict", state.topic_group_id in store)
    _check("source_diversity_tag_recorded", state.source_diversity_tag == "test-post-1")


def test_register_skips_unclassifiable_text() -> None:
    print("\n=== 検証5: 抽出不能な投稿は登録されないこと ===")
    store: dict[str, TopicGroupState] = {}
    result = register_proposed_topic_group_from_teacher_post(store, _REAL_TEACHER_TEXT_MELT_MOUSE)
    _check("registration_returns_none", result is None)
    _check("store_stays_empty", store == {})


def test_proposed_excluded_from_mainline_candidate_filter() -> None:
    print("\n=== 検証6（最重要）: 'proposed'状態がpasses_mainline_candidate_filter()から除外されること ===")
    store: dict[str, TopicGroupState] = {}
    state = get_or_create_topic_group(store, "tg-proposed-test", "sig-proposed-test", initial_status="proposed")
    result = passes_mainline_candidate_filter(state, posted_theme_blocked=False, exploration_quota_remaining=True)
    _check("proposed_fails_filter", result["passes"] is False, str(result))
    _check("proposed_fails_status_check_specifically", result["topic_status_ok"] is False)


def test_promote_proposed_to_active() -> None:
    print("\n=== 検証7: promote_proposed_topic_group()が'proposed'->'active'へ正しく遷移させること ===")
    store: dict[str, TopicGroupState] = {}
    state = get_or_create_topic_group(store, "tg-promote-test", "sig-promote-test", initial_status="proposed")
    promoted = promote_proposed_topic_group(store, "tg-promote-test")
    _check("promoted_to_active", promoted.topic_status == "active", promoted.topic_status)

    filter_result = passes_mainline_candidate_filter(promoted, posted_theme_blocked=False, exploration_quota_remaining=True)
    _check("passes_filter_after_promotion", filter_result["passes"] is True, str(filter_result))


def test_promote_raises_on_non_proposed_status() -> None:
    print("\n=== 検証8: 'proposed'以外の状態をpromoteしようとするとエラーになること ===")
    store: dict[str, TopicGroupState] = {}
    get_or_create_topic_group(store, "tg-already-active", "sig-already-active")  # デフォルトactive
    raised = False
    try:
        promote_proposed_topic_group(store, "tg-already-active")
    except TopicGroupStateError:
        raised = True
    _check("raises_on_non_proposed_status", raised)


def test_promote_raises_on_missing_topic_group() -> None:
    print("\n=== 検証9: 存在しないtopic_group_idをpromoteしようとするとエラーになること ===")
    store: dict[str, TopicGroupState] = {}
    raised = False
    try:
        promote_proposed_topic_group(store, "tg-does-not-exist")
    except TopicGroupStateError:
        raised = True
    _check("raises_on_missing_topic_group", raised)


def test_get_or_create_topic_group_default_status_unchanged() -> None:
    print("\n=== 検証10: 既存の全呼び出し箇所との後方互換（initial_status未指定=activeのまま） ===")
    store: dict[str, TopicGroupState] = {}
    state = get_or_create_topic_group(store, "tg-default-status-test", "sig-default")
    _check("default_status_is_active", state.topic_status == "active", state.topic_status)


def test_get_or_create_topic_group_does_not_overwrite_existing() -> None:
    print("\n=== 検証11: 既存のtopic_group（activeまたはproposed）はinitial_status指定でも上書きされないこと ===")
    store: dict[str, TopicGroupState] = {}
    get_or_create_topic_group(store, "tg-existing", "sig-existing", initial_status="proposed")
    # 同じtopic_group_idに対し、initial_status="active"で再度呼んでも既存のproposedは維持される。
    state2 = get_or_create_topic_group(store, "tg-existing", "sig-existing-2", initial_status="active")
    _check("existing_proposed_status_preserved", state2.topic_status == "proposed", state2.topic_status)
    _check("existing_theme_signature_preserved", state2.theme_signature == "sig-existing", state2.theme_signature)


if __name__ == "__main__":
    test_extraction_on_real_fashion_teacher_post()
    test_extraction_on_real_akanuke_teacher_post()
    test_extraction_fails_gracefully_on_unmatched_vocabulary()
    test_register_creates_proposed_status()
    test_register_skips_unclassifiable_text()
    test_proposed_excluded_from_mainline_candidate_filter()
    test_promote_proposed_to_active()
    test_promote_raises_on_non_proposed_status()
    test_promote_raises_on_missing_topic_group()
    test_get_or_create_topic_group_default_status_unchanged()
    test_get_or_create_topic_group_does_not_overwrite_existing()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
