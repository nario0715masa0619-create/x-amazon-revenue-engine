"""GenerationSlots.hashtags/engagement_question（2026-09-08追加、
GOV-20260908-ENGAGEMENT-ELEMENTS-01）の検証スクリプト。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイルに合わせ、
`python scripts/test_engagement_elements.py`で直接実行できるplain assertベースの
検証スクリプトとする。

外部API呼び出しは一切行わない（Gate A/B実監査を伴う検証は
ops/reports/engagement_elements_investigation_2026-09-08.md側で実施済み）。
Gate A/thresholds/shipping decision・既存8テンプレートの本文組み立てロジックには
一切触れない（末尾への追加分岐のみを検証する）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from draft_generation_templates import GenerationSlots, render_draft

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


_BASE_KWARGS = dict(
    source_structure_type=["essay_like"],
    layer_primary="fashion",
    hook="テストのhook",
    benefit="テストのbenefit",
    age_angle="",
    concrete_items=["アイテムA", "アイテムB"],
    reusable_elements=[],
)


def test_no_hashtag_no_question_matches_existing_output() -> None:
    print("\n=== 検証1: hashtags/engagement_question未指定なら既存出力と完全一致すること（後方互換） ===")
    slots_without = GenerationSlots(**_BASE_KWARGS)
    slots_with_none_explicit = GenerationSlots(**_BASE_KWARGS, hashtags=None, engagement_question=None)
    draft_without = render_draft(slots_without)
    draft_with_none = render_draft(slots_with_none_explicit)
    _check("outputs_identical", draft_without == draft_with_none, repr(draft_without))
    _check("no_hash_symbol", "#" not in draft_without)


def test_hashtags_appended_to_essay_like() -> None:
    print("\n=== 検証2: hashtagsを指定するとessay_likeテンプレートの末尾に付与されること ===")
    slots = GenerationSlots(**_BASE_KWARGS, hashtags=["ファッション", "40代コーデ"])
    draft = render_draft(slots)
    _check("contains_hashtag_1", "#ファッション" in draft, draft)
    _check("contains_hashtag_2", "#40代コーデ" in draft, draft)
    _check("hashtags_at_end", draft.rstrip().endswith("#ファッション #40代コーデ"), draft)


def test_engagement_question_appended_to_essay_like() -> None:
    print("\n=== 検証3: engagement_questionを指定するとessay_likeテンプレートの末尾に付与されること ===")
    slots = GenerationSlots(**_BASE_KWARGS, engagement_question="みんなはどうしてる？")
    draft = render_draft(slots)
    _check("contains_question", "みんなはどうしてる？" in draft, draft)
    _check("question_at_end", draft.rstrip().endswith("みんなはどうしてる？"), draft)


def test_both_hashtags_and_question_appended_in_order() -> None:
    print("\n=== 検証4: hashtags・engagement_question両方指定時、ハッシュタグ→質問の順で末尾に付与されること ===")
    slots = GenerationSlots(
        **_BASE_KWARGS, hashtags=["ファッション"], engagement_question="どう思う？"
    )
    draft = render_draft(slots)
    hashtag_pos = draft.find("#ファッション")
    question_pos = draft.find("どう思う？")
    _check("both_present", hashtag_pos >= 0 and question_pos >= 0, draft)
    _check("hashtag_before_question", hashtag_pos < question_pos, draft)


def test_all_eight_templates_support_engagement_elements() -> None:
    print("\n=== 検証5: 全8テンプレート（essay_like以外の7種含む）がengagement要素の付与に対応すること ===")
    template_specific_kwargs = {
        "listicle": dict(source_structure_type=["listicle"]),
        "comparison": dict(
            source_structure_type=["comparison"],
            layer_primary="gadget",
            usage_scenes=["通勤"],
            comparison_axes=["音質", "装着感"],
            category_head_nouns=["イヤホン"],
            concrete_items=["A", "B", "C"],
        ),
        "priority_reversal": dict(
            source_structure_type=["priority_reversal"],
            comparison_axes=["見た目", "実用性"],
        ),
        "experience_review": dict(source_structure_type=["experience_review"]),
        "how_to": dict(source_structure_type=["how_to"]),
        "single_claim": dict(source_structure_type=["single_claim"]),
        "essay_like": dict(source_structure_type=["essay_like"]),
    }
    for label, overrides in template_specific_kwargs.items():
        kwargs = dict(_BASE_KWARGS)
        kwargs.update(overrides)
        slots = GenerationSlots(**kwargs, hashtags=["テスト"], engagement_question="質問？")
        draft = render_draft(slots)
        _check(f"{label}_contains_hashtag", "#テスト" in draft, draft)
        _check(f"{label}_contains_question", "質問？" in draft, draft)


if __name__ == "__main__":
    test_no_hashtag_no_question_matches_existing_output()
    test_hashtags_appended_to_essay_like()
    test_engagement_question_appended_to_essay_like()
    test_both_hashtags_and_question_appended_in_order()
    test_all_eight_templates_support_engagement_elements()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
