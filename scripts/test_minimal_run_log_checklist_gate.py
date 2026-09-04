"""minimal_run_log.build_minimal_run_log()に組み込んだpre_publish_checklistの
ブロック機構（2026-09-04追加）の検証スクリプト。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイルに合わせ、
`python scripts/test_minimal_run_log_checklist_gate.py`で直接実行できるplain assert
ベースの検証スクリプトとする。

外部API呼び出しは一切行わない。Gate A/thresholds/shipping decisionには一切触れない
（本テストはminimal_run_log記録時の後段チェックのみを対象とする）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from minimal_run_log import build_minimal_run_log
from pre_publish_checklist import PrePublishChecklistError, run_pre_publish_checklist

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


def test_blocked_when_factual_verification_result_missing() -> None:
    print("\n=== 検証1: factual_verification_required=Trueなのにresult未記入だとbuild_minimal_run_log()がブロックされること ===")
    checklist = run_pre_publish_checklist(MENS_OSUSUME_DRAFT)
    _check("checklist_flags_factual", checklist["factual_verification_required"] is True, str(checklist))
    try:
        build_minimal_run_log(
            run_id="test-run-blocked",
            source_post_id="1920279945374245275",
            target_layer="fashion",
            pre_publish_checklist=checklist,
            human_selected_top="dummy-candidate",
        )
        _check("raised", False, "ブロックされずに記録できてしまった")
    except PrePublishChecklistError:
        _check("raised", True)


def test_succeeds_when_results_filled() -> None:
    print("\n=== 検証2: 結果が記入済みならbuild_minimal_run_log()が正常に完了すること ===")
    checklist = run_pre_publish_checklist(MENS_OSUSUME_DRAFT)
    log = build_minimal_run_log(
        run_id="test-run-ok",
        source_post_id="1920279945374245275",
        target_layer="fashion",
        pre_publish_checklist=checklist,
        human_selected_top="dummy-candidate",
        compliance_review_result="対象外と判定（Amazon言及・CTA・リンクなし）",
        factual_verification_result="7店舗すべて営業確認済み（2026-09-04 web検索）",
    )
    _check("factual_required_recorded", log.factual_verification_required is True)
    _check(
        "factual_result_recorded",
        log.factual_verification_result == "7店舗すべて営業確認済み（2026-09-04 web検索）",
        str(log.factual_verification_result),
    )
    _check("compliance_not_required_recorded", log.compliance_review_required is False)
    _check(
        "compliance_result_recorded",
        log.compliance_review_result == "対象外と判定（Amazon言及・CTA・リンクなし）",
    )


def test_denim_draft_no_flags_no_results_needed() -> None:
    print("\n=== 検証3: 固有名詞を含まない下書き（デニム-定番-服__定番実データ）はresult未記入でもブロックされないこと ===")
    denim_draft = (
        "結局よく着ているのは、昔から好きな定番の服ばかり。Tシャツ、シャツ、デニム、軍パン、ローファー。\n"
        "定番と新しさのバランスを保つ姿勢。\n"
        "40代の服選びは、これくらいのバランスがちょうどいい"
    )
    checklist = run_pre_publish_checklist(denim_draft)
    _check("no_flags", not checklist["compliance_review_required"] and not checklist["factual_verification_required"])
    try:
        log = build_minimal_run_log(
            run_id="test-run-denim",
            source_post_id="2088777767747735983",
            target_layer="fashion",
            pre_publish_checklist=checklist,
            human_selected_top="dummy-candidate",
        )
        _check("no_exception", True)
        _check("fields_recorded_as_false", log.compliance_review_required is False and log.factual_verification_required is False)
    except PrePublishChecklistError as e:
        _check("no_exception", False, str(e))


if __name__ == "__main__":
    test_blocked_when_factual_verification_result_missing()
    test_succeeds_when_results_filled()
    test_denim_draft_no_flags_no_results_needed()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
