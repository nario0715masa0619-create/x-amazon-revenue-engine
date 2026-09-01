"""Claude Code（生成）× 外部AI（監査）の二段構成パイプライン。

段階A/B（候補取得・選定）は既存の scripts/x_api_phase1_collect.py /
scripts/x_api_phase2_classify.py の出力（pre_teacher_candidate.json）をそのまま使う。

このモジュールが持つ責務:
    - source_structure_type の分類（段階B補助。ヒューリスティック、決定的）
    - 外部監査を呼ぶ前のローカル一次バリデーション（無料・高速なフィルタ。
      diary-like検出・具体名詞数チェック・CTA混入チェック・記事紹介語チェック・
      layer_primary別の必須信号チェック）
    - 外部AI監査の required_fixes を次の生成制約へ変換する
      （map_audit_fixes_to_generation_constraints）
    - 外部AI監査の呼び出しとpass/revise/reject分岐・再生成ループの管理（段階D/E）
    - 監査ログの保存（段階F）

初稿・再稿の"組み立て"は scripts/draft_generation_templates.py の
source_structure_type別テンプレートが担当する（自由作文の禁止。骨格はコードが
強制し、Claude Codeはスロットの中身のみを埋める）。

詳細方針: ops/reports/external_audit_policy_2026-08-18.md、
         ops/reports/generation_spec_refactor_2026-08-18.md
"""

from __future__ import annotations

