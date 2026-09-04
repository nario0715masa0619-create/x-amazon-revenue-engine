"""pre_publish_checklist.py（下書き記録前の必須事前チェック）の検証スクリプト。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイルに合わせ、
`python scripts/test_pre_publish_checklist.py`で直接実行できるplain assertベースの
検証スクリプトとする。

外部API呼び出しは一切行わない。Gate A/thresholds/shipping decisionには一切触れない。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pre_publish_checklist import (
    PrePublishChecklistError,
    check_compliance_applicability,
    check_factual_verification_flag,
    extract_proper_noun_candidates,
    run_pre_publish_checklist,
    validate_checklist_before_recording,
)

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


# mainline-run-2026-09-04-010の実下書き本文（回帰フィクスチャ）
MENS_OSUSUME_DRAFT = (
    "大人の男性が新宿で服を買うならこの辺りのお店をチェックするのがおすすめ。"
    "ビューティ&ユース/UA、トゥモローランド、アーバンリサーチ、スティーブン・アラン、"
    "グリーンレーベル、エディフィス、伊勢丹メンズ館。\n"
    "使いやすさ重視かこだわり派かで選ぶ店を変える。\n"
    "個人的にはどの店にもそれぞれの良さがあって、結局全部回ってしまう"
)

# 前々回（デニム-定番-服__定番）の実下書き本文。固有名詞を含まない参照ケース。
DENIM_DRAFT = (
    "結局よく着ているのは、昔から好きな定番の服ばかり。Tシャツ、シャツ、デニム、軍パン、ローファー。\n"
    "定番と新しさのバランスを保つ姿勢。\n"
    "40代の服選びは、これくらいのバランスがちょうどいい"
)


def test_compliance_not_applicable_when_no_signals() -> None:
    print("\n=== 検証1: Amazon言及/購入CTA/リンクが無ければcompliance_review_required=Falseになること ===")
    result = check_compliance_applicability(MENS_OSUSUME_DRAFT)
    _check("not_required", result["compliance_review_required"] is False, str(result))
    _check("reasons_recorded", len(result["reasons"]) >= 1, str(result["reasons"]))


def test_compliance_applicable_with_amazon_link() -> None:
    print("\n=== 検証2: Amazonリンクを含む下書きはcompliance_review_required=Trueになること ===")
    draft = MENS_OSUSUME_DRAFT + "\n詳しくはこちら: https://amzn.to/xxxxx"
    result = check_compliance_applicability(draft)
    _check("required", result["compliance_review_required"] is True, str(result))
    _check("reason_mentions_link", any("リンク" in r for r in result["reasons"]))


def test_compliance_applicable_with_purchase_cta() -> None:
    print("\n=== 検証3: 購入CTAキーワードを含む下書きはcompliance_review_required=Trueになること ===")
    draft = MENS_OSUSUME_DRAFT + "\n#PR"
    result = check_compliance_applicability(draft)
    _check("required", result["compliance_review_required"] is True, str(result))


def test_factual_verification_required_for_store_names() -> None:
    print("\n=== 検証4: 実店舗名を含む下書きはfactual_verification_required=Trueになること（mainline-run-2026-09-04-010実データ） ===")
    result = check_factual_verification_flag(MENS_OSUSUME_DRAFT)
    _check("required", result["factual_verification_required"] is True, str(result))
    for expected in ["トゥモローランド", "アーバンリサーチ", "エディフィス", "伊勢丹メンズ館"]:
        _check(f"detected_{expected}", expected in result["detected_proper_nouns"], str(result["detected_proper_nouns"]))


def test_factual_verification_not_required_without_proper_nouns() -> None:
    print("\n=== 検証5: 固有名詞を含まない下書き（デニム-定番-服__定番実データ）はfactual_verification_required=Falseになること ===")
    result = check_factual_verification_flag(DENIM_DRAFT)
    _check("not_required", result["factual_verification_required"] is False, str(result))
    _check("no_candidates", result["detected_proper_nouns"] == [], str(result["detected_proper_nouns"]))


def test_generic_fashion_topic_words_not_flagged_as_proper_nouns() -> None:
    print("\n=== 検証6: FASHION_CORE_KEYWORDS等の一般的な話題語（デニム/白T等）が誤って固有名詞扱いされないこと ===")
    draft = "白Tとデニムでコーデするならワイドパンツが今っぽい"
    candidates = extract_proper_noun_candidates(draft)
    _check("no_generic_topic_words_flagged", candidates == [], str(candidates))


def test_generic_katakana_verb_not_flagged() -> None:
    print("\n=== 検証7: 「チェック」等の一般的な片仮名語が固有名詞候補から除外されること ===")
    candidates = extract_proper_noun_candidates("この辺りのお店をチェックするのがおすすめ")
    _check("check_not_flagged", "チェック" not in candidates, str(candidates))


def test_validate_blocks_when_compliance_flag_unmet() -> None:
    print("\n=== 検証8: compliance_review_required=Trueなのにresultが未記入だとブロックされること ===")
    checklist = {"compliance_review_required": True, "factual_verification_required": False}
    try:
        validate_checklist_before_recording(checklist, compliance_review_result=None, factual_verification_result=None)
        _check("raised", False, "例外が発生しなかった")
    except PrePublishChecklistError:
        _check("raised", True)


def test_validate_blocks_when_factual_flag_unmet() -> None:
    print("\n=== 検証9: factual_verification_required=Trueなのにresultが未記入だとブロックされること ===")
    checklist = {"compliance_review_required": False, "factual_verification_required": True}
    try:
        validate_checklist_before_recording(checklist, compliance_review_result=None, factual_verification_result=None)
        _check("raised", False, "例外が発生しなかった")
    except PrePublishChecklistError:
        _check("raised", True)


def test_validate_passes_when_all_results_filled() -> None:
    print("\n=== 検証10: 両フラグとも結果が記入済みならブロックされないこと ===")
    checklist = {"compliance_review_required": True, "factual_verification_required": True}
    try:
        validate_checklist_before_recording(
            checklist,
            compliance_review_result="非該当と判定済み（記録用ダミー）",
            factual_verification_result="7店舗すべて営業確認済み（記録用ダミー）",
        )
        _check("no_exception", True)
    except PrePublishChecklistError as e:
        _check("no_exception", False, str(e))


def test_validate_passes_when_no_flags_required() -> None:
    print("\n=== 検証11: どちらのフラグも立っていなければ結果未記入でもブロックされないこと ===")
    checklist = {"compliance_review_required": False, "factual_verification_required": False}
    try:
        validate_checklist_before_recording(checklist, compliance_review_result=None, factual_verification_result=None)
        _check("no_exception", True)
    except PrePublishChecklistError as e:
        _check("no_exception", False, str(e))


def test_run_pre_publish_checklist_integration_mens_osusume() -> None:
    print("\n=== 検証12: run_pre_publish_checklist()統合テスト（mainline-run-2026-09-04-010実データ） ===")
    result = run_pre_publish_checklist(MENS_OSUSUME_DRAFT)
    _check("compliance_not_required", result["compliance_review_required"] is False, str(result))
    _check("factual_required", result["factual_verification_required"] is True, str(result))
    _check("proper_nouns_detected", len(result["factual_verification_detected_proper_nouns"]) >= 6, str(result))


if __name__ == "__main__":
    test_compliance_not_applicable_when_no_signals()
    test_compliance_applicable_with_amazon_link()
    test_compliance_applicable_with_purchase_cta()
    test_factual_verification_required_for_store_names()
    test_factual_verification_not_required_without_proper_nouns()
    test_generic_fashion_topic_words_not_flagged_as_proper_nouns()
    test_generic_katakana_verb_not_flagged()
    test_validate_blocks_when_compliance_flag_unmet()
    test_validate_blocks_when_factual_flag_unmet()
    test_validate_passes_when_all_results_filled()
    test_validate_passes_when_no_flags_required()
    test_run_pre_publish_checklist_integration_mens_osusume()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
