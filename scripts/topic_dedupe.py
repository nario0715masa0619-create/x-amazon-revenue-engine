"""topic_dedupe（投稿済みテーマ除外の中核: theme_signature生成・類似度判定）のpure function層。

学習モードmainlineへ、実投稿済みテーマがsource再利用・言い換え・微差分draftとして再流入する
問題（例: ATH-PRO5MK2×ジム用骨伝導×用途別使い分けテーマがsource_post_id違いで複数回mainline
再生成された）に対応する。AIの重い意味判定には依存せず、ルールベースのキーワード抽出+正規化キー
で判定する（false positiveをある程度許容しても、実投稿済みテーマの再流入防止を優先する設計）。

外部API呼び出しは一切行わない。production scoring/Gate A/thresholds/shipping decisionには
一切触れない。

設計文書: ops/reports/posted_theme_exclusion_design_2026-08-30.md
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 2026-09-02追加（GOV-20260902-TOPIC-GROUP-IDENTITY-UNIFICATION-01）:
# teacher_theme_extraction.pyが使う広いジャンル辞書を正本として合流させる
# （x_api_phase2_classify.py自体への依存はimportのみで、判定ロジック
# _apply_engagement_gate()/_classify_core()には一切触れない。循環import回避のため
# teacher_theme_extraction.pyではなくその上流のx_api_phase2_classify.pyから直接importする
# ——teacher_theme_extraction.py自身がtopic_dedupe.pyをimportしているため）。
from x_api_phase2_classify import (  # noqa: E402
    DECISION_KEYWORDS,
    FASHION_CORE_KEYWORDS_SPECIFIC,
    GADGET_CORE_KEYWORDS,
    _mask_negated_genre_context,
)

# ==============================================================================
# 2026-08-31 EXP-20260831-TOPIC-GROUP-LIFECYCLE-01: 表記ゆれ吸収の強化。
#
# 従来はキーワードの単純substring一致（大文字小文字・記号・和英表記の違いに弱かった）。
# ここでは「マッチング専用の正規化」を挟むことで、以下5パターンの表記ゆれを吸収する
# （テストはtests/test_topic_dedupe.pyまたは同等の検証スクリプトを参照）:
#   1. 語順違い（構造的にJaccard集合比較のため元々吸収済み）
#   2. 送り仮名違い（例: 使い分けている/使い分けてる/使い分け方）
#   3. 型番大文字小文字（例: ATH-PRO5MK2/ath-pro5mk2/Ath-Pro5Mk2）
#   4. カタカナ/英語表記違い（例: ネックバンド/neckband、骨伝導/bone conduction）
#   5. 記号有無（例: ATH-PRO5MK2/ATHPRO5MK2/ATH PRO5MK2）
# 出力されるタグ名自体（"ath-pro5mk2"等）は変更しない——既存のposted_theme_registryに
# 保存済みのtheme_key_terms（タグ名ベース）との比較には影響しない（overlap_ratioは
# タグ名の集合比較であり、マッチング時の正規化は「入力textから同じタグをより確実に
# 検出できるようにする」ためのものであるため）。
# ==============================================================================


def _normalize_for_matching(s: str) -> str:
    """マッチング専用の正規化。大文字小文字・全角/半角・ハイフン/スペース/アンダースコアの
    有無を吸収する（表記ゆれ対策）。タグ名やkeyword辞書の見た目には影響しない
    ——この関数はマッチング時にのみ、textとkeywordの両方へ同じ処理をかけて使う。
    """
    s = unicodedata.normalize("NFKC", s)  # 全角英数・記号を半角へ統一
    s = s.lower()
    s = re.sub(r"[\-\s_・]", "", s)  # ハイフン・スペース・アンダースコア・中黒を除去
    return s


# ==============================================================================
# テーマ構成要素の辞書（ルールベース、gadget layer中心。必要に応じて拡張する）。
# キーは正規化タグ、値はテキスト中に探すキーワード群（表記ゆれ対策の別表記も含める）。
# ==============================================================================
PRODUCT_TERMS: dict[str, list[str]] = {
    "ath-pro5mk2": ["ATH-PRO5MK2", "ATHPRO5MK2", "ATH PRO5MK2"],
    "bone-conduction": ["骨伝導", "bone conduction", "bone-conduction"],
    "neckband": ["ネックバンド", "neckband", "neck band"],
    "airpods-pro": ["AirPods Pro", "AirPodsPro"],
}

USE_CASE_TERMS: dict[str, list[str]] = {
    "gym": ["ジム", "gym"],
    "home": ["自宅", "家で"],
    "meeting": ["会議", "Teams", "打ち合わせ"],
    "commute": ["通勤"],
}

COMPARISON_AXIS_TERMS: dict[str, list[str]] = {
    "lightness": ["軽さ", "軽量", "軽い"],
    "sound-quality": ["音質"],
    "call-quality": ["マイク", "通話", "mic"],
    "fit": ["装着感"],
    "split-use": ["使い分け"],
}

CONTRAST_TERMS: dict[str, list[str]] = {
    "two-device-split": ["2本", "使い分け", "2台"],
    "bone-vs-sealed": ["骨伝導", "密閉型"],
    "priority-reversal": ["より", "重視"],
}

CONCLUSION_TERMS: dict[str, list[str]] = {
    "split-settled": [
        "使い分けている", "使い分けると", "使い分けに落ち着いた", "使い分けてる",
        "使い分け方", "持っている", "2本を",
    ],
    "one-device-narrowed": ["1本に絞", "これに決め", "落ち着いた"],
}

_DIMENSIONS: tuple[tuple[str, dict[str, list[str]]], ...] = (
    ("product", PRODUCT_TERMS),
    ("use_case", USE_CASE_TERMS),
    ("comparison_axis", COMPARISON_AXIS_TERMS),
    ("contrast", CONTRAST_TERMS),
    ("conclusion", CONCLUSION_TERMS),
)


def _all_existing_keywords_normalized(term_map: dict[str, list[str]]) -> set[str]:
    result: set[str] = set()
    for keywords in term_map.values():
        result.update(_normalize_for_matching(kw) for kw in keywords)
    return result


# 2026-09-02追加（GOV-20260902-TOPIC-GROUP-IDENTITY-UNIFICATION-01）: 広いジャンル辞書
# （GADGET_CORE_KEYWORDS/FASHION_CORE_KEYWORDS_SPECIFIC/DECISION_KEYWORDS）由来の語が、
# 既存のPRODUCT_TERMS/COMPARISON_AXIS_TERMSと意味的に重複する場合に新規タグ追加を
# スキップするための参照集合（extract_theme_components()のdocstring参照）。
_EXISTING_PRODUCT_KEYWORDS_NORMALIZED = _all_existing_keywords_normalized(PRODUCT_TERMS)
_EXISTING_AXIS_KEYWORDS_NORMALIZED = _all_existing_keywords_normalized(COMPARISON_AXIS_TERMS)


def extract_theme_components(text: str) -> dict[str, list[str]]:
    """textから、次元別（product/use_case/comparison_axis/contrast/conclusion）に
    マッチしたタグのリストを抽出する。マッチが無い次元は空リストのまま返す。
    大文字小文字・全角半角・ハイフン/スペース/アンダースコアの有無は区別しない
    （_normalize_for_matching()による表記ゆれ吸収）。

    2026-09-02追加（GOV-20260902-TOPIC-GROUP-IDENTITY-UNIFICATION-01）: PRODUCT_TERMS/
    COMPARISON_AXIS_TERMS（ATH-PRO5MK2等、既知の特定型番のみを対象にした狭い辞書）に加え、
    x_api_phase2_classify.pyのGADGET_CORE_KEYWORDS/FASHION_CORE_KEYWORDS_SPECIFIC
    （product次元）・DECISION_KEYWORDS（comparison_axis次元）による広いジャンル語彙も
    productとcomparison_axisへ合流させる。これにより、teacher_theme_extraction.pyが
    生成するtopic_group_idと、evaluate_topic_group_for_mainline()（本関数経由）が
    生成するtopic_group_idが同一の語彙体系に統一される
    （旧: 広いfashion/gadgetジャンルの投稿はここで全て"unclassified"になっていた）。

    **既存のATH-PRO5MK2関連タグとの重複防止（重要な安全策）**: 広い辞書の語が、既存の
    PRODUCT_TERMS/COMPARISON_AXIS_TERMSの語彙と意味的に重複する場合（例:
    GADGET_CORE_KEYWORDSの「骨伝導」は既にPRODUCT_TERMS["bone-conduction"]の同義語として
    登録済み）、新規タグとしては追加しない（_existing_narrow_keywords()で判定）。これにより、
    ATH-PRO5MK2×ジム用骨伝導系の投稿から抽出されるtheme_signature/topic_groupは、本変更の
    前後で完全に同一の文字列のまま変化しない（既存のposted_theme_registry照合・分裂検出の
    既知ケースを壊さない）。真に新しい語彙（fashion系のコーデ/デニム等）のみが新規タグとして
    追加される。

    否定文脈（「ガジェットには興味ゼロ」等）の扱いは、既存のGADGET_CORE_KEYWORDS/
    FASHION_CORE_KEYWORDS_SPECIFIC/DECISION_KEYWORDS判定と同じく
    x_api_phase2_classify._mask_negated_genre_context()でマスクしたテキストに対して行う
    （既存のPRODUCT_TERMS等の狭い辞書側はこれまでどおり否定文脈マスクなしのまま、
    挙動を変更しない）。
    """
    normalized_text = _normalize_for_matching(text)
    components: dict[str, list[str]] = {}
    for dim_name, term_map in _DIMENSIONS:
        matched = []
        for tag, keywords in term_map.items():
            if any(_normalize_for_matching(kw) in normalized_text for kw in keywords):
                matched.append(tag)
        components[dim_name] = matched

    genre_text = _mask_negated_genre_context(text)
    for kw in GADGET_CORE_KEYWORDS + FASHION_CORE_KEYWORDS_SPECIFIC:
        if kw in genre_text and _normalize_for_matching(kw) not in _EXISTING_PRODUCT_KEYWORDS_NORMALIZED:
            if kw not in components["product"]:
                components["product"].append(kw)
    for kw in DECISION_KEYWORDS:
        if kw in genre_text and _normalize_for_matching(kw) not in _EXISTING_AXIS_KEYWORDS_NORMALIZED:
            if kw not in components["comparison_axis"]:
                components["comparison_axis"].append(kw)

    return components


def build_theme_signature(components: dict[str, list[str]]) -> str:
    """theme componentsから、mainlineで再利用判定できる一貫した正規化キーを組み立てる。
    各次元の先頭タグ（複数マッチ時は辞書順で先頭）を"__"で連結する。空の次元はスキップする。
    例: "ath-pro5mk2__bone-conduction__gym__lightness__two-device-split__split-settled"
    """
    parts = []
    for dim_name, _ in _DIMENSIONS:
        tags = sorted(components.get(dim_name, []))
        if tags:
            parts.append("-".join(tags) if dim_name == "product" else tags[0])
    return "__".join(parts) if parts else "unclassified"


def build_topic_group(components: dict[str, list[str]]) -> str:
    """cooldown判定用の粗いグルーピングキー。product + comparison_axisの主要タグのみで構成し、
    theme_signatureより粗い粒度にする（wording差やconclusion差では別グループにしない）。
    """
    product_tags = sorted(components.get("product", []))
    axis_tags = sorted(components.get("comparison_axis", []))
    parts = []
    if product_tags:
        parts.append("-".join(product_tags))
    if axis_tags:
        parts.append("-".join(axis_tags))
    return "__".join(parts) if parts else "unclassified"


def theme_component_overlap_ratio(a: dict[str, list[str]], b: dict[str, list[str]]) -> float:
    """2つのtheme componentsの重なり度合い（Jaccard風）を0.0〜1.0で返す。
    全次元のタグ集合をまとめて比較する。両方空なら0.0を返す。
    """
    set_a: set[str] = set()
    set_b: set[str] = set()
    for dim_name, _ in _DIMENSIONS:
        set_a |= {f"{dim_name}:{t}" for t in a.get(dim_name, [])}
        set_b |= {f"{dim_name}:{t}" for t in b.get(dim_name, [])}
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    intersection = set_a & set_b
    return len(intersection) / len(union)


def build_theme_profile(texts: list[str]) -> dict[str, Any]:
    """draft_text等の複数テキスト（例: source_full_text + draft_text）をまとめてtheme
    componentsを抽出し、theme_signature/topic_group/componentsを1つにまとめて返す。
    """
    combined = "\n".join(t for t in texts if t)
    components = extract_theme_components(combined)
    return {
        "theme_components": components,
        "theme_signature": build_theme_signature(components),
        "topic_group": build_topic_group(components),
    }
