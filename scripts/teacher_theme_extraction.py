"""teacher投稿（pre_teacher_candidate）本文から、topic_group自動登録用のテーマ要素を
機械的に抽出するpure function層。

**再利用方針**: theme_signature/topic_group_idの組み立て自体は
topic_dedupe.build_theme_signature()/build_topic_group()（既存、正本）をそのまま使う。
本モジュールが新設するのは、その入力となる`components`辞書（product/use_case/
comparison_axis/contrast/conclusionの5次元）を、teacher投稿本文からルールベースで
組み立てる部分のみ。

- 商品名・カテゴリ語: x_api_phase2_classify.GADGET_CORE_KEYWORDS/FASHION_CORE_
  KEYWORDS_SPECIFIC（既存、broaderなジャンル辞書）を再利用する。topic_dedupe.
  PRODUCT_TERMS（ATH-PRO5MK2等、既知の特定型番のみを対象にした狭い辞書）はそのままでは
  一般的なteacher投稿の商品抽出には狭すぎるため使わない——ただし
  use_case/comparison_axis/contrast/conclusionの4次元はtopic_dedupe.
  extract_theme_components()の結果をそのまま流用する（既存の正規化・表記ゆれ吸収
  ロジックを再実装しない）。
- 訴求切り口: x_api_phase2_classify.DECISION_KEYWORDS（既存、比較・選び方等の語彙）を
  再利用し、topic_dedupe側のcomparison_axis抽出結果へ合流させる。

抽出されたタグは、辞書に登場する日本語キーワードそのものを使う（英語スラッグへの
変換・翻訳は行わない——存在しない対応関係を捏造しないため）。

Gate A/thresholds/shipping decision、_apply_engagement_gate()、_classify_core()、
topic_groupの既存ライフサイクル関数（record_mainline_attempt等）・候補フィルタ
（passes_mainline_candidate_filter）本体には一切触れない。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from topic_dedupe import build_theme_signature, build_topic_group, extract_theme_components
from topic_group_state import TopicGroupState, get_or_create_topic_group
from x_api_phase2_classify import (
    DECISION_KEYWORDS,
    FASHION_CORE_KEYWORDS_SPECIFIC,
    GADGET_CORE_KEYWORDS,
    _mask_negated_genre_context,
)

_COMPONENT_DIMENSIONS = ("product", "use_case", "comparison_axis", "contrast", "conclusion")


def _matched_tags(text: str, keywords: list[str]) -> list[str]:
    """textに含まれるkeywords内の語を、辞書の表記そのままタグとして返す（重複除去・整列済み）。"""
    return sorted({kw for kw in keywords if kw in text})


def extract_teacher_theme_components(text: str) -> dict[str, list[str]]:
    """teacher投稿本文から、topic_dedupe.build_theme_signature()/build_topic_group()へ
    渡せる形のcomponents辞書（product/use_case/comparison_axis/contrast/conclusion）を
    組み立てる。

    product: GADGET_CORE_KEYWORDS/FASHION_CORE_KEYWORDS_SPECIFIC（ジャンル全体の広い辞書）
    use_case/contrast/conclusion: topic_dedupe.extract_theme_components()の抽出結果を
        そのまま使う（既存の正規化ロジックを再実装しない）
    comparison_axis: topic_dedupe側の抽出結果 + DECISION_KEYWORDS由来のタグを合流
    """
    genre_text = _mask_negated_genre_context(text)
    base_components = extract_theme_components(text)

    product_tags = sorted(
        set(_matched_tags(genre_text, GADGET_CORE_KEYWORDS))
        | set(_matched_tags(genre_text, FASHION_CORE_KEYWORDS_SPECIFIC))
    )
    if not product_tags:
        # ジャンル辞書で何も検出できない場合のみ、topic_dedupe側の狭い既知商品名
        # マッチ（ATH-PRO5MK2等）にフォールバックする。
        product_tags = sorted(base_components.get("product", []))

    comparison_axis_tags = sorted(
        set(base_components.get("comparison_axis", [])) | set(_matched_tags(genre_text, DECISION_KEYWORDS))
    )

    return {
        "product": product_tags,
        "use_case": sorted(base_components.get("use_case", [])),
        "comparison_axis": comparison_axis_tags,
        "contrast": sorted(base_components.get("contrast", [])),
        "conclusion": sorted(base_components.get("conclusion", [])),
    }


def build_teacher_theme_profile(text: str) -> dict[str, Any]:
    """teacher投稿本文1件から、topic_group自動登録に必要な情報一式（components/
    theme_signature/topic_group_id）をまとめて返す。

    theme_signature/topic_group_idの組み立て自体はtopic_dedupe.build_theme_signature()/
    build_topic_group()（既存、正本）をそのまま使う——本関数はcomponentsの入力を
    組み立てるだけで、正規化キーの生成ロジック自体には一切手を入れていない。
    """
    components = extract_teacher_theme_components(text)
    return {
        "theme_components": components,
        "theme_signature": build_theme_signature(components),
        "topic_group_id": build_topic_group(components),
    }


def has_extractable_theme(profile: dict[str, Any]) -> bool:
    """抽出結果が実質的に空（"unclassified"）でないかを確認する。

    topic_group_idが"unclassified"のまま登録すると、無関係なteacher投稿が
    全て同一のtopic_group_idへ合流してしまう（誤った同一テーマ扱い）ため、
    呼び出し側はこれを確認したうえで、trueの場合のみ登録処理へ進むべきである。
    """
    return profile["topic_group_id"] != "unclassified"


def register_proposed_topic_group_from_teacher_post(
    store: dict[str, TopicGroupState],
    text: str,
    source_diversity_tag: str | None = None,
) -> tuple[TopicGroupState, dict[str, Any]] | None:
    """teacher投稿本文1件からtopic_groupを抽出し、"proposed"状態でstoreへ登録する。

    抽出結果が"unclassified"（実質的に何も抽出できなかった）の場合は登録せずNoneを
    返す。get_or_create_topic_group()は既存関数をそのまま呼び出す（今回追加した
    initial_status引数のみ利用、関数本体は無変更）——**同一topic_group_idが既に
    存在する場合は、その既存状態（activeであれproposedであれ）をそのまま返し、
    上書きしない**（get_or_create_topic_group()自体の既存の安全な挙動）。

    戻り値: (TopicGroupState, theme_profile)のタプル。登録不能時はNone。
    """
    profile = build_teacher_theme_profile(text)
    if not has_extractable_theme(profile):
        return None
    state = get_or_create_topic_group(
        store,
        topic_group_id=profile["topic_group_id"],
        theme_signature=profile["theme_signature"],
        source_diversity_tag=source_diversity_tag,
        initial_status="proposed",
    )
    return state, profile