import difflib
import json
import re
import statistics
import sys
import unicodedata
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from external_audit_client import AuditClient
from external_audit_schema import (
    AuditRequest,
    AuditResult,
    Candidate,
    NormalizedAuditFix,
    FixNormalizationResult,
    HardGateResult,
    QualityScoreResult,
    TEACHER_FLOOR,
    BORDERLINE_LOW,
    BORDERLINE_HIGH,
    SHIP_THRESHOLD,
    STRONG_SHIP_THRESHOLD,
    classify_quality_band,
    classify_quality_band_from_score,
    normalize_gate_b_score_breakdown,
    calculate_weighted_gate_b_score,
    detect_gate_b_consistency_issues,
    build_gate_b_normalized_result,
    QUALITY_SCORE_WEIGHTS,
    ComparativeQualityScoreResult,
    FirstLineHookEvaluationResult,
    OpeningSpanHookEvaluationResult,
    MetaGateDivergenceResult,
    validate_meta_gate_divergence_result,
    DIVERGENCE_TYPES,
    DIVERGENCE_SEVERITIES,
    RECOMMENDED_REVIEW_MODES,
)
from first_line_hook_evaluator import (
    evaluation_result_to_dict,
    determine_structure_hook_alignment,
    evaluation_result_v2_to_dict,
    determine_hook_v1_vs_hook_v2_alignment,
    compute_hook_v1_axis_consensus,
)
from minimal_run_log import (
    build_minimal_run_log,
    minimal_run_log_to_dict,
    save_minimal_run_log,
)
from posted_theme_registry import (
    check_posted_theme_guard,
    load_posted_theme_registry,
)
from topic_dedupe import build_theme_profile
from topic_group_state import (
    TopicGroupState,
    get_or_create_topic_group,
    record_mainline_attempt,
    record_publication,
    update_performance_band,
    passes_mainline_candidate_filter,
    load_topic_group_state_store,
    save_topic_group_state_store,
)
from enrichment_record import (
    build_enrichment_record,
    build_failed_enrichment_record,
    enrichment_record_to_dict,
    save_enrichment_record,
)
from draft_generation_templates import GenerationSlots, GenerationSlotsError
from concrete_item_enrichment import (
    has_look_axis,
    has_practical_axis,
    axis_short_phrase,
    soft_contains_phrase,
    soft_match_any_phrase,
    has_required_category_head_noun,
    extract_present_items,
    GADGET_CONCRETE_ITEM_KEYWORDS,
    INTERSECTION_CONCRETE_ITEM_KEYWORDS,
    FASHION_ALLOWED_ACCESSORY_CATEGORIES,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PHASE2_OUTPUT_DIR = _REPO_ROOT / "outputs" / "x_api_phase2"
_LOG_DIR = _REPO_ROOT / "ops" / "reports"

# --------------------------------------------------------------------------
# source_structure_type 分類（段階B補助）
# --------------------------------------------------------------------------
_LISTICLE_PATTERN = re.compile(r"(^|\n)\s*(・|[0-9０-９]+[.．)）])")
_URL_PATTERN = re.compile(r"https?://\S+")
# 「vs」はURL内（例: ...6EBvsiSzKV）に偶然出現し誤検出するため、単語境界を要求する
# （bareな部分文字列一致にしない。DECISION_KEYWORDS等での既知の教訓に合わせる）
_VS_PATTERN = re.compile(r"(?<![A-Za-z])[Vv][Ss](?![A-Za-z])")
_COMPARISON_KEYWORDS = ["比較", "結局どれ", "結局どの", "どちらが", "使い分け", "どっちが"]
# 「AよりBが大事/優先」型の対比（例:「おしゃれより疲れにくさも大事」）を単独で拾う。
# 「昔はA、今はB」型の明示的な過去/現在マーカーが無くても対比があれば十分とする。
_PRIORITY_REVERSAL_CONTRAST = ["より"]
_PRIORITY_REVERSAL_SHIFT = ["も大事", "を選ぶ", "を優先", "重視", "の方が", "を選ぶようになった"]
_PRIORITY_REVERSAL_PAST = ["だった", "昔は", "以前は", "たぶん30代", "若い頃は"]
_PRIORITY_REVERSAL_NOW = ["より", "も大事", "を選ぶようになった", "優先", "今は"]
_EXPERIENCE_REVIEW_KEYWORDS = ["実体験", "使ってみた", "比較してみた", "使い勝手", "レビュー", "買ってよかった"]
_HOW_TO_KEYWORDS = ["コツ", "にアリ", "方法", "やり方", "選び方", "解説"]
_NEWS_LIKE_KEYWORDS = ["逮捕", "発表しました", "調査によると", "ニュース", "報道", "容疑者"]
_THREAD_LIKE_KEYWORDS = ["🧵", "1/", "続く)", "（続く"]
_ESSAY_ENDING_PATTERN = re.compile(r"(になった|と思う|感じた|気がする)[。！]?\s*$")
# 2026-08-21追補: 【】記事見出し表記 + （URL or 〈媒体タグ〉）という、雑誌/まとめ記事の
# 見出しツイートによく見られる形式（teacher_reproduction_validation_2026-08-21のFashion先生）。
# この形式は勝ち要素が"how_toの説明"ではなく"見出し断定の勢い"にあるため、独立ラベルとして
# 分類する（draft_generation_templates.pyのrender_headline_assertion_fashion優先分岐に使う）。
_ARTICLE_TITLE_BRACKET_PATTERN = re.compile(r"【[^】]+】")
_ARTICLE_TITLE_TAG_PATTERN = re.compile(r"〈[^〉]+〉")


def classify_source_structure_type(text: str) -> list[str]:
    """元投稿の構造を分類する（複数ラベル可）。1つも該当しなければ essay_like。

    URLを除去したテキストに対して判定する（「vs」等の短い語がURL内の
    ランダム文字列に偶然一致するfalse positiveを防ぐため）。
    """
    labels: list[str] = []
    has_url = bool(_URL_PATTERN.search(text))
    text = _URL_PATTERN.sub("", text)

    if _ARTICLE_TITLE_BRACKET_PATTERN.search(text) and (has_url or _ARTICLE_TITLE_TAG_PATTERN.search(text)):
        labels.append("article_title_like")
    if _LISTICLE_PATTERN.search(text):
        labels.append("listicle")
    if any(kw in text for kw in _COMPARISON_KEYWORDS) or _VS_PATTERN.search(text):
        labels.append("comparison")
    contrast_shift = any(kw in text for kw in _PRIORITY_REVERSAL_CONTRAST) and any(
        kw in text for kw in _PRIORITY_REVERSAL_SHIFT
    )
    past_now_shift = any(kw in text for kw in _PRIORITY_REVERSAL_PAST) and any(
        kw in text for kw in _PRIORITY_REVERSAL_NOW
    )
    if contrast_shift or past_now_shift:
        labels.append("priority_reversal")
    if any(kw in text for kw in _EXPERIENCE_REVIEW_KEYWORDS):
        labels.append("experience_review")
    if any(kw in text for kw in _HOW_TO_KEYWORDS):
        labels.append("how_to")
    if any(kw in text for kw in _NEWS_LIKE_KEYWORDS):
        labels.append("news_like")
    if any(kw in text for kw in _THREAD_LIKE_KEYWORDS):
        labels.append("thread_like")
    if not labels and len(text.strip()) < 30 and "\n" not in text.strip():
        labels.append("single_claim")
    if not labels:
        labels.append("essay_like")

    return labels


# --------------------------------------------------------------------------
# ローカル一次構造チェック（外部監査呼び出し前のフィルタ。API費用節約が目的で、
# 外部監査の代わりにはしない。ここを通っても外部監査は必ず実施する）
# --------------------------------------------------------------------------
def local_structure_precheck(draft: str, source_structure_type: list[str]) -> list[str]:
    issues: list[str] = []
    draft_stripped = draft.strip()

    if "listicle" in source_structure_type and not _LISTICLE_PATTERN.search(draft):
        issues.append("listicle構造なのに箇条書き/列挙が生成文から消えている")

    is_single_paragraph = "\n" not in draft_stripped
    essay_ending = bool(_ESSAY_ENDING_PATTERN.search(draft_stripped))
    if "essay_like" not in source_structure_type and is_single_paragraph and essay_ending:
        issues.append("単一段落＋内省的な結び（『〜になった』等）で日記化している疑いがある")

    if "comparison" in source_structure_type and not any(
        kw in draft for kw in _COMPARISON_KEYWORDS + ["か", "より"]
    ):
        issues.append("comparison構造なのに比較軸・争点が生成文から読み取れない")

    return issues


# --------------------------------------------------------------------------
# 日記文禁止ルール（指示書7章）・CTA/記事紹介化禁止（指示書8章）・
# layer_primary別必須信号チェック（指示書6章）
# --------------------------------------------------------------------------
_CTA_KEYWORDS = ["フォロー", "プロフ", "チェックして", "リンクは", "詳しくは", "こちらから", "見てね", "保存して", "コメントで"]
_ARTICLE_INTRO_KEYWORDS = ["まとめました", "紹介されていた", "で紹介", "記事はこちら", "SNAP", "ライター", "くらべる"]
_FASHION_LAYER_SIGNAL_KEYWORDS = ["着映え", "小物", "垢抜け", "清潔感", "見た目", "コーデ", "似合う", "腕時計", "メガネ", "ベルト"]
_GADGET_LAYER_SIGNAL_KEYWORDS = ["比較", "使い分け", "実体験", "使ってみた", "選ぶ", "基準", "有線", "ワイヤレス", "骨伝導"]
# 2026-08-19: 「〜のような場面ほど、これが効く」等、具体化のつもりが記事紹介文体的な
# メタ解説として監査に読まれた説明調のつなぎ文（audit_criteria_adjustment_2026-08-19参照）。
# テンプレート側は廃止済みだが、自由記述の再生成で紛れ込むことがあるためローカルでも検出する。
_EXPLANATORY_BRIDGE_PATTERN = re.compile(
    r"(のような場面ほど|見ているのは.{0,20}の両方|という場面が増える|ということになる)"
)


def _axis_present_in_draft(axis: str, draft: str) -> bool:
    """comparison_axesの語は、生の名詞形かaxis_short_phrase変換後の短句のどちらかが
    生成文に含まれていれば「残っている」とみなす（テンプレートが短句化するため）。

    2026-08-21追補: 完全一致に加え、表記ゆれ耐性つき照合（soft_contains_phrase）も
    許容する（助詞挿入等の軽微な差でrejectしないため。
    ops/reports/teacher_reproduction_validation_2026-08-21.md参照）。
    """
    if axis in draft or axis_short_phrase(axis) in draft:
        return True
    matched_raw, _ = soft_contains_phrase(draft, axis)
    matched_short, _ = soft_contains_phrase(draft, axis_short_phrase(axis))
    return matched_raw or matched_short


def has_sufficient_gadget_category_specificity(draft: str, slots: GenerationSlots) -> bool:
    """ブランド名・型番がなくても、カテゴリ名3個以上+比較軸2個以上+使用場面1個以上が
    揃っていれば「十分に具体的」とみなす（audit_criteria_adjustment_2026-08-19の方針）。
    """
    present_categories = sum(1 for item in slots.concrete_items if item in draft)
    present_axes = sum(1 for axis in slots.comparison_axes if _axis_present_in_draft(axis, draft))
    present_scenes = sum(1 for scene in slots.usage_scenes if scene in draft)
    return present_categories >= 3 and present_axes >= 2 and present_scenes >= 1


def has_compact_intersection_listicle_structure(draft: str, slots: GenerationSlots) -> bool:
    """優先順位逆転(or両立課題) + 列挙(3個以上) + 見た目側/実用側の両方の比較軸、を
    コンパクトに満たしているか（説明文の長さは問わない）。"""
    has_listicle_marker = bool(_LISTICLE_PATTERN.search(draft))
    present_items = sum(1 for item in slots.concrete_items if item in draft)
    axes_in_draft = [axis for axis in slots.comparison_axes if _axis_present_in_draft(axis, draft)]
    dual_axis = has_look_axis(axes_in_draft) and has_practical_axis(axes_in_draft)
    return has_listicle_marker and present_items >= 3 and dual_axis


def has_excessive_meta_explanation(draft: str) -> bool:
    """『〜のような場面ほど、これが効く』等の説明調つなぎ文が含まれているか
    （記事紹介文体的なメタ解説として監査に読まれやすいため、intersectionでは避ける）。"""
    return bool(_EXPLANATORY_BRIDGE_PATTERN.search(draft))


# --------------------------------------------------------------------------
# Gadget minimal/rich 二段スロット（2026-08-21 production_pipeline_patch追加）
#
# 背景: 先生原文にusage_scenes/comparison_axesの記述が無い場合、GenerationSlotsの
# rich基準（comparison_axes>=2・usage_scenes>=1）を満たすには捏造が必要になり、
# GenerationSlotsErrorで候補が全滅していた（production_selection_fashion_gadget_
# 2026-08-21.mdで実際に確認）。原文にある情報だけで再現できる最小モード
# （gadget_minimal）を切り分ける。
# --------------------------------------------------------------------------
def can_build_gadget_rich_slots(
    comparison_axes: list[str], usage_scenes: list[str], concrete_items: list[str], category_head_nouns: list[str]
) -> bool:
    return (
        len(category_head_nouns) >= 1
        and len(comparison_axes) >= 2
        and len(usage_scenes) >= 1
        and len(concrete_items) >= 3
    )


def can_build_gadget_minimal_slots(comparison_endpoints: list[str], category_head_nouns: list[str]) -> bool:
    return len(category_head_nouns) >= 1 and len(comparison_endpoints) >= 1


def build_generation_slots_for_gadget(
    *,
    source_structure_type: list[str],
    hook: str,
    benefit: str,
    age_angle: str,
    concrete_items: list[str],
    reusable_elements: list[str],
    category_head_nouns: list[str],
    comparison_targets: list[str] | None = None,
    comparison_axis: str | None = None,
    comparison_axes: list[str] | None = None,
    usage_scenes: list[str] | None = None,
    conclusion_or_choice: str | None = None,
) -> GenerationSlots:
    """先生原文の情報量に応じて gadget_rich / gadget_minimal を自動選択してGenerationSlotsを組む。

    情報不足をusage_scenes/comparison_axesの捏造で埋めることはしない。richの条件を
    満たさなければminimalを試し、minimalの条件（category_head_nouns>=1・比較両端>=1）も
    満たさなければGenerationSlotsErrorを送出する（=候補として処理不能。原文が薄すぎる）。
    """
    comparison_axes = comparison_axes or []
    usage_scenes = usage_scenes or []
    endpoints = comparison_targets or concrete_items

    if can_build_gadget_rich_slots(comparison_axes, usage_scenes, concrete_items, category_head_nouns):
        mode = "gadget_rich"
    elif can_build_gadget_minimal_slots(endpoints, category_head_nouns):
        mode = "gadget_minimal"
    else:
        raise GenerationSlotsError(
            "gadget候補がminimal基準（category_head_nouns>=1・比較両端>=1）すら満たせません。"
            "原文の情報が薄すぎるため、この候補は処理できません（manual_reviewへ戻してください）。"
        )

    return GenerationSlots(
        source_structure_type=source_structure_type,
        layer_primary="gadget",
        slot_mode=mode,
        hook=hook,
        benefit=benefit,
        age_angle=age_angle,
        concrete_items=concrete_items,
        reusable_elements=reusable_elements,
        category_head_nouns=category_head_nouns,
        comparison_targets=comparison_targets,
        comparison_axis=comparison_axis,
        comparison_axes=comparison_axes,
        usage_scenes=usage_scenes,
        conclusion_or_choice=conclusion_or_choice,
    )


_EXPERIENCE_OR_STANCE_KEYWORDS = ["実体験", "使ってみた", "比較してみた", "本気で", "使い勝手", "選んでいる", "使い分けている"]
_QUESTION_OR_CONCLUSION_KEYWORDS = ["結局どれ", "結局どの", "どちらが", "どっちが"]


def local_gadget_minimal_precheck(draft: str, slots: GenerationSlots) -> list[str]:
    """gadget_minimalモード専用のローカル事前検証。

    minimalでは usage_scenes/comparison_axes を要求しない代わりに、
    以下だけは必須のまま維持する:
    - category_head_nouns（上位概念語）の保持（既存のlocal_pre_validateで別途チェック済み）
    - 比較両端（comparison_targets/concrete_items）の保持
    - 実体験アンカー or 比較姿勢の明示
    - 問いフレーム or 結論フレームのどちらか
    """
    issues: list[str] = []
    if not (slots.layer_primary == "gadget" and slots.slot_mode == "gadget_minimal"):
        return issues

    draft_stripped = draft.strip()

    endpoints = slots.comparison_targets or slots.concrete_items
    present_endpoints = sum(1 for e in endpoints if soft_contains_phrase(draft_stripped, e)[0])
    if present_endpoints < 1:
        issues.append("gadget_minimalなのに比較両端（comparison_targets/concrete_items）が生成文に1つも残っていない")

    has_stance = any(kw in draft_stripped for kw in _EXPERIENCE_OR_STANCE_KEYWORDS)
    if not has_stance:
        issues.append("gadget_minimalなのに実体験アンカーまたは比較姿勢の明示が見当たらない")

    has_question_or_conclusion = (
        any(kw in draft_stripped for kw in _QUESTION_OR_CONCLUSION_KEYWORDS)
        or bool(slots.conclusion_or_choice and soft_contains_phrase(draft_stripped, slots.conclusion_or_choice)[0])
    )
    if not has_question_or_conclusion:
        issues.append("gadget_minimalなのに問いフレーム（結局どれ等）または結論フレームのどちらも見当たらない")

    return issues


# 2026-08-21追補: how_toの「悩み→解決軸」テンプレートを見出し断定型の先生原文に
# 当てはめると、原文にはなかった"悩みの説明"というワンクッションが挟まり、断定の勢いと
# 感情トリガーが薄まることがteacher reproduction検証で判明した
# （fashion-repro-Bがこのパターンでrevise。ops/reports/teacher_reproduction_validation_2026-08-21.md）。
_PROBLEM_EXPOSITION_PATTERN = re.compile(
    r"(のに.{0,15}(感じる|気がする)|と感じる日がある|というときがある|ということがある|なのに.{0,10}(しない|できない))"
)


def local_fashion_headline_precheck(draft: str, slots: GenerationSlots) -> list[str]:
    """fashion + article_title_like（見出し断定型）専用のローカル事前検証。

    - 冒頭（最初の一文）に具体起点（headline_anchor）があるか
    - 解決軸（key_difference_claim/judgment_axis）が明示されているか
    - 悩みを長く説明する前置き（problem exposition）が入っていないか
    """
    issues: list[str] = []
    if not (slots.layer_primary == "fashion" and "article_title_like" in slots.source_structure_type):
        return issues

    draft_stripped = draft.strip()
    first_sentence = draft_stripped.split("。")[0] if "。" in draft_stripped else draft_stripped[:20]

    anchor = slots.headline_anchor or (slots.concrete_items[0] if slots.concrete_items else None)
    if anchor and not soft_contains_phrase(first_sentence, anchor)[0]:
        issues.append("headline_assertion想定なのに、冒頭一文に具体起点（headline_anchor）が見当たらない")

    axis = slots.key_difference_claim or slots.judgment_axis
    if axis and not soft_contains_phrase(draft_stripped, axis)[0]:
        issues.append("headline_assertion想定なのに、解決軸（key_difference_claim/judgment_axis）が生成文にない")

    if _PROBLEM_EXPOSITION_PATTERN.search(draft_stripped):
        issues.append(
            "headline_assertion想定なのに悩みを説明する前置きが入っている"
            "（overexplanation_risk上昇の疑い。見出し断定の勢いを優先し、悩み説明を挟まないこと）"
        )

    # 2026-08-21 production_pipeline_patch追補: 具体アクセサリカテゴリ語の数チェック。
    # fail（reject）ではなくwarning（監査APIには送るが、量の適正さを可視化する）として扱う。
    if slots.accessory_categories:
        present_categories = sum(1 for c in slots.accessory_categories if soft_contains_phrase(draft_stripped, c)[0])
        if present_categories < 2:
            issues.append(f"[warning] 具体アクセサリカテゴリが2語未満（現在{present_categories}語）")
        elif present_categories > 4:
            issues.append(f"[warning] 具体アクセサリカテゴリが4語を超えている（現在{present_categories}語、過剰列挙の疑い）")

    return issues


def is_diary_like_draft(draft: str, source_structure_type: list[str], concrete_items: list[str]) -> bool:
    """複数条件に該当したらdiary-likeとみなす（指示書7章）。

    単一条件だけでは弾かない（例: 単一段落でも具体物が十分あれば許容しうる）。
    2条件以上の複合でのみtrueを返す。
    """
    draft_stripped = draft.strip()
    conditions_met = 0

    if "\n" not in draft_stripped:
        conditions_met += 1

    present_items = sum(1 for item in concrete_items if soft_contains_phrase(draft_stripped, item)[0])
    if present_items < 2:
        conditions_met += 1

    if _ESSAY_ENDING_PATTERN.search(draft_stripped):
        conditions_met += 1

    if "listicle" in source_structure_type and not _LISTICLE_PATTERN.search(draft):
        conditions_met += 1

    if "comparison" in source_structure_type and not any(kw in draft for kw in _COMPARISON_KEYWORDS):
        conditions_met += 1

    return conditions_met >= 2


def local_pre_validate(draft: str, slots: GenerationSlots) -> list[str]:
    """初稿を外部AI監査へ送る前のローカル静的チェック（指示書6章、全項目）。

    ここで弾けるものは外部監査APIを消費せずに弾く
    （「監査APIを初歩ミスの検出器にしない」という指示書の方針）。
    """
    issues: list[str] = []
    draft_stripped = draft.strip()

    # 1. 文字数が極端に短すぎないか
    if len(draft_stripped) < 15:
        issues.append("文字数が極端に短すぎる（15文字未満）")

    # 2〜4・6: diary-like（単一段落独白・具体名詞不足・構造未達・内省的な結び）
    if is_diary_like_draft(draft, slots.source_structure_type, slots.concrete_items):
        issues.append(
            "diary-likeと判定（単一段落/具体物不足/内省的な結び/構造未達のうち2つ以上に該当）"
        )
    issues.extend(local_structure_precheck(draft, slots.source_structure_type))

    # 3. 具体名詞（concrete_items）が2個以上、実際に生成文に残っているか
    # 2026-08-18追補: gadget/intersectionは最低3個・比較軸2個・使用場面1個を要求する
    # （監査ログでこの2層の「具体名詞不足」指摘が支配的だったため。
    #  ops/reports/generation_spec_refactor_2026-08-18.md参照）
    # 2026-08-21追補: gadget_minimalモード（usage_scenes/comparison_axesが原文に無い先生）は
    # concrete_items最低1個（比較両端）まで緩める。rich基準で不必要に落とさないため。
    is_gadget_minimal = slots.layer_primary == "gadget" and slots.slot_mode == "gadget_minimal"
    present_items = sum(1 for item in slots.concrete_items if soft_contains_phrase(draft_stripped, item)[0])
    if is_gadget_minimal:
        min_items_required = 1
    else:
        min_items_required = 3 if slots.layer_primary in ("gadget", "intersection") else 2
    if present_items < min_items_required:
        issues.append(
            f"concrete_itemsのうち生成文に残っているのは{present_items}個"
            f"（{slots.layer_primary}{'(gadget_minimal)' if is_gadget_minimal else ''}は"
            f"{min_items_required}個以上必須）"
        )

    if slots.layer_primary in ("gadget", "intersection") and not is_gadget_minimal:
        present_axes = sum(1 for axis in slots.comparison_axes if _axis_present_in_draft(axis, draft_stripped))
        if present_axes < 2:
            issues.append(f"comparison_axesのうち生成文に残っているのは{present_axes}個（2個以上必須）")

        present_scenes = sum(1 for scene in slots.usage_scenes if soft_contains_phrase(draft_stripped, scene)[0])
        if present_scenes < 1:
            issues.append("usage_scenesが生成文中に1個も残っていない")
    elif is_gadget_minimal:
        # rich基準（比較軸2個以上・使用場面1個以上）では落とさない。
        # あれば使うが、無くてもgadget_minimalとしては許容する（指示書の方針どおり）。
        issues.extend(local_gadget_minimal_precheck(draft, slots))

    # 2026-08-21追補: gadgetは「上位概念語（例: イヤホン）」が型/方式名の羅列に
    # 埋もれて消えていないかを必須チェックする（teacher_reproduction_validation_2026-08-21で
    # verdict=passでも起きうる部分的な名詞欠落として判明した問題への対策）。
    if slots.layer_primary == "gadget" and slots.category_head_nouns:
        if not has_required_category_head_noun(draft_stripped, slots.category_head_nouns):
            issues.append(
                "category_head_nouns（上位概念語）が生成文から欠落している。"
                "型/方式名（有線・骨伝導等）だけで押し切らず、上位概念語を最低1つ残すこと"
            )

    # 2026-08-21 gadget_minimal_patch追補: age_angleが生成文から消失していないかを
    # 必須チェックする（render_comparison()がage_angleを使っていなかったことによる
    # reject実例。production_selection_gadget_only_2026-08-21.md参照）。
    if slots.layer_primary == "gadget" and "comparison" in slots.source_structure_type and slots.age_angle:
        if not soft_contains_phrase(draft_stripped, slots.age_angle)[0]:
            issues.append(
                f"age_angle（{slots.age_angle}）が生成文から消失している。"
                "40代視点は比較の問いや結論に短く添えて必ず残すこと"
            )

    if slots.layer_primary == "intersection":
        axes_in_draft = [axis for axis in slots.comparison_axes if _axis_present_in_draft(axis, draft_stripped)]
        if not (has_look_axis(axes_in_draft) and has_practical_axis(axes_in_draft)):
            issues.append("intersectionだが見た目側・実用側どちらかの比較軸が生成文から欠落している")
        if has_excessive_meta_explanation(draft):
            issues.append("説明調のつなぎ文（『〜のような場面ほど』等）が残っている。列挙+短い締めへ戻すこと")

    # 具体名詞密度: 120文字あたりconcrete_items最低2個の目安（共通の下限チェック）
    density_expected = max(2, round(len(draft_stripped) / 120 * 2))
    if present_items < min(density_expected, min_items_required):
        issues.append("文の長さに対して具体名詞の密度が低い（抽象語に置き換わっている可能性）")

    # 5. CTAが勝手に入っていないか
    if any(kw in draft for kw in _CTA_KEYWORDS):
        issues.append("CTAらしき表現が混入している（明示指示がない限りCTAは付けない）")

    # 8章: 記事紹介化の禁止
    if any(kw in draft for kw in _ARTICLE_INTRO_KEYWORDS):
        issues.append("記事紹介・媒体名/記名的な語調が残っている")

    # 7. layer_primaryに必要な信号が残っているか
    has_fashion_signal = any(kw in draft for kw in _FASHION_LAYER_SIGNAL_KEYWORDS)
    has_gadget_signal = any(kw in draft for kw in _GADGET_LAYER_SIGNAL_KEYWORDS)
    if slots.layer_primary == "fashion" and not has_fashion_signal:
        issues.append("layer_primary=fashionだが見え方/小物差等のfashion信号が読み取れない")
    if slots.layer_primary == "gadget" and not has_gadget_signal:
        issues.append("layer_primary=gadgetだが比較軸/実体験等のgadget信号が読み取れない")
    if slots.layer_primary == "intersection" and not (has_fashion_signal or has_gadget_signal):
        issues.append("layer_primary=intersectionだが見た目/実用いずれの信号も読み取れない")

    issues.extend(local_fashion_headline_precheck(draft, slots))

    return issues


def has_blocking_local_issues(issues: list[str]) -> bool:
    """local_pre_validate()等が返すissuesのうち、"[warning]"接頭辞の無いものが
    1つでもあればTrue（=外部監査に送らずreject）。[warning]は送信をブロックしない。"""
    return any(not issue.startswith("[warning]") for issue in issues)


# --------------------------------------------------------------------------
# 監査ログ→生成制約への変換（指示書9章）
# --------------------------------------------------------------------------
_FIX_KEYWORD_TO_CONSTRAINT_COMMON: list[tuple[list[str], str]] = [
    (["構造", "保持", "維持"], "must_keep_structure"),
    (["列挙", "箇条書き"], "force_listicle_items"),
    (["内省", "独白", "感想", "日記"], "forbid_diary_ending"),
    (["40代", "視点"], "strengthen_age_angle"),
    (["理由", "根拠", "主張"], "add_reasoning"),
    (["結果", "効果", "明確"], "clarify_outcome"),
]

# 2026-08-19: gadgetは「製品名」要求をブランド捏造ではなくカテゴリ具体性強化へ翻訳する。
# intersectionは「記事紹介っぽい」指摘を、説明を増やす方向ではなく説明調つなぎ文の削除
# （列挙+短い締めへ戻す）へ翻訳する。layer_primaryごとに翻訳規則を分ける。
_FIX_KEYWORD_TO_CONSTRAINT_GADGET: list[tuple[list[str], str]] = [
    (["製品名", "型番", "ブランド", "製品カテゴリ", "アイテム"], "force_category_specificity"),
    (["具体", "名詞", "特徴", "例"], "force_category_specificity"),
    (["比較軸", "選び方", "使い分け", "争点", "基準"], "force_comparison_axes_min_2"),
    (["抽象", "一般論", "曖昧"], "force_usage_scene"),
    # 2026-08-21追補: 「上位概念語」「何の比較か不明」等の指摘は、型/方式名だけで
    # 押し切った圧縮が原因のことが多い（teacher_reproduction_validation_2026-08-21参照）。
    (["上位概念", "カテゴリ", "何の比較", "対象が不明", "総称"], "force_category_head_noun"),
    (["問い", "結局どれ", "結局どの", "消え"], "preserve_comparison_question"),
]

# 2026-08-21 gadget_minimal_patch追補: slot_mode="gadget_minimal"のとき、rich向けの
# 翻訳規則（force_category_specificity等、原文にない具体性の追加を促す）をそのまま
# 適用すると、原文にない比較軸・使用場面・ブランド名の捏造要求になってしまう
# （production_selection_gadget_only_2026-08-21.mdで実際に発生）。minimal専用の
# 翻訳規則は「足す」方向ではなく「骨格を締める」方向（問いの明確化・age_angleの
# 接続強化・上位概念語/endpointsの再整理）に限定する。
_FIX_KEYWORD_TO_CONSTRAINT_GADGET_MINIMAL: list[tuple[list[str], str]] = [
    (["40代", "視点", "年代"], "force_age_angle_retention"),
    (["使用場面", "シーン"], "do_not_invent_usage_scene"),
    (["比較軸", "具体的", "具体性", "スペック", "特徴", "種類", "ブランド", "型番"], "do_not_invent_missing_axes"),
    (["問い", "結局どれ", "結局どの", "曖昧", "明確にする", "散っている"], "tighten_comparison_question"),
    (["骨格", "構造", "維持", "薄い"], "preserve_sparse_comparison_structure"),
]

_FIX_KEYWORD_TO_CONSTRAINT_INTERSECTION: list[tuple[list[str], str]] = [
    (["具体", "名詞", "アイテム", "薄い", "製品カテゴリ"], "force_concrete_items_min_3"),
    (["記事", "紹介", "導入"], "remove_explanatory_bridge_sentence"),
    (["両立", "両方", "見た目と実用", "比較軸"], "force_dual_axis_terms"),
    (["日記", "独白"], "force_listicle_compact_mode"),
]

_FIX_KEYWORD_TO_CONSTRAINT_FASHION: list[tuple[list[str], str]] = [
    # 2026-08-21 production_pipeline_patch追補: 本番監査の「具体例が薄い」指摘は、
    # axis自体を長くする（例:「腕時計やメガネなどの小物」）と再度reviseになることが実測で
    # 判明した（production_selection_fashion_gadget_2026-08-21.md）。増やす先はaccessory_
    # categories（独立した列挙文）であり、concrete_items自体を増やすのではないため、
    # 制約名をincrease_fashion_concrete_categoriesに変更した。
    (["具体", "名詞", "アイテム", "特徴", "例"], "increase_fashion_concrete_categories"),
    (["記事", "紹介"], "forbid_article_intro_tone"),
    # 2026-08-21追補: 見出し断定型の勢い・感情トリガーが薄まった、という指摘
    # （teacher_reproduction_validation_2026-08-21のfashion-repro-B）への翻訳。
    # 「悩みの説明を増やす」方向ではなく「悩み説明を削り断定に戻す」方向へ翻訳する。
    (["リズム", "rhythm", "断定", "emotional_trigger", "感情"], "prefer_headline_assertion_template"),
]

_FIX_KEYWORD_TO_CONSTRAINT_BY_LAYER = {
    "gadget": _FIX_KEYWORD_TO_CONSTRAINT_GADGET,
    "intersection": _FIX_KEYWORD_TO_CONSTRAINT_INTERSECTION,
    "fashion": _FIX_KEYWORD_TO_CONSTRAINT_FASHION,
}


def map_audit_fixes_to_generation_constraints(
    required_fixes: list[str], layer_primary: str | None = None, slot_mode: str | None = None
) -> list[str]:
    """[legacy/非推奨] 外部AIのrequired_fixes（自然文）を、生成制約IDへ直接変換する。

    2026-08-21 audit_fix_normalization_layer追補: この関数はraw fix textを
    キーワード一致で直接constraintへ変換するため、「もっと具体的に」のような
    曖昧な指摘や「比較軸を増やして」のような指摘が、原文にないscene/axis/brand/specを
    足す方向の制約へ誤って変換されるリスクを構造的に持つ
    （production_selection_fashion_gadget_2026-08-21.md等で繰り返し観測）。

    新しいコードは normalize_audit_required_fixes() を使うこと。そちらは
    raw fix → FixIntent（意図） → FixSafety（安全性判定） → 安全な制約のみ、という
    正規化パイプラインを経由し、捏造要求を検出してブロックする。
    この関数は既存呼び出し元との後方互換のためだけに残している。
    """
    rules = list(_FIX_KEYWORD_TO_CONSTRAINT_COMMON)
    if layer_primary == "gadget" and slot_mode == "gadget_minimal":
        rules.extend(_FIX_KEYWORD_TO_CONSTRAINT_GADGET_MINIMAL)
    else:
        rules.extend(_FIX_KEYWORD_TO_CONSTRAINT_BY_LAYER.get(layer_primary or "", []))

    constraints: list[str] = []
    for fix in required_fixes:
        for keywords, constraint in rules:
            if any(kw in fix for kw in keywords) and constraint not in constraints:
                constraints.append(constraint)

    # 2026-08-21追補: fashionの具体カテゴリ追加は、断定リズムを壊さない方向とセットで
    # 常に適用する（片方だけ適用すると悩み説明の再混入リスクがあるため）。
    if "increase_fashion_concrete_categories" in constraints and "preserve_headline_rhythm_while_concretizing" not in constraints:
        constraints.append("preserve_headline_rhythm_while_concretizing")

    return constraints


# ============================================================================
# audit fix 正規化層（2026-08-21 audit_fix_normalization_layer追加）
#
# raw audit fix → FixIntent（意図） → FixSafety（安全性） → 安全な生成制約 or 破棄。
# 目的は監査を弱めることではなく、「監査要求を捏造禁止の運用ルールに沿って実行可能な
# 修正へ翻訳する」こと。詳細方針: ops/reports/audit_fix_normalization_layer_2026-08-21.md
# ============================================================================

# --------------------------------------------------------------------------
# 1. raw fix text → FixIntent 分類
#
# 優先順位付きキーワード表。より具体的・より危険（捏造リスクが高い）な意図を先に
# 判定する（例: 「ブランド名」は「具体的」より先にチェックする。先に「具体的」に
# 一致してしまうとadd_brand_or_model_detailを見逃すため）。最初に一致したintentを採用する。
# --------------------------------------------------------------------------
_FIX_INTENT_KEYWORD_PRIORITY: list[tuple[list[str], str]] = [
    # --- 最優先: 捏造リスクが明確なもの ---
    (["ブランド", "型番", "メーカー", "製品名"], "add_brand_or_model_detail"),
    (["使用場面", "シーン", "場面が"], "add_usage_scene"),
    (["比較軸を追加", "比較軸を増や", "軸を追加", "軸を増や", "スペック", "装着感", "音質", "バッテリー持ち"], "add_comparison_axis"),

    # --- 上位概念語・年代視点（sourceにあれば安全に再明示できる） ---
    (["上位概念", "何の比較か", "対象が不明", "総称"], "reinforce_category_head_noun"),
    (["40代", "年代", "世代"], "retain_age_angle"),

    # --- 比較両端・問い・結論のクラリファイ系（既存事実の再配置で対応可能） ---
    (["有線と骨伝導", "対象の違い", "比較両端", "差が伝わらない", "endpoints"], "reinforce_endpoints"),
    (["比較軸を明確", "比較の問い", "結局どれ", "結局どの", "比較の具体的なポイント", "比較の文脈"], "clarify_comparison_question"),
    (["結論", "着映えの差を明確", "効果を明確", "結果を明確", "何が違うのか"], "clarify_conclusion_frame"),

    # --- トーン系（新情報不要） ---
    (["記事", "紹介", "導入"], "reduce_article_intro"),
    (["日記", "独白", "内省"], "reduce_diary_tone"),
    (["構造", "保持", "維持"], "preserve_structure"),

    # --- 製品例・具体名詞系（sourceに未使用の実在語があれば安全） ---
    (["種類や特徴", "製品例", "アイテム例", "商品"], "add_product_specific_examples"),
    (["具体", "もっと", "詳しく", "薄い"], "increase_concreteness"),

    # --- 汎用の主張強化 ---
    (["文脈", "主張", "論点", "根拠", "散っている", "曖昧"], "tighten_claim_focus"),
]


# 「比較軸を追加」のような固定フレーズの完全一致だけでは、「比較軸をもっと追加してください」
# のような間に語が挟まる自然な言い回しの揺れを拾えない（テストで実際に検出）。
# 名詞＋動詞を分離したAND条件で判定する語だけ、ここに別枠で持つ。
_FIX_INTENT_AND_CONDITIONS: list[tuple[list[str], list[str], str]] = [
    (["比較軸", "軸"], ["追加", "増や", "足し", "もっと"], "add_comparison_axis"),
    (["使用場面", "シーン"], ["追加", "増や", "足し"], "add_usage_scene"),
]


def classify_fix_intent(raw_fix_text: str, slot_mode: str | None = None, layer_primary: str | None = None) -> str:
    """raw fix textをFIX_INTENTSのいずれかへ分類する（決定的、キーワード優先順位方式）。

    slot_mode/layer_primaryは現時点では分類そのものには使わない（意図の分類は
    レイヤー非依存であるべきため）が、将来の拡張のためシグネチャに残す。
    """
    # AND条件（名詞語＋動作語の組み合わせ）を先に見る。固定フレーズより語順の揺れに強い。
    for noun_kws, verb_kws, intent in _FIX_INTENT_AND_CONDITIONS:
        if any(n in raw_fix_text for n in noun_kws) and any(v in raw_fix_text for v in verb_kws):
            return intent

    for keywords, intent in _FIX_INTENT_KEYWORD_PRIORITY:
        if any(kw in raw_fix_text for kw in keywords):
            return intent
    return "other_unknown"


# --------------------------------------------------------------------------
# 2. FixIntent → FixSafety 安全性判定
# --------------------------------------------------------------------------
_ALWAYS_SAFE_BY_REPHRASING_INTENTS = {
    "preserve_structure",
    "reduce_article_intro",
    "reduce_diary_tone",
    "tighten_claim_focus",
}


def _source_has_unused_concrete_terms(candidate: Candidate, slots: GenerationSlots) -> bool:
    """source_full_textに、slots.concrete_itemsにまだ含まれていない辞書語（原文由来の
    具体語）が残っているか。あればincrease_concreteness/add_product_specific_examplesを
    safe_from_sourceとして扱える（＝原文の中に、まだ使っていない実在の材料がある）。"""
    if slots.layer_primary == "gadget":
        dict_ = GADGET_CONCRETE_ITEM_KEYWORDS
    elif slots.layer_primary == "intersection":
        dict_ = INTERSECTION_CONCRETE_ITEM_KEYWORDS
    else:
        dict_ = FASHION_ALLOWED_ACCESSORY_CATEGORIES
    present_in_source = extract_present_items(candidate.source_full_text, dict_)
    used_text = "、".join(slots.concrete_items)
    return any(not soft_contains_phrase(used_text, term)[0] for term in present_in_source)


def assess_fix_safety(fix_intent: str, candidate: Candidate, slots: GenerationSlots) -> str:
    """FixIntentの安全性を判定する。FIX_SAFETY_LEVELSのいずれかを返す。

    判断の軸は一貫して「原文（candidate.source_full_text）またはslotsに既にある
    情報だけで対応できるか」。できなければforbidden_requires_invention。
    どちらとも言い切れない場合はambiguous_needs_manual（自動適用しない）。
    """
    is_gadget_minimal = slots.layer_primary == "gadget" and slots.slot_mode == "gadget_minimal"

    if fix_intent in _ALWAYS_SAFE_BY_REPHRASING_INTENTS:
        return "safe_by_rephrasing"

    if fix_intent == "reinforce_category_head_noun":
        return "safe_from_source" if slots.category_head_nouns else "ambiguous_needs_manual"

    if fix_intent == "retain_age_angle":
        return "safe_from_source" if slots.age_angle else "ambiguous_needs_manual"

    if fix_intent == "reinforce_endpoints":
        endpoints = slots.comparison_targets or slots.concrete_items
        return "safe_from_source" if len(endpoints) >= 2 else "ambiguous_needs_manual"

    if fix_intent == "clarify_comparison_question":
        return "safe_by_rephrasing" if "comparison" in candidate.source_structure_type else "ambiguous_needs_manual"

    if fix_intent == "clarify_conclusion_frame":
        return "safe_by_rephrasing" if (slots.conclusion_or_choice or slots.benefit) else "ambiguous_needs_manual"

    if fix_intent == "add_brand_or_model_detail":
        # このプロジェクトはブランド名・型番の捏造を無条件で禁止する方針
        # （sourceに実在しても、それを判定する信頼できる手段が無いため常にforbiddenとして扱う）。
        return "forbidden_requires_invention"

    if fix_intent == "add_usage_scene":
        if is_gadget_minimal:
            return "safe_from_source" if slots.usage_scenes else "forbidden_requires_invention"
        return "safe_from_source" if slots.usage_scenes else "forbidden_requires_invention"

    if fix_intent == "add_comparison_axis":
        return "safe_from_source" if slots.comparison_axes else "forbidden_requires_invention"

    if fix_intent == "add_product_specific_examples":
        return "safe_from_source" if _source_has_unused_concrete_terms(candidate, slots) else "forbidden_requires_invention"

    if fix_intent == "increase_concreteness":
        if slots.layer_primary == "fashion":
            return "safe_by_rephrasing"  # 許可カテゴリ語（ブランド名ではない）の範囲で対応可能
        return "safe_from_source" if _source_has_unused_concrete_terms(candidate, slots) else "ambiguous_needs_manual"

    return "ambiguous_needs_manual"  # other_unknown等


# --------------------------------------------------------------------------
# 3. 安全なFixIntent → 生成制約への変換
# --------------------------------------------------------------------------
def convert_safe_fix_intent_to_constraints(fix_intent: str, candidate: Candidate, slots: GenerationSlots) -> list[str]:
    """safe判定されたFixIntentを、既存の生成制約ID（draft_generation_templates/
    render関数が解釈する語彙）へ変換する。forbidden/ambiguousには使わないこと。"""
    is_gadget_minimal = slots.layer_primary == "gadget" and slots.slot_mode == "gadget_minimal"

    mapping = {
        "preserve_structure": ["preserve_sparse_comparison_structure"] if is_gadget_minimal else ["must_keep_structure"],
        "reduce_article_intro": ["forbid_article_intro_tone"],
        "reduce_diary_tone": ["forbid_diary_ending"],
        "tighten_claim_focus": ["add_reasoning", "clarify_outcome"],
        "reinforce_category_head_noun": ["force_category_head_noun"],
        "retain_age_angle": ["force_age_angle_retention"],
        "reinforce_endpoints": ["preserve_sparse_comparison_structure"] if is_gadget_minimal else ["must_keep_structure"],
        "clarify_comparison_question": ["tighten_comparison_question", "preserve_comparison_question"],
        "clarify_conclusion_frame": ["clarify_outcome"],
        "add_usage_scene": ["force_usage_scene"],  # safeの場合＝既にsourceにscene有り、再明示するだけ
        "add_comparison_axis": ["force_comparison_axes_min_2"],  # 同上
        "add_product_specific_examples": ["force_category_specificity"],
        "increase_concreteness": (
            ["increase_fashion_concrete_categories", "preserve_headline_rhythm_while_concretizing"]
            if slots.layer_primary == "fashion"
            else ["force_category_specificity"]
        ),
    }
    return mapping.get(fix_intent, [])


# --------------------------------------------------------------------------
# 4. forbidden fix → 安全な代替intentへの変換テーブル
# --------------------------------------------------------------------------
_FORBIDDEN_TO_ALTERNATIVE_INTENTS: dict[str, list[str]] = {
    "add_usage_scene": ["preserve_structure", "reduce_article_intro", "tighten_claim_focus"],
    "add_comparison_axis": ["clarify_comparison_question", "reinforce_endpoints", "reinforce_category_head_noun"],
    "add_brand_or_model_detail": ["reinforce_category_head_noun"],
    "add_product_specific_examples": ["reinforce_category_head_noun", "tighten_claim_focus"],
}


def map_forbidden_fix_to_safe_alternative_intents(fix_intent: str) -> list[str]:
    """forbidden判定されたintentを、捏造なしで実行可能な代替intentのリストへ変換する。
    該当が無ければ空リスト（＝代替なし、破棄するしかない）。"""
    return list(_FORBIDDEN_TO_ALTERNATIVE_INTENTS.get(fix_intent, []))


def detect_forbidden_invention_request(raw_fix_text: str, candidate: Candidate, slots: GenerationSlots) -> bool:
    """raw fix textが、原文に無い情報の追加要求（forbidden_requires_invention）かどうかを
    1発で判定する薄いラッパー（classify_fix_intent + assess_fix_safetyの合成）。"""
    intent = classify_fix_intent(raw_fix_text, slots.slot_mode, slots.layer_primary)
    return assess_fix_safety(intent, candidate, slots) == "forbidden_requires_invention"


# --------------------------------------------------------------------------
# 5. required_fixes全体の正規化（メインエントリポイント）
# --------------------------------------------------------------------------
def normalize_raw_fixes(
    raw_fixes: list[str], candidate: Candidate, slots: GenerationSlots
) -> FixNormalizationResult:
    """raw fix文字列のリストを正規化し、捏造要求を含まない安全な制約セットを返す。

    2026-08-23追補: 従来 normalize_audit_required_fixes() 内に直接書かれていたコア処理を
    ここへ切り出した。audit_result.required_fixes（Gate A/legacy用）だけでなく、
    QualityScoreResult.improvement_suggestions（Gate B用）にも同じロジックを使い回すため
    （normalize_quality_improvement_suggestions()参照）。

    処理フロー（1件のraw fixごと）:
        1. classify_fix_intent()で意図を分類する
        2. assess_fix_safety()で安全性を判定する
        3. safe（from_source/by_rephrasing）なら convert_safe_fix_intent_to_constraints()
           でそのまま制約へ変換する
        4. forbidden（requires_invention）なら map_forbidden_fix_to_safe_alternative_intents()
           で代替intentを探し、代替が安全に変換できればそちらを適用する
           （raw fix自体はblockedのまま記録するが、代替経由でwas_applied=Trueになりうる）
        5. ambiguousは自動適用せず、blocked_reasonを残して保留する
    """
    normalized: list[NormalizedAuditFix] = []
    safe_constraints: list[str] = []
    forbidden_intents: list[str] = []

    for raw_fix in raw_fixes:
        intent = classify_fix_intent(raw_fix, slots.slot_mode, slots.layer_primary)
        safety = assess_fix_safety(intent, candidate, slots)
        entry = NormalizedAuditFix(raw_fix_text=raw_fix, intent=intent, safety=safety)

        if safety in ("safe_from_source", "safe_by_rephrasing"):
            constraints = convert_safe_fix_intent_to_constraints(intent, candidate, slots)
            entry.resulting_constraints = constraints
            entry.was_applied = bool(constraints)
            for c in constraints:
                if c not in safe_constraints:
                    safe_constraints.append(c)

        elif safety == "forbidden_requires_invention":
            forbidden_intents.append(intent)
            alternatives = map_forbidden_fix_to_safe_alternative_intents(intent)
            entry.alternative_intents = alternatives
            entry.was_blocked = True

            applied_alt_constraints: list[str] = []
            for alt_intent in alternatives:
                alt_safety = assess_fix_safety(alt_intent, candidate, slots)
                if alt_safety in ("safe_from_source", "safe_by_rephrasing"):
                    for c in convert_safe_fix_intent_to_constraints(alt_intent, candidate, slots):
                        if c not in applied_alt_constraints:
                            applied_alt_constraints.append(c)

            if applied_alt_constraints:
                entry.resulting_constraints = applied_alt_constraints
                entry.was_applied = True
                entry.blocked_reason = (
                    "forbidden_requires_invention（原文に無い情報の追加要求のため、raw fixそのものは不採用）。"
                    f"代替intent {alternatives} 経由で安全な制約へ変換した。"
                )
                for c in applied_alt_constraints:
                    if c not in safe_constraints:
                        safe_constraints.append(c)
            else:
                entry.blocked_reason = (
                    "forbidden_requires_invention（原文に無い情報の追加要求）。"
                    "安全な代替intentも見つからず、この指摘は破棄した。"
                )

        else:  # ambiguous_needs_manual
            entry.was_blocked = True
            entry.blocked_reason = "ambiguous_needs_manual（自動判定が危険なため、制約への自動反映を保留した）"

        normalized.append(entry)

    return FixNormalizationResult(
        normalized_fixes=normalized,
        safe_constraints=safe_constraints,
        blocked_count=sum(1 for n in normalized if n.was_blocked),
        forbidden_intents=forbidden_intents,
        all_forbidden=(len(normalized) > 0 and not safe_constraints),
    )


def normalize_audit_required_fixes(
    audit_result: AuditResult, candidate: Candidate, slots: GenerationSlots
) -> FixNormalizationResult:
    """[legacy互換] audit_result.required_fixesを正規化する。normalize_raw_fixes()の薄いラッパー。"""
    return normalize_raw_fixes(audit_result.required_fixes, candidate, slots)


def normalize_quality_improvement_suggestions(
    quality_result: "QualityScoreResult", candidate: Candidate, slots: GenerationSlots
) -> FixNormalizationResult:
    """Gate B（QualityScoreResult）のimprovement_suggestions（+weaknesses）を正規化する。

    2026-08-23追補: Gate Bは「もっと具体的に」「比較が弱い」等の改善提案をweaknesses/
    improvement_suggestionsとして返すが、これも従来のrequired_fixesと同様、原文にない
    scene/axis/brand/model/experience detailを足す方向に流れうる。normalize_raw_fixes()を
    weaknesses+improvement_suggestionsの結合リストに適用し、safeな改善intentのみを
    抽出する。forbidden判定されたものはブロックする（silent ignoreではなくログに残る）。
    """
    raw_fixes = list(quality_result.improvement_suggestions) + list(quality_result.weaknesses)
    return normalize_raw_fixes(raw_fixes, candidate, slots)


def is_safe_quality_improvement(safety: str) -> bool:
    """FixSafetyがsafe（from_source/by_rephrasing）かどうかを判定する薄いヘルパー。"""
    return safety in ("safe_from_source", "safe_by_rephrasing")


def should_retry_based_on_score_delta(previous_score: int, current_score: int) -> bool:
    """スコアが前回より改善していれば、もう1ラウンドの余地ありとみなす。

    改善していなければ（同点含む）打ち切る。「revise 2回だから自動破棄」ではなく、
    「score改善が止まったから打ち切る」という、指示書の新しい停止基準に対応する。
    """
    return current_score > previous_score


def build_fix_normalization_log(result: FixNormalizationResult, slot_mode: str | None, layer_primary: str | None) -> dict[str, Any]:
    """FixNormalizationResultをJSON保存用のdictへ変換する。"""
    return {
        "layer_primary": layer_primary,
        "slot_mode": slot_mode,
        "safe_constraints": result.safe_constraints,
        "blocked_count": result.blocked_count,
        "forbidden_intents": result.forbidden_intents,
        "all_forbidden": result.all_forbidden,
        "normalized_fixes": [asdict(n) for n in result.normalized_fixes],
    }


def detect_forbidden_intent_recurrence(
    previous_forbidden_intents: list[str], current_forbidden_intents: list[str]
) -> list[str]:
    """revise 1回目と2回目で共通して現れたforbidden intentを返す（構造衝突の検知）。"""
    return [i for i in current_forbidden_intents if i in previous_forbidden_intents]


def should_stop_revise_due_to_structural_conflict(
    previous_result: FixNormalizationResult, current_result: FixNormalizationResult
) -> tuple[bool, str | None]:
    """同じforbidden intentが2ラウンド連続で再発した場合、reviseを打ち切るべきかを判定する。

    「監査要求とsource密度の構造衝突」として明示し、無意味なrevise→revise
    ループを防ぐ（audit_fix_normalization_layer_2026-08-21.mdの狙い）。
    """
    recurring = detect_forbidden_intent_recurrence(previous_result.forbidden_intents, current_result.forbidden_intents)
    if recurring:
        return True, (
            f"同じforbidden intent（{recurring}）が2ラウンド連続で再発。"
            "監査要求とsource密度が構造的に衝突しているため、これ以上のreviseは打ち切る。"
        )
    return False, None


# --------------------------------------------------------------------------
# 段階D/E: 監査 + 再生成ループの管理
# --------------------------------------------------------------------------
def audit_one_draft(
    candidate: Candidate,
    draft_text: str,
    draft_version: int,
    audit_client: AuditClient,
    slot_mode: str | None = None,
) -> dict[str, Any]:
    local_issues = local_structure_precheck(draft_text, candidate.source_structure_type)
    request = AuditRequest(
        layer_primary=candidate.layer_primary,
        source_post_id=candidate.source_post_id,
        source_full_text=candidate.source_full_text,
        source_structure_type=candidate.source_structure_type,
        source_reusable_elements=candidate.reusable_elements,
        generated_draft=draft_text,
        slot_mode=slot_mode,
    )
    audit_result = audit_client.audit(request)
    return {
        "candidate_id": candidate.candidate_id,
        "source_post_id": candidate.source_post_id,
        "source_structure_type": candidate.source_structure_type,
        "draft_version": draft_version,
        "draft_text": draft_text,
        "local_precheck_issues": local_issues,
        "audit_verdict": audit_result.verdict,
        "audit": asdict(audit_result),
    }


def run_pipeline_for_candidate(
    candidate: Candidate,
    draft_texts: list[str],
    audit_client: AuditClient,
    max_revisions: int = 2,
    slot_mode: str | None = None,
) -> dict[str, Any]:
    """draft_texts は呼び出し側（対話内のClaude Code）が用意した初稿+再稿のリスト
    （最大 1 + max_revisions 件）。順に監査し、最初にpassしたものを採用する。
    全て pass しなければ候補自体を不採用（candidate_rejected）として返す。

    slot_modeを渡すと監査官へ明示的に伝わる（"gadget_minimal"のとき、
    rich相当の具体性を要求しないよう監査プロンプト側で扱う）。
    """
    log: list[dict[str, Any]] = []
    for i, draft in enumerate(draft_texts[: max_revisions + 1], start=1):
        entry = audit_one_draft(candidate, draft, i, audit_client, slot_mode=slot_mode)
        log.append(entry)
        if entry["audit_verdict"] == "pass":
            return {
                "candidate_id": candidate.candidate_id,
                "layer_primary": candidate.layer_primary,
                "status": "adopted",
                "final_text": draft,
                "final_draft_version": i,
                "log": log,
            }
    return {
        "candidate_id": candidate.candidate_id,
        "layer_primary": candidate.layer_primary,
        "status": "candidate_rejected",
        "final_text": None,
        "final_draft_version": None,
        "log": log,
    }


# --------------------------------------------------------------------------
# 段階D/E 二段化（2026-08-23 audit_gate_split_redesign）
#
# 旧フロー: local_pre_validate -> 1発監査(audit) -> required_fixes正規化 -> revise/discard
# 新フロー: local_pre_validate -> Gate A(hard_gate) -> [fail=discard] ->
#           Gate B(quality_score) -> score記録 -> [改善余地があればsafe改善で1回再生成] ->
#           再生成後もGate A再通過 -> 最高scoreを最終候補に残す
#
# 「reject=即破棄」「revise2回=破棄」という旧ルールを、
# 「Gate A fail=即破棄」「Gate A pass、score改善が止まった+閾値未満=破棄」へ置き換える。
# --------------------------------------------------------------------------
def evaluate_shipping_decision(score_overall: int) -> dict[str, Any]:
    """score_overallを、teacher floor / ship threshold / strong ship の二段基準で評価する。

    2026-08-23 two_threshold_redesign: 「先生投稿として成立しているか」（teacher floor）と
    「今日の投稿として採用できるか」（ship threshold）を分離して判定する。
    `teacher_level_but_not_ship`はfailureではなく、「先生水準は満たすが今日は出さない」
    という積極的なラベルであることに注意（詳細: ops/reports/two_threshold_redesign_2026-08-23.md）。
    """
    meets_teacher_floor = score_overall >= TEACHER_FLOOR
    meets_ship_threshold = score_overall >= SHIP_THRESHOLD
    meets_strong_ship_threshold = score_overall >= STRONG_SHIP_THRESHOLD
    band = classify_quality_band(score_overall)

    if not meets_teacher_floor:
        decision = "below_teacher_floor_no_ship"
    elif not meets_ship_threshold:
        decision = "teacher_level_but_not_ship_no_ship"
    elif meets_strong_ship_threshold:
        decision = "strong_ship_candidate"
    else:
        decision = "ship_candidate"

    return {
        "score_overall": score_overall,
        "quality_band": band,
        "meets_teacher_floor": meets_teacher_floor,
        "meets_ship_threshold": meets_ship_threshold,
        "meets_strong_ship_threshold": meets_strong_ship_threshold,
        "final_shipping_decision": decision,
    }


def evaluate_shipping_decision_from_normalized_gate_b(
    gate_a_result: dict[str, Any], quality_result: QualityScoreResult
) -> dict[str, Any]:
    """Gate A結果とGate Bの正規化済み結果から、最終出荷判定を一本化して算出する
    （2026-08-24 gate_b_score_consistency_patch）。

    最終判定に使うのは常にquality_result.normalized_score_overall（=QualityScoreResult.
    from_json()で既に正規化済みの値）であり、監査モデルのraw score_overallやraw
    quality_bandは一切参照しない。decision_sourceは常に"code_normalized_only"を返す。
    """
    if not gate_a_result.get("gate_a_pass"):
        return {
            "score_overall": None,
            "quality_band": None,
            "meets_teacher_floor": False,
            "meets_ship_threshold": False,
            "meets_strong_ship_threshold": False,
            "final_shipping_decision": "discarded_gate_a",
            "decision_source": "code_normalized_only",
        }
    decision = evaluate_shipping_decision(quality_result.normalized_score_overall)
    decision["decision_source"] = "code_normalized_only"
    return decision


def log_gate_b_consistency_comparison(
    candidate_id: str, draft_id: str, layer_primary: str | None, quality_result: QualityScoreResult
) -> dict[str, Any]:
    """モデル自己申告値とコード正規化値を並記したログエントリを作る
    （2026-08-24 gate_b_score_consistency_patch）。"""
    return {
        "candidate_id": candidate_id,
        "draft_id": draft_id,
        "layer_primary": layer_primary,
        "model_reported_score_overall": quality_result.model_reported_score_overall,
        "model_reported_quality_band": quality_result.model_reported_quality_band,
        "normalized_score_overall": quality_result.normalized_score_overall,
        "normalized_quality_band": quality_result.normalized_quality_band,
        "score_breakdown_raw": quality_result.score_breakdown_raw,
        "score_breakdown_normalized": quality_result.normalized_score_breakdown,
        "score_consistency_status": quality_result.score_consistency_status,
        "score_consistency_issues": quality_result.score_consistency_issues,
    }


def run_gate_a(
    candidate: Candidate, draft_text: str, audit_client: AuditClient, slot_mode: str | None = None
) -> dict[str, Any]:
    """Gate A（禁止違反ゲート）を実行する。audit_clientはaudit_hard_gate()を持つこと。"""
    local_issues = local_structure_precheck(draft_text, candidate.source_structure_type)
    request = AuditRequest(
        layer_primary=candidate.layer_primary,
        source_post_id=candidate.source_post_id,
        source_full_text=candidate.source_full_text,
        source_structure_type=candidate.source_structure_type,
        source_reusable_elements=candidate.reusable_elements,
        generated_draft=draft_text,
        slot_mode=slot_mode,
    )
    result: HardGateResult = audit_client.audit_hard_gate(request)
    return {
        "candidate_id": candidate.candidate_id,
        "source_post_id": candidate.source_post_id,
        "draft_text": draft_text,
        "local_precheck_issues": local_issues,
        "gate_a_pass": result.hard_gate_pass and not result.must_not_ship,
        "gate_a_result": asdict(result),
    }


def run_gate_b(
    candidate: Candidate, draft_text: str, audit_client: AuditClient, slot_mode: str | None = None
) -> dict[str, Any]:
    """Gate B（採用品質スコア）を実行する。Gate Aを通過した案にのみ呼ぶこと。"""
    request = AuditRequest(
        layer_primary=candidate.layer_primary,
        source_post_id=candidate.source_post_id,
        source_full_text=candidate.source_full_text,
        source_structure_type=candidate.source_structure_type,
        source_reusable_elements=candidate.reusable_elements,
        generated_draft=draft_text,
        slot_mode=slot_mode,
    )
    result: QualityScoreResult = audit_client.audit_quality_score(request)
    # 2026-08-24 gate_b_score_consistency_patch: gate_b_scoreは常にresult.normalized_score_overall
    # （=コード側で正規化・再計算した最終値）を使う。result.score_overallも同値だが、
    # 「rawモデル値をそのまま採用判定に使っていない」ことを明示するため、ここでは
    # normalized_score_overallを直接参照する。
    return {
        "candidate_id": candidate.candidate_id,
        "source_post_id": candidate.source_post_id,
        "draft_text": draft_text,
        "gate_b_score": result.normalized_score_overall,
        "gate_b_result": asdict(result),
        "gate_b_consistency": {
            "model_reported_score_overall": result.model_reported_score_overall,
            "model_reported_quality_band": result.model_reported_quality_band,
            "normalized_score_overall": result.normalized_score_overall,
            "normalized_quality_band": result.normalized_quality_band,
            "score_consistency_status": result.score_consistency_status,
            "score_consistency_issues": result.score_consistency_issues,
        },
    }


def run_two_gate_audit_for_draft(
    candidate: Candidate,
    draft_text: str,
    slots: GenerationSlots,
    audit_client: AuditClient,
    max_quality_revisions: int = 1,
) -> dict[str, Any]:
    """1件のdraftに対し、Gate A -> Gate B -> (safe改善があれば1回だけ再生成) を実行する。

    再生成そのもの（テンプレートの再描画）はこの関数の責務ではない（呼び出し側が
    draft_generation_templates.render_draft()等で新しいdraft_textを用意すること）。
    ここではGate A/Bの実行・正規化・スコア推移の記録・停止判定までを行う。
    戻り値の"final_status"は "discarded_gate_a" / "recorded" のいずれか
    （"recorded"はscoreを記録した状態。最終採用判断は複数候補を集めてから
    select_ship_candidate()で行う）。
    """
    gate_a = run_gate_a(candidate, draft_text, audit_client, slot_mode=slots.slot_mode)
    if not gate_a["gate_a_pass"]:
        return {
            "candidate_id": candidate.candidate_id,
            "final_status": "discarded_gate_a",
            "gate_a": gate_a,
            "gate_b": None,
            "normalized_improvements": None,
        }

    gate_b = run_gate_b(candidate, draft_text, audit_client, slot_mode=slots.slot_mode)
    quality_result = QualityScoreResult(**gate_b["gate_b_result"])
    normalized = normalize_quality_improvement_suggestions(quality_result, candidate, slots)
    # 2026-08-24 gate_b_score_consistency_patch: shipping_decisionは常にnormalized_score_overall
    # 経由（evaluate_shipping_decision_from_normalized_gate_b）で算出する。gate_b["gate_b_score"]
    # （旧: raw score_overallをそのまま見ていた）は参照しない。
    shipping_decision = evaluate_shipping_decision_from_normalized_gate_b(gate_a, quality_result)
    consistency_log = log_gate_b_consistency_comparison(
        candidate.candidate_id, candidate.candidate_id, candidate.layer_primary, quality_result
    )

    return {
        "candidate_id": candidate.candidate_id,
        "final_status": "recorded",
        "gate_a": gate_a,
        "gate_b": gate_b,
        "normalized_improvements": build_fix_normalization_log(normalized, slots.slot_mode, slots.layer_primary),
        # quality_bandはevaluate_shipping_decision_from_normalized_gate_b()内の
        # classify_quality_band()と同じ計算式で求めた値（監査モデルの自己申告ではなく
        # コード側の正規化値を正とする。audit_gate_split_redesign_2026-08-23.mdで、
        # 監査モデルの自己申告quality_bandが閾値定義と矛盾する例が実測されたため。
        # 2026-08-24 gate_b_score_consistency_patchで、score_overall自体もモデル自己申告と
        # 食い違うことが判明したため、band・scoreの双方をcode_normalized値に統一した）。
        "quality_band": shipping_decision["quality_band"],
        "shipping_decision": shipping_decision,
        "gate_b_consistency": consistency_log,
    }


def select_ship_candidate(
    scored_drafts: list[dict[str, Any]], ship_threshold: int = SHIP_THRESHOLD
) -> dict[str, Any] | None:
    """Gate Aを通過しscore記録済みのdraft群から、最終出荷候補を選ぶ。

    2026-08-23 two_threshold_redesign: 選定順は
      1. strong_ship_candidate（score >= STRONG_SHIP_THRESHOLD）があれば、その中の最高score
      2. 無ければ ship_candidate（ship_threshold以上）の中の最高score
      3. どちらも無ければNone（today-no-ship）
    `teacher_level_but_not_ship`（teacher floorは満たすがship_threshold未満）はログには残るが、
    ここでは採用しない（failureではなく「今日は出さない」という扱い）。

    scored_draftsは run_two_gate_audit_for_draft() の戻り値のリスト（final_status="recorded"のみ対象）。

    2026-08-24 gate_b_score_consistency_patch: d["gate_b"]["gate_b_score"]は
    run_gate_b()内でresult.normalized_score_overall（コード側正規化値）に統一済みのため、
    ここで改めてraw値を参照する心配はない（20番テスト: raw score_overallをshipping判定に
    使っていないことの確認に対応）。
    """
    candidates = [d for d in scored_drafts if d.get("final_status") == "recorded" and d.get("gate_b")]
    eligible = [d for d in candidates if d["gate_b"]["gate_b_score"] >= ship_threshold]
    if not eligible:
        return None
    strong = [d for d in eligible if d["gate_b"]["gate_b_score"] >= STRONG_SHIP_THRESHOLD]
    pool = strong if strong else eligible
    return max(pool, key=lambda d: d["gate_b"]["gate_b_score"])


# --------------------------------------------------------------------------
# quality_score 圧縮診断（2026-08-25 quality_score_compression_fix追加）
#
# 背景: 実測で、明らかに出来が異なるdraft同士がほぼ同一のscore_overall（74-79付近）に
# 集中し、strong_ship_candidateがほとんど出ない「圧縮」問題が繰り返し観測された
# （詳細: ops/reports/quality_score_scale_check_2026-08-25.md）。この関数は
# shipping判定には一切関与しない（診断・ログ専用）。同一batch（同時に生成・監査した
# draft群）内の複数QualityScoreResultを横断して、軸ごとの分散不足とoverallの
# レンジ幅を機械的に検出する。
# --------------------------------------------------------------------------
def detect_quality_score_compression(results: list[QualityScoreResult]) -> dict[str, Any]:
    """batch内のGate B quality_score結果群を横断し、共有軸/overallの圧縮（分散不足）を検出する。

    「圧縮」はdraft 1件だけでは定義できない（他と比べて初めて分かる性質）ため、
    この関数はbatch（複数draftのQualityScoreResultのリスト）単位で呼ぶこと。
    n<2の場合は判定不能（compression_flag=None）を返す。

    各軸の「分散不足」は、その軸のstdevを配点上限で正規化した値（0-1）で判定する:
    - <0.05: nearly_dead（実質同じ値しか返っていない）
    - <0.15: compressed（差はあるが小さすぎる）
    - それ以外: active（意味のある差がついている）
    overallのcompression_flagは、score_range_width<10点、または軸の過半数が
    compressed/nearly_deadのいずれかを満たす場合にTrueとする（閾値はヒューリスティックであり、
    今後の実測で調整してよい）。
    """
    if len(results) < 2:
        return {
            "compression_flag": None,
            "compression_reason": "batch size < 2のため比較不能",
            "active_axes_count": None,
            "compressed_axes_count": None,
            "score_range_width": None,
            "pairwise_distance_summary": None,
            "per_axis_stats": {},
        }

    scores = [r.normalized_score_overall for r in results]
    score_range_width = max(scores) - min(scores)

    per_axis_stats: dict[str, Any] = {}
    active_count = 0
    compressed_or_dead_count = 0
    for axis, max_points in QUALITY_SCORE_WEIGHTS.items():
        vals = [r.normalized_score_breakdown.get(axis, 0) for r in results]
        axis_stdev = statistics.stdev(vals) if len(vals) >= 2 else 0.0
        normalized_stdev = (axis_stdev / max_points) if max_points else 0.0
        if normalized_stdev < 0.05:
            status = "nearly_dead"
            compressed_or_dead_count += 1
        elif normalized_stdev < 0.15:
            status = "compressed"
            compressed_or_dead_count += 1
        else:
            status = "active"
            active_count += 1
        per_axis_stats[axis] = {
            "min": min(vals), "max": max(vals), "mean": round(statistics.mean(vals), 1),
            "stdev": round(axis_stdev, 2), "range": max(vals) - min(vals), "max_points": max_points,
            "normalized_stdev_pct": round(normalized_stdev * 100, 1), "status": status,
        }

    pairwise = [abs(scores[i] - scores[j]) for i in range(len(results)) for j in range(i + 1, len(results))]
    pairwise_distance_summary = {
        "count": len(pairwise),
        "mean": round(statistics.mean(pairwise), 1) if pairwise else None,
        "min": min(pairwise) if pairwise else None,
        "max": max(pairwise) if pairwise else None,
    }

    axis_total = len(QUALITY_SCORE_WEIGHTS)
    dead_or_compressed_ratio = compressed_or_dead_count / axis_total
    reasons = []
    if score_range_width < 10:
        reasons.append(f"overallのscore_range_width={score_range_width}が10点未満")
    if dead_or_compressed_ratio >= 0.5:
        flagged_axes = [a for a, s in per_axis_stats.items() if s["status"] in ("compressed", "nearly_dead")]
        reasons.append(f"軸の過半数（{compressed_or_dead_count}/{axis_total}）がcompressed/nearly_dead: {flagged_axes}")
    compression_flag = bool(reasons)

    return {
        "compression_flag": compression_flag,
        "compression_reason": "; ".join(reasons) if reasons else None,
        "active_axes_count": active_count,
        "compressed_axes_count": compressed_or_dead_count,
        "score_range_width": score_range_width,
        "pairwise_distance_summary": pairwise_distance_summary,
        "per_axis_stats": per_axis_stats,
    }


# --------------------------------------------------------------------------
# Comparative Gate B 実験ランナー（2026-08-25 quality_score_multidraft_gate_b追加）
#
# EXP-20260825-QS-MULTIDRAFT-01専用。single_draft_absolute_scoringが2実験連続で圧縮の
# 主因として支持されたことを受け、同一candidate由来の複数draftをComparative Gate B v1
# （external_audit_client.ExternalAuditClient.audit_quality_score_multidraft_v1()）へ
# まとめて渡し、結果をQualityScoreResult互換のdictとして返す実験専用関数。
#
# **重要: これはexperimental pathであり、本番のshipping decision経路（run_gate_b()/
# run_two_gate_audit_for_draft()/select_ship_candidate()）には一切接続しない。**
# 既存のsingle-draft pathはこの関数の追加によって一切変更されない。
# --------------------------------------------------------------------------
def run_gate_b_multidraft_experiment(
    candidate: Candidate,
    drafts: list[dict[str, Any]],
    audit_client: Any,
    batch_id: str | None = None,
) -> dict[str, Any]:
    """同一candidate由来の複数draft（drafts=[{"draft_id":..., "draft_text":..., "slot_mode":...}, ...]）を
    Comparative Gate B v1へまとめて渡し、比較結果を返す。audit_clientは
    audit_quality_score_multidraft_v1()を持つこと（ExternalAuditClient）。

    戻り値のnormalized_scores/normalized_bandsは、build_comparative_normalized_result()
    （external_audit_schema.py、TEACHER_FLOOR/SHIP_THRESHOLD/STRONG_SHIP_THRESHOLDを
    変更せずそのまま適用）で算出済み。呼び出し側（レポートスクリプト）はこの結果を
    実験の比較対象としてのみ使い、本番のfinal_shipping_decisionには使わないこと。
    """
    result: ComparativeQualityScoreResult = audit_client.audit_quality_score_multidraft_v1(
        layer_primary=candidate.layer_primary,
        source_post_id=candidate.source_post_id,
        source_full_text=candidate.source_full_text,
        source_structure_type=candidate.source_structure_type,
        source_reusable_elements=candidate.reusable_elements,
        drafts=drafts,
        batch_id=batch_id,
    )
    return {
        "batch_id": result.batch_id,
        "draft_ids": result.draft_ids,
        "audit_mode": result.audit_mode,
        "normalized_axis_breakdown": result.normalized_axis_breakdown,
        "normalized_scores": result.normalized_scores,
        "normalized_bands": result.normalized_bands,
        # 2026-08-26 R2-2: tier_bounded_v1マッピング（順位方向維持・gap圧縮）。
        # recommendation表示にはこちらを使う。normalized_scores（v1 Borda）は診断用に残す。
        "mapped_normalized_scores": result.mapped_normalized_scores,
        "mapped_normalized_bands": result.mapped_normalized_bands,
        "mapping_version": result.mapping_version,
        "mapping_diagnostics": result.mapping_diagnostics,
        "model_overall_ranking_reference_only": result.overall_ranking,
        "model_top_candidate_reference_only": result.top_candidate_id,
        "comparative_summary": result.comparative_summary,
        "compression_warning": result.compression_warning,
        "axis_results_raw": [
            {
                "axis_name": a.axis_name, "ranking_tiers": a.ranking_tiers, "tiers": a.tiers,
                "confidence": a.confidence, "rationale": a.rationale,
            }
            for a in result.axis_results
        ],
        "note": "experimental path専用の結果。本番shipping decision経路には接続していない",
    }


# --------------------------------------------------------------------------
# 2026-08-26 EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01追加。
# run_gate_b_multidraft_experiment()（legacy 9軸のみ）とは完全に独立した並行関数。
# legacy側のロジック・戻り値は一切変更しない。hook軸4本を追加したcomparative
# rubric（audit_quality_score_multidraft_hook_v2）を使い、legacy_axes_top_candidate_id
# （既存9軸のみでの推奨top）とhook_augmented_top_candidate_id（9軸+hook軸を踏まえた
# モデル自身の総合順位のtop）の両方を戻り値に含める。
# --------------------------------------------------------------------------
def run_gate_b_multidraft_hook_v2_experiment(
    candidate: Candidate,
    drafts: list[dict[str, Any]],
    audit_client: Any,
    batch_id: str | None = None,
) -> dict[str, Any]:
    """同一candidate由来の複数draftを、hook軸拡張版のComparative Gate B
    （audit_quality_score_multidraft_hook_v2）へまとめて渡す。audit_clientは
    audit_quality_score_multidraft_hook_v2()を持つこと（ExternalAuditClient）。
    legacy 9軸のraw/mapped scoreの計算経路はrun_gate_b_multidraft_experiment()と
    完全に同一（build_comparative_normalized_result + build_comparative_bounded_mapping_result）。
    """
    result: ComparativeQualityScoreResult = audit_client.audit_quality_score_multidraft_hook_v2(
        layer_primary=candidate.layer_primary,
        source_post_id=candidate.source_post_id,
        source_full_text=candidate.source_full_text,
        source_structure_type=candidate.source_structure_type,
        source_reusable_elements=candidate.reusable_elements,
        drafts=drafts,
        batch_id=batch_id,
    )
    return {
        "batch_id": result.batch_id,
        "draft_ids": result.draft_ids,
        "audit_mode": result.audit_mode,
        "comparative_rubric_version": result.comparative_rubric_version,
        "normalized_axis_breakdown": result.normalized_axis_breakdown,
        "normalized_scores": result.normalized_scores,
        "normalized_bands": result.normalized_bands,
        "mapped_normalized_scores": result.mapped_normalized_scores,
        "mapped_normalized_bands": result.mapped_normalized_bands,
        "mapping_version": result.mapping_version,
        "mapping_diagnostics": result.mapping_diagnostics,
        "model_overall_ranking_reference_only": result.overall_ranking,
        "model_top_candidate_reference_only": result.top_candidate_id,
        "comparative_summary": result.comparative_summary,
        "compression_warning": result.compression_warning,
        "axis_results_raw": [
            {
                "axis_name": a.axis_name, "ranking_tiers": a.ranking_tiers, "tiers": a.tiers,
                "confidence": a.confidence, "rationale": a.rationale,
            }
            for a in result.axis_results
        ],
        "hook_axis_results_raw": [
            {"axis_name": h.axis_name, "ranking": h.ranking, "rationale": h.rationale}
            for h in result.hook_axis_results
        ],
        "overall_ranking_hook_augmented": result.overall_ranking_hook_augmented,
        "hook_augmented_top_candidate_id": result.hook_augmented_top_candidate_id,
        "legacy_axes_top_candidate_id": result.legacy_axes_top_candidate_id,
        "note": "experimental path専用の結果（hook_augmented_v1）。本番shipping decision経路には接続していない",
    }


# --------------------------------------------------------------------------
# Phase D: Shadow Mode（2026-08-25 shadow_mode_run追加）
#
# 運用ブランチ（L0→L1→L2→L3→L6）を止めずに、Gate A pass済みdraft群へ研究ブランチの
# comparative Gate B（L4）を並走させ、結果をrecommendationとして記録するだけの機能。
# **採用判断には一切介入しない**（最終採用は人間/運用ブランチの既存決定ロジックが行う）。
# 詳細方針: ops/reports/operations_research_split_plan_2026-08-25.md、
#          ops/reports/shadow_mode_run_2026-08-25.md
# --------------------------------------------------------------------------
def run_shadow_mode_comparative_gate_b(
    candidate_groups: dict[str, dict[str, Any]],
    audit_client: Any,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Gate A pass済みdraft群を、同一candidate（同一source）単位でグルーピングした
    candidate_groups（{group_name: {"candidate": Candidate, "drafts": [{"draft_id":...,
    "draft_text":..., "slot_mode":...}, ...]}}）を受け取り、2件以上のグループにだけ
    comparative Gate Bを実行する。1件のみのグループはnot_applicable_single_survivorとして
    記録する（比較対象が無いため）。呼び出し側run（本番run）を止めない設計とするため、
    グループ単位の例外はexecution_failedとして記録し、他グループの処理・呼び出し元の
    本番runには一切伝播させないこと（呼び出し側でtry/exceptすること）。
    """
    results: dict[str, Any] = {}
    for group_name, group in candidate_groups.items():
        drafts = group["drafts"]
        if len(drafts) < 2:
            results[group_name] = {
                "shadow_mode_executed": False,
                "shadow_execution_status": "not_applicable_single_survivor",
                "shadow_failure_reason": "Gate A pass draftが1本のみで比較対象が無い",
                "draft_ids": [d["draft_id"] for d in drafts],
            }
            continue
        try:
            batch_id = f"{run_id}-{group_name}" if run_id else group_name
            result = run_gate_b_multidraft_experiment(group["candidate"], drafts, audit_client, batch_id=batch_id)
            result["shadow_mode_executed"] = True
            result["shadow_execution_status"] = "executed"
            result["shadow_failure_reason"] = None
            results[group_name] = result
        except Exception as e:  # noqa: BLE001 - shadow modeの失敗を本番runに伝播させないための意図的な広域捕捉
            results[group_name] = {
                "shadow_mode_executed": False,
                "shadow_execution_status": "execution_failed",
                "shadow_failure_reason": str(e),
                "draft_ids": [d["draft_id"] for d in drafts],
            }
    return results


def run_shadow_mode_comparative_gate_b_hook_v2(
    candidate_groups: dict[str, dict[str, Any]],
    audit_client: Any,
    run_id: str | None = None,
) -> dict[str, Any]:
    """run_shadow_mode_comparative_gate_b()のhook_augmented_v1版（2026-08-26
    EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01追加）。既存のrun_shadow_mode_comparative_gate_b()
    は一切変更しない。呼び出し側run（本番run）を止めない設計は同一
    （グループ単位の例外はexecution_failedとして記録し、伝播させない）。
    """
    results: dict[str, Any] = {}
    for group_name, group in candidate_groups.items():
        drafts = group["drafts"]
        if len(drafts) < 2:
            results[group_name] = {
                "shadow_mode_executed": False,
                "shadow_execution_status": "not_applicable_single_survivor",
                "shadow_failure_reason": "Gate A pass draftが1本のみで比較対象が無い",
                "draft_ids": [d["draft_id"] for d in drafts],
            }
            continue
        try:
            batch_id = f"{run_id}-{group_name}" if run_id else group_name
            result = run_gate_b_multidraft_hook_v2_experiment(group["candidate"], drafts, audit_client, batch_id=batch_id)
            result["shadow_mode_executed"] = True
            result["shadow_execution_status"] = "executed"
            result["shadow_failure_reason"] = None
            results[group_name] = result
        except Exception as e:  # noqa: BLE001 - shadow modeの失敗を本番runに伝播させないための意図的な広域捕捉
            results[group_name] = {
                "shadow_mode_executed": False,
                "shadow_execution_status": "execution_failed",
                "shadow_failure_reason": str(e),
                "draft_ids": [d["draft_id"] for d in drafts],
            }
    return results


# --------------------------------------------------------------------------
# 2026-08-27 EXP-20260827-FLHOOK-01実装。
#
# first-line hook evaluator: comparative Gate B本体（legacy v1・hook_augmented_v1）とは
# 完全に独立したresearch-onlyの補助判定器の呼び出し導線。既存のrun_gate_b_multidraft_*
# /run_shadow_mode_comparative_gate_b*関数は一切変更しない。structure系top（comparative
# Gate B本体）とhook系top（この評価器）を並記するだけで、どちらのtop-1も上書きしない。
# shipping decisionには一切接続しない。research branch / shadow mode / replayでのみ
# 有効化する想定（enable_first_line_hook_evaluatorフラグ）。
# 設計文書: ops/reports/first_line_hook_evaluator_design_2026-08-27.md
# --------------------------------------------------------------------------
def run_first_line_hook_evaluator_experiment(
    drafts: list[dict[str, Any]],
    audit_client: Any,
    structure_top_candidate_id: str | None = None,
    structure_reason_summary: str | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    """同一candidate由来の複数draft（drafts=[{"draft_id":..., "draft_text":..., "label":...}, ...]）を
    first-line hook evaluatorへまとめて渡す。audit_clientはaudit_first_line_hook_multidraft()を
    持つこと（ExternalAuditClient）。structure_top_candidate_id/structure_reason_summaryは
    呼び出し側がcomparative Gate B本体（legacy/hook_augmented_v1）の結果から渡すと、
    structure_hook_alignment等の比較フィールドが埋まる（渡さなければNoneのまま）。
    """
    result: FirstLineHookEvaluationResult = audit_client.audit_first_line_hook_multidraft(
        drafts=drafts, batch_id=batch_id,
    )
    result.structure_top_candidate_id = structure_top_candidate_id
    result.structure_hook_alignment = determine_structure_hook_alignment(
        structure_top_candidate_id, result.hook_top_candidate_id
    )
    result.structure_reason_summary = structure_reason_summary
    result.hook_reason_summary = result.hook_summary_reason
    out = evaluation_result_to_dict(result)
    out["note"] = "experimental path専用の結果（first_line_hook_v1）。本番shipping decision経路には接続していない"
    return out


def run_opening_span_hook_evaluator_experiment(
    drafts: list[dict[str, Any]],
    audit_client: Any,
    structure_top_candidate_id: str | None = None,
    structure_reason_summary: str | None = None,
    hook_v1_top_candidate_id: str | None = None,
    hook_v1_reason_summary: str | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    """[実験専用/2026-08-28 EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01]
    hook_v2 (opening span evaluator) をdraftグループへ実行する。audit_clientは
    audit_opening_span_hook_multidraft()を持つこと（ExternalAuditClient）。
    structure_top_candidate_id/hook_v1_top_candidate_idを渡すと、
    structure_vs_hook_v2_alignment/hook_v1_vs_hook_v2_alignmentが埋まる
    （渡さなければNoneのまま。hook_v1・comparative Gate B本体は一切変更しない）。
    """
    result: OpeningSpanHookEvaluationResult = audit_client.audit_opening_span_hook_multidraft(
        drafts=drafts, batch_id=batch_id,
    )
    result.structure_top_candidate_id = structure_top_candidate_id
    result.structure_vs_hook_v2_alignment = determine_structure_hook_alignment(
        structure_top_candidate_id, result.hook_v2_top_candidate_id
    )
    result.hook_v1_top_candidate_id = hook_v1_top_candidate_id
    result.hook_v1_vs_hook_v2_alignment = determine_hook_v1_vs_hook_v2_alignment(
        hook_v1_top_candidate_id, result.hook_v2_top_candidate_id
    )
    result.structure_reason_summary = structure_reason_summary
    result.hook_v1_reason_summary = hook_v1_reason_summary
    out = evaluation_result_v2_to_dict(result)
    out["note"] = "experimental research-only path専用の結果（opening_span_hook_v2）。hook_v1・comparative Gate B本体・本番shipping decision経路には接続していない"
    return out


_DEFAULT_POSTED_THEME_REGISTRY_PATH = _REPO_ROOT / "ops" / "reports" / "posted_theme_registry_2026-08-30.json"


def run_posted_theme_guard_check(
    candidate_source_post_id: str | None,
    candidate_texts: list[str],
    target_layer: str | None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """[2026-08-30 posted-theme exclusion] mainline開始前ガード。指定した
    posted theme registry（既定は`ops/reports/posted_theme_registry_2026-08-30.json`）を
    読み込み、candidate（source_post_id・draft/source本文）を照合して
    block_mainline/route_to_research/cooldown_active等を判定する。

    registry_pathが存在しない場合はregistryを空扱いとし、全candidateをblockしない
    （registry未構築時にmainlineを誤って全停止させないための安全側フォールバック）。
    外部AI呼び出しは行わない。production scoring/Gate A/thresholds/shipping decisionには
    一切触れない。
    """
    path = Path(registry_path) if registry_path else _DEFAULT_POSTED_THEME_REGISTRY_PATH
    registry = load_posted_theme_registry(path) if path.exists() else []
    return check_posted_theme_guard(
        candidate_source_post_id=candidate_source_post_id,
        candidate_texts=candidate_texts,
        target_layer=target_layer,
        registry=registry,
    )


_DEFAULT_TOPIC_GROUP_STATE_PATH = _REPO_ROOT / "ops" / "reports" / "topic_group_state_2026-08-31.json"


def evaluate_topic_group_for_mainline(
    candidate_source_post_id: str | None,
    candidate_texts: list[str],
    target_layer: str | None,
    exploration_quota_remaining: bool = True,
    posted_theme_registry_path: str | Path | None = None,
    topic_group_state_path: str | Path | None = None,
) -> dict[str, Any]:
    """[2026-08-31 topic_groupライフサイクル管理] mainline候補生成直前フィルタ本体。

    posted_theme_registry.check_posted_theme_guard()の判定と、topic_group_stateの
    5条件フィルタ（topic_status=active／posted-theme exclusion／retry_budget>0／
    cooldown外／exploration quota内）をまとめて評価する。stateストアの永続化(save)は
    この関数では行わない——in-memory storeを返すので、呼び出し側がfinalize時に
    まとめて保存する（record_mainline_attempt()等で状態を更新してから保存する想定）。

    外部AI呼び出しは行わない。production scoring/Gate A/thresholds/shipping decision
    には一切触れない。
    """
    guard_result = run_posted_theme_guard_check(
        candidate_source_post_id=candidate_source_post_id,
        candidate_texts=candidate_texts,
        target_layer=target_layer,
        registry_path=posted_theme_registry_path,
    )
    profile = build_theme_profile(candidate_texts)
    path = Path(topic_group_state_path) if topic_group_state_path else _DEFAULT_TOPIC_GROUP_STATE_PATH
    store = load_topic_group_state_store(path)
    state = get_or_create_topic_group(store, profile["topic_group"], profile["theme_signature"])
    filter_result = passes_mainline_candidate_filter(
        state,
        posted_theme_blocked=guard_result["block_mainline"],
        exploration_quota_remaining=exploration_quota_remaining,
    )
    return {
        "guard_result": guard_result,
        "topic_group_id": state.topic_group_id,
        "theme_signature": profile["theme_signature"],
        "filter_result": filter_result,
        "store": store,
        "state_path": str(path),
    }


def record_topic_group_outcome_and_save(
    store: dict[str, TopicGroupState],
    topic_group_id: str,
    succeeded: bool,
    published_at: str | None = None,
    repo_root: str | Path | None = None,
    label: str | None = None,
) -> Path:
    """[2026-08-31 topic_groupライフサイクル管理] evaluate_topic_group_for_mainline()で
    取得したin-memory storeへ、mainline試行結果（succeeded）・実投稿確定（published_at）を
    反映して保存する。「不発テーマの延命」防止（retry_budget消費）と「投稿済みテーマの
    ライフサイクル退場」（record_publication）をここで確定させる。
    """
    state = store.get(topic_group_id)
    if state is None:
        raise KeyError(f"topic_group_id={topic_group_id} がstoreに存在しません")
    record_mainline_attempt(state, succeeded=succeeded)
    if published_at:
        record_publication(state, published_at=published_at)
    return save_topic_group_state_store(store, repo_root or _REPO_ROOT, label=label)


def update_topic_performance_from_post_analytics(
    topic_group_id: str,
    impression_count: int | None,
    topic_group_state_path: str | Path | None = None,
    repo_root: str | Path | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """[2026-08-31 topic_groupライフサイクル管理] post_analytics取得後に、対応する
    topic_groupのtopic_performance_bandを更新するbatch関数（フィードバック接続）。
    mainlineの候補生成とは非同期（enrichment/post_analytics取得と同じnon-blocking
    原則）——本関数の失敗はmainline処理には一切伝播しない設計とし、呼び出し側で
    try/exceptすることを想定する。
    """
    path = Path(topic_group_state_path) if topic_group_state_path else _DEFAULT_TOPIC_GROUP_STATE_PATH
    store = load_topic_group_state_store(path)
    state = store.get(topic_group_id)
    if state is None:
        return {"updated": False, "reason": f"topic_group_id={topic_group_id} がstoreに存在しません"}
    update_performance_band(state, impression_count=impression_count)
    saved_path = save_topic_group_state_store(store, repo_root or _REPO_ROOT, label=label)
    return {"updated": True, "topic_performance_band": state.topic_performance_band, "saved_path": str(saved_path)}


def finalize_minimal_run_log(
    run_id: str,
    source_post_id: str | None,
    target_layer: str | None,
    draft_ids: list[str] | None = None,
    gate_a_pass_ids: list[str] | None = None,
    human_selected_top: str | None = None,
    published_draft_id: str | None = None,
    selection_reason_short: str | None = None,
    primary_source_post_id: str | None = None,
    fallback_source_post_id: str | None = None,
    used_fallback_source: bool = False,
    research_followup_required: bool = False,
    published_at: str | None = None,
    post_url: str | None = None,
    posted_theme_check: dict[str, Any] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """[学習モードLayer1: 投稿時最小ログ/2026-08-28 GOV-20260828-ASYNC-ENRICHMENT-REDESIGN-01]

    Gate A結果とhuman selectionからminimal_run_logを組み立て、persist=Trueなら
    ops/reports/へ保存する。structure_top_candidate_id/hook_top_candidate_id等の
    research/enrichment情報は引数に一切含まれず、要求もしない——本線の完了判定は
    「Gate A survivorsからhumanが1本選べたか」だけで決まる。

    本関数はshipping decisionの判断結果（select_ship_candidate/evaluate_shipping_decision_
    from_normalized_gate_b等）には一切関与しない。それらの関数の呼び出し前でも後でも、
    人間の最終選定さえ分かれば独立に呼び出せる記録専用の関数である。

    posted_theme_checkに`run_posted_theme_guard_check()`（2026-08-30 posted-theme exclusion）
    の戻り値を渡すと、そのblock/routing判定結果がログへ格納される（渡さなくても動作する）。
    渡した場合でも、本関数自体はmainline_statusを書き換えない——block_mainline=Trueのcandidate
    をhuman selectionへ進めるかどうかの運用判断は呼び出し側（このセッションの操作者）の責務。
    """
    log = build_minimal_run_log(
        run_id=run_id,
        source_post_id=source_post_id,
        target_layer=target_layer,
        draft_ids=draft_ids,
        gate_a_pass_ids=gate_a_pass_ids,
        human_selected_top=human_selected_top,
        published_draft_id=published_draft_id,
        selection_reason_short=selection_reason_short,
        primary_source_post_id=primary_source_post_id,
        fallback_source_post_id=fallback_source_post_id,
        used_fallback_source=used_fallback_source,
        research_followup_required=research_followup_required,
        published_at=published_at,
        post_url=post_url,
        posted_theme_check=posted_theme_check,
    )
    out: dict[str, Any] = {"minimal_run_log": minimal_run_log_to_dict(log)}
    if persist:
        saved_path = save_minimal_run_log(log, _REPO_ROOT)
        out["saved_path"] = str(saved_path)
    return out


_STRUCTURE_MAPPED_GAP_CONFIDENT_THRESHOLD = 5.0
_HOOK_V1_CONSENSUS_CONFIDENT_THRESHOLD = 0.75
_HOOK_V1_CONSENSUS_MODERATE_THRESHOLD = 0.5


def evaluate_structure_hook_divergence(
    structure_top_candidate_id: str | None,
    hook_top_candidate_id: str | None,
    mapped_normalized_scores: dict[str, float] | None = None,
    hook_v1_axis_rankings: list[dict[str, Any]] | None = None,
    human_initial_top: str | None = None,
    human_final_top: str | None = None,
) -> dict[str, Any]:
    """[実験専用/2026-08-28 EXP-20260828-METAGATE-DIVERGENCE-01] structure evaluator
    （comparative Gate B本体）とhook_v1（first-line hook evaluator）のsplitを、
    「どちらが正しいか」の勝敗判定ではなく「人間確認の価値が高い局面」を示す
    review priority signalとして評価する。外部AI呼び出しは行わない（既存の
    structure_result/hook_v1結果に対する純粋な後段計算）。hook_v2はこの判定の
    入力に使わない（Run13で優位性が確認できなかったため）。

    mapped_normalized_scores/hook_v1_axis_rankingsを渡さない場合は、
    structure/hookそれぞれの「確信度」を判定できないため、両方とも保守的に
    weak側（confidence不明）として扱い、severityの計算は控えめに倒す。
    human_initial_top/human_final_topは分かる範囲で渡してよい（未取得ならNoneのまま）。
    このいずれの入力もshipping decisionには一切接続しない。
    """
    structure_hook_alignment = determine_structure_hook_alignment(structure_top_candidate_id, hook_top_candidate_id)
    structure_hook_divergence = bool(structure_hook_alignment is False)

    mapped_gap = None
    structure_confident = False
    if mapped_normalized_scores and len(mapped_normalized_scores) >= 2:
        vals = list(mapped_normalized_scores.values())
        mapped_gap = max(vals) - min(vals)
        structure_confident = mapped_gap >= _STRUCTURE_MAPPED_GAP_CONFIDENT_THRESHOLD

    hook_v1_consensus = None
    hook_confidence_level = "unknown"
    if hook_v1_axis_rankings and hook_top_candidate_id is not None:
        hook_v1_consensus = compute_hook_v1_axis_consensus(hook_v1_axis_rankings, hook_top_candidate_id)
        if hook_v1_consensus >= _HOOK_V1_CONSENSUS_CONFIDENT_THRESHOLD:
            hook_confidence_level = "confident"
        elif hook_v1_consensus >= _HOOK_V1_CONSENSUS_MODERATE_THRESHOLD:
            hook_confidence_level = "moderate"
        else:
            hook_confidence_level = "weak"

    if not structure_hook_divergence:
        divergence_type = "none"
        divergence_severity = "low"
        recommended_review_mode = "auto_candidate_ok"
        divergence_reason_summary = (
            "structure_top_candidate_idとhook_top_candidate_idが一致しており、divergenceは発生していない。"
            "自動候補として扱ってよい水準（recommendation-only前提での参考評価に留まる）"
        )
    else:
        hook_has_signal = hook_confidence_level in ("confident", "moderate")
        if structure_confident and hook_has_signal:
            divergence_type = "mutual_disagreement"
        elif structure_confident and not hook_has_signal:
            divergence_type = "structure_only"
        elif not structure_confident and hook_has_signal:
            divergence_type = "hook_only"
        else:
            divergence_type = "mutual_disagreement"  # 両者ともconfidenceが低い弱いsplitも、mutualの一種として扱う

        if divergence_type == "mutual_disagreement" and structure_confident and hook_has_signal:
            divergence_severity = "high"
        elif divergence_type in ("structure_only", "hook_only"):
            divergence_severity = "medium"
        else:
            divergence_severity = "low"

        # 「split時は原則human_review_required以上に寄せる」という運用方針に従い、
        # severityがlowであっても最低限human_review_requiredまでは引き上げる。
        recommended_review_mode = (
            "human_review_priority_high" if divergence_severity == "high" else "human_review_required"
        )
        divergence_reason_summary = (
            f"structure_top={structure_top_candidate_id}（mapped_gap="
            f"{mapped_gap if mapped_gap is not None else 'unknown'}、confident={structure_confident}）、"
            f"hook_top={hook_top_candidate_id}（axis_consensus="
            f"{hook_v1_consensus if hook_v1_consensus is not None else 'unknown'}、confidence={hook_confidence_level}）"
            f"で不一致。divergence_type={divergence_type}、severity={divergence_severity}。"
            "structureとhookのどちらが正しいかを自動では確定させず、split自体を人間確認の優先度シグナルとして扱う"
        )

    divergence_vs_human_observation = None
    if human_final_top is not None:
        structure_matched = structure_top_candidate_id == human_final_top
        hook_matched = hook_top_candidate_id == human_final_top
        if structure_matched and hook_matched:
            divergence_vs_human_observation = "human_final_topはstructure_top/hook_top双方と一致（今回のsplit判定は該当なし、または元々divergenceなし）"
        elif structure_matched:
            divergence_vs_human_observation = "human_final_topはstructure_topと一致し、hook_topとは不一致だった（このsplitはstructure側に軍配）"
        elif hook_matched:
            divergence_vs_human_observation = "human_final_topはhook_topと一致し、structure_topとは不一致だった（このsplitはhook側に軍配）"
        else:
            divergence_vs_human_observation = "human_final_topはstructure_top/hook_topのいずれとも不一致だった"
    elif human_initial_top is not None:
        divergence_vs_human_observation = "human_final_topは未取得。human_initial_topのみ参考値として存在する（Step B完了までは断定しない）"
    else:
        divergence_vs_human_observation = "human judgmentは未取得のため、split方向の答え合わせはまだできない"

    result = {
        "structure_top_candidate_id": structure_top_candidate_id,
        "hook_top_candidate_id": hook_top_candidate_id,
        "structure_hook_alignment": structure_hook_alignment,
        "structure_hook_divergence": structure_hook_divergence,
        "divergence_type": divergence_type,
        "divergence_severity": divergence_severity,
        "recommended_review_mode": recommended_review_mode,
        "divergence_reason_summary": divergence_reason_summary,
        "structure_mapped_gap": mapped_gap,
        "hook_v1_axis_consensus": hook_v1_consensus,
        "human_initial_top": human_initial_top,
        "human_final_top": human_final_top,
        "divergence_vs_human_observation": divergence_vs_human_observation,
        "meta_gate_takeaway": None,
        "note": "experimental research-only path専用の結果（meta_gate_divergence_v1）。hook_v2は入力に使わない。本番shipping decision経路には接続していない",
    }
    validate_meta_gate_divergence_result(result)
    return result


def run_async_enrichment_experiment(
    run_id: str,
    structure_top_candidate_id: str | None = None,
    hook_top_candidate_id: str | None = None,
    mapped_normalized_scores: dict[str, float] | None = None,
    raw_normalized_scores: dict[str, float] | None = None,
    hook_v1_axis_rankings: list[dict[str, Any]] | None = None,
    human_initial_top: str | None = None,
    human_final_top: str | None = None,
    human_initial_confidence: str | None = None,
    human_final_confidence: str | None = None,
    recommendation_influence_level: str | None = None,
    comparative_snapshot_persisted: bool | None = None,
    mapping_version: str | None = None,
    step_a_disclosure_contamination: bool = False,
    minimal_run_log_path: str | Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """[学習モードLayer2: 投稿後非同期enrichment/2026-08-28 GOV-20260828-ASYNC-ENRICHMENT-REDESIGN-01]

    minimal_run_log（Layer1、scripts/minimal_run_log.py）を壊さずに、structure/hook/
    divergenceの研究情報をbest-effortで追記する。**この関数は例外を送出しない。**
    処理中に何が起きても`enrichment_status="failed_non_blocking"`のレコードを返す
    だけであり、呼び出し元のmainline処理（Gate A/human selection/投稿判断）には
    一切伝播させない（既存のrun_shadow_mode_first_line_hook_evaluator()と同じ
    「グループ単位の例外を握りつぶし、runを止めない」設計原則をenrichment全体に適用する）。

    structure_top_candidate_id/hook_top_candidate_idの少なくとも一方が渡された場合のみ
    evaluate_structure_hook_divergence()（EXP-20260828-METAGATE-DIVERGENCE-01）を呼んで
    divergence判定を行う。新規の外部AI呼び出しは一切行わない——既存の保存済み
    structure_result/hook_result/human selectionに対する後段計算のみ。

    minimal_run_log_pathを渡した場合、対応するminimal_run_log JSONの
    `enrichment_status`フィールドのみを本処理結果に合わせて更新し再保存する。
    `mainline_status`等の他フィールドには一切触れない（更新自体が失敗しても
    non-blockingに扱う）。
    """
    try:
        divergence_result = None
        if structure_top_candidate_id is not None or hook_top_candidate_id is not None:
            divergence_result = evaluate_structure_hook_divergence(
                structure_top_candidate_id=structure_top_candidate_id,
                hook_top_candidate_id=hook_top_candidate_id,
                mapped_normalized_scores=mapped_normalized_scores,
                hook_v1_axis_rankings=hook_v1_axis_rankings,
                human_initial_top=human_initial_top,
                human_final_top=human_final_top,
            )
        record = build_enrichment_record(
            run_id=run_id,
            divergence_result=divergence_result,
            human_initial_top=human_initial_top,
            human_final_top=human_final_top,
            human_initial_confidence=human_initial_confidence,
            human_final_confidence=human_final_confidence,
            recommendation_influence_level=recommendation_influence_level,
            comparative_snapshot_persisted=comparative_snapshot_persisted,
            mapping_version=mapping_version,
            raw_normalized_scores=raw_normalized_scores,
            mapped_normalized_scores=mapped_normalized_scores,
            step_a_disclosure_contamination=step_a_disclosure_contamination,
        )
    except Exception as e:  # noqa: BLE001 - enrichment失敗をmainlineへ伝播させないための意図的な広域捕捉
        record = build_failed_enrichment_record(run_id, str(e))

    out: dict[str, Any] = {"enrichment_record": enrichment_record_to_dict(record)}

    if persist:
        try:
            saved_path = save_enrichment_record(record, _REPO_ROOT)
            out["saved_path"] = str(saved_path)
        except Exception as e:  # noqa: BLE001 - 保存失敗もnon-blocking
            out["save_error"] = str(e)

    if minimal_run_log_path is not None:
        try:
            path = Path(minimal_run_log_path)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["enrichment_status"] = record.enrichment_status
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            out["minimal_run_log_updated"] = True
        except Exception as e:  # noqa: BLE001 - minimal_run_log更新失敗もnon-blocking
            out["minimal_run_log_update_error"] = str(e)

    return out


def run_shadow_mode_first_line_hook_evaluator(
    candidate_groups: dict[str, dict[str, Any]],
    audit_client: Any,
    run_id: str | None = None,
    structure_top_candidate_ids: dict[str, str] | None = None,
    structure_reason_summaries: dict[str, str] | None = None,
    enable_first_line_hook_evaluator: bool = True,
) -> dict[str, Any]:
    """run_shadow_mode_comparative_gate_b()と同じ形式で、first-line hook evaluatorを
    グループ単位で並走実行する。呼び出し側run（本番run）を止めない設計は同一
    （グループ単位の例外はexecution_failedとして記録し、伝播させない）。

    enable_first_line_hook_evaluator=Falseの場合は一切API呼び出しをせず、
    全グループを"disabled"として返す（research branch / shadow mode / replayでのみ
    有効化する想定のフラグ）。structure_top_candidate_ids/structure_reason_summariesは
    {group_name: value}の辞書で、comparative Gate B本体側の結果を渡すと比較フィールドが埋まる。
    """
    structure_top_candidate_ids = structure_top_candidate_ids or {}
    structure_reason_summaries = structure_reason_summaries or {}
    results: dict[str, Any] = {}
    for group_name, group in candidate_groups.items():
        drafts = group["drafts"]
        if not enable_first_line_hook_evaluator:
            results[group_name] = {
                "shadow_mode_executed": False,
                "shadow_execution_status": "disabled",
                "shadow_failure_reason": "enable_first_line_hook_evaluator=Falseのため未実行",
                "draft_ids": [d["draft_id"] for d in drafts],
            }
            continue
        if len(drafts) < 2:
            results[group_name] = {
                "shadow_mode_executed": False,
                "shadow_execution_status": "not_applicable_single_survivor",
                "shadow_failure_reason": "Gate A pass draftが1本のみで比較対象が無い",
                "draft_ids": [d["draft_id"] for d in drafts],
            }
            continue
        try:
            batch_id = f"{run_id}-{group_name}-flhook" if run_id else f"{group_name}-flhook"
            result = run_first_line_hook_evaluator_experiment(
                drafts, audit_client,
                structure_top_candidate_id=structure_top_candidate_ids.get(group_name),
                structure_reason_summary=structure_reason_summaries.get(group_name),
                batch_id=batch_id,
            )
            result["shadow_mode_executed"] = True
            result["shadow_execution_status"] = "executed"
            result["shadow_failure_reason"] = None
            results[group_name] = result
        except Exception as e:  # noqa: BLE001 - shadow modeの失敗を本番runに伝播させないための意図的な広域捕捉
            results[group_name] = {
                "shadow_mode_executed": False,
                "shadow_execution_status": "execution_failed",
                "shadow_failure_reason": str(e),
                "draft_ids": [d["draft_id"] for d in drafts],
            }
    return results


def compare_shadow_recommendation_with_human_decision(
    comparative_top_candidate_id: str | None,
    human_selected_draft_id: str | None,
    comparative_overall_ranking: list[str] | None = None,
) -> dict[str, Any]:
    """comparative Gate Bのtop_candidate_idと、人間（または運用ブランチの決定的選定規則）の
    選択結果を突き合わせ、match/mismatch/not_applicableを判定する。この関数はいかなる
    採用判断にも介入しない（純粋な比較・記録用）。
    """
    if comparative_top_candidate_id is None or human_selected_draft_id is None:
        return {
            "match_status": "not_applicable",
            "gap_summary": "comparative_top_candidate_idまたはhuman_selected_draft_idが未確定のため比較不能",
            "rationale_note": None,
        }
    if comparative_top_candidate_id == human_selected_draft_id:
        return {"match_status": "match", "gap_summary": "一致", "rationale_note": None}

    human_rank = None
    if comparative_overall_ranking:
        try:
            human_rank = comparative_overall_ranking.index(human_selected_draft_id) + 1
        except ValueError:
            human_rank = None
    gap_summary = f"comparative top-1={comparative_top_candidate_id} / human選択={human_selected_draft_id}"
    if human_rank is not None:
        gap_summary += f"（human選択はcomparative順位{human_rank}位相当）"
    return {"match_status": "mismatch", "gap_summary": gap_summary, "rationale_note": None}


def build_shadow_mode_log(
    run_id: str,
    gate_a_pass_draft_ids: list[str],
    human_selected_draft_id: str | None,
    shadow_results: dict[str, Any],
    match_result: dict[str, Any],
    phase_e_readiness: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """1回のshadow mode run分のログをJSON保存用の形へ組み立てる。
    phase_e_readinessは呼び出し側が"not_ready"/"partially_ready"/"ready_for_promotion_review"
    のいずれかを判断して渡すこと（この関数は判定ロジックを持たない）。
    """
    log = {
        "run_id": run_id,
        "gate_a_pass_draft_ids": gate_a_pass_draft_ids,
        "human_selected_draft_id": human_selected_draft_id,
        "shadow_results": shadow_results,
        "recommendation_vs_human_match": match_result["match_status"],
        "recommendation_vs_human_gap_summary": match_result["gap_summary"],
        "phase_e_readiness": phase_e_readiness,
    }
    if extra:
        log.update(extra)
    return log


def save_pipeline_log(results: list[dict[str, Any]], run_label: str) -> Path:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _LOG_DIR / f"draft_audit_log_{run_label}.json"
    out_path.write_text(
        json.dumps(
            {"run_at": datetime.now(timezone.utc).isoformat(), "results": results},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return out_path


# --------------------------------------------------------------------------
# 段階A/B補助: Phase 2出力からの候補読み込み
# --------------------------------------------------------------------------
def load_pre_teacher_candidates() -> list[dict[str, Any]]:
    path = _PHASE2_OUTPUT_DIR / "pre_teacher_candidate.json"
    if not path.exists():
        print(f"エラー: {path} が見つかりません。先にPhase 1/2を実行してください。", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 自社過去投稿の自動除外（2026-08-21 production_pipeline_patch追加）
#
# 背景: 探索結果の pre_teacher_candidate に自社の過去投稿が再ヒットして混入した
# （production_selection_fashion_gadget_2026-08-21.mdで手動検出）。これを機械的に
# 検出・除外する。「先生」は外部の勝ち投稿でなければならず、自社投稿を先生として
# 再現するのは自己参照的で先生最強前提と矛盾する。
# --------------------------------------------------------------------------
_POST_TEXT_URL_PATTERN = re.compile(r"https?://\S+")
_POST_TEXT_QUOTE_PATTERN = re.compile(r"[「」『』\"'‘’“”]")


def normalize_post_text(text: str) -> str:
    """自社投稿マッチング用の全文正規化（URL除去/空白・改行差吸収/全半角統一/引用符差吸収）。

    concrete_item_enrichment.normalize_surface_text() は単語単位の照合向けの正規化で、
    改行を含む投稿全文の比較には別途これを使う（改行→空白統一・連続空白圧縮を行う）。
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _POST_TEXT_URL_PATTERN.sub("", text)
    text = _POST_TEXT_QUOTE_PATTERN.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", "", text)
    return text.strip().lower()


def load_own_post_registry() -> list[dict[str, Any]]:
    """postsシート（Google Sheets、正本）から自社の既投稿レジストリを読み込む。

    selected_for_post=yes かつ tweet_idありの行のみを対象にする
    （下書き未投稿は除外対象に含めない、という指示書の方針どおり）。
    """
    from x_metrics_collector.config import load_config
    from x_metrics_collector.sheets_client import SheetsClient

    client = SheetsClient(load_config())
    posts = client.get_posts()

    registry: list[dict[str, Any]] = []
    for p in posts:
        if str(p.get("selected_for_post", "")).strip().lower() != "yes":
            continue
        tweet_id = str(p.get("tweet_id", "")).strip()
        if not tweet_id:
            continue
        final_text = p.get("final_text", "") or ""
        registry.append(
            {
                "post_id": p.get("post_id"),
                "tweet_id": tweet_id,
                "posted_url": str(p.get("posted_url", "")).strip(),
                "final_text": final_text,
                "final_text_normalized": normalize_post_text(final_text),
            }
        )
    return registry


_OWN_POST_SOFT_MATCH_THRESHOLD = 0.92


def is_own_post_candidate(
    candidate_post_id: str, candidate_text: str, registry: list[dict[str, Any]]
) -> tuple[bool, str | None, str | None]:
    """候補が自社の既投稿と一致するか判定する。

    戻り値は (is_own_post, match_type, matched_own_post_id)。
    match_typeの優先順位: tweet_id > url > text_exact > text_soft。
    """
    candidate_post_id = str(candidate_post_id or "").strip()
    candidate_text_norm = normalize_post_text(candidate_text)

    for entry in registry:
        if candidate_post_id and entry["tweet_id"] and candidate_post_id == entry["tweet_id"]:
            return True, "tweet_id", entry["post_id"]

    for entry in registry:
        if entry["posted_url"] and candidate_post_id and entry["posted_url"].rstrip("/").endswith(candidate_post_id):
            return True, "url", entry["post_id"]

    for entry in registry:
        if candidate_text_norm and entry["final_text_normalized"] and candidate_text_norm == entry["final_text_normalized"]:
            return True, "text_exact", entry["post_id"]

    for entry in registry:
        if not (candidate_text_norm and entry["final_text_normalized"]):
            continue
        ratio = difflib.SequenceMatcher(None, candidate_text_norm, entry["final_text_normalized"]).ratio()
        if ratio >= _OWN_POST_SOFT_MATCH_THRESHOLD:
            return True, "text_soft", entry["post_id"]

    return False, None, None


def filter_out_own_posts(
    candidates: list[dict[str, Any]], registry: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """候補リストから自社既投稿を除外する。戻り値は (kept, excluded)。

    excludedの各要素には is_own_post / own_post_match_type / excluded_reason を付与する。
    """
    kept: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for c in candidates:
        candidate_post_id = c.get("post_id") or c.get("tweet_id") or ""
        candidate_text = c.get("text") or c.get("source_full_text") or ""
        is_own, match_type, matched_id = is_own_post_candidate(candidate_post_id, candidate_text, registry)
        c2 = dict(c)
        if is_own:
            c2["is_own_post"] = True
            c2["own_post_match_type"] = match_type
            c2["exclusion_stage"] = "pre_teacher_candidate_post_filter"
            c2["excluded_reason"] = (
                f"自社投稿(post_id={matched_id})との{match_type}一致のため候補から除外"
                "（先生は外部の勝ち投稿のみを対象とする方針のため）"
            )
            excluded.append(c2)
        else:
            c2["is_own_post"] = False
            kept.append(c2)
    return kept, excluded
