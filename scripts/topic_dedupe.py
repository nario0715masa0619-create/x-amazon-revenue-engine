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

from typing import Any

# ==============================================================================
# テーマ構成要素の辞書（ルールベース、gadget layer中心。必要に応じて拡張する）。
# キーは正規化タグ、値はテキスト中に探すキーワード群。
# ==============================================================================
PRODUCT_TERMS: dict[str, list[str]] = {
    "ath-pro5mk2": ["ATH-PRO5MK2", "ath-pro5mk2"],
    "bone-conduction": ["骨伝導"],
    "neckband": ["ネックバンド"],
    "airpods-pro": ["AirPods Pro"],
}

USE_CASE_TERMS: dict[str, list[str]] = {
    "gym": ["ジム"],
    "home": ["自宅"],
    "meeting": ["会議", "Teams", "通話"],
    "commute": ["通勤"],
}

COMPARISON_AXIS_TERMS: dict[str, list[str]] = {
    "lightness": ["軽さ", "軽量", "軽い"],
    "sound-quality": ["音質"],
    "call-quality": ["マイク", "通話"],
    "fit": ["装着感"],
    "split-use": ["使い分け"],
}

CONTRAST_TERMS: dict[str, list[str]] = {
    "two-device-split": ["2本", "使い分け"],
    "bone-vs-sealed": ["骨伝導", "密閉型"],
    "priority-reversal": ["より", "重視"],
}

CONCLUSION_TERMS: dict[str, list[str]] = {
    "split-settled": ["使い分けている", "使い分けると", "使い分けに落ち着いた", "持っている", "2本を"],
    "one-device-narrowed": ["1本に絞", "これに決め", "落ち着いた"],
}

_DIMENSIONS: tuple[tuple[str, dict[str, list[str]]], ...] = (
    ("product", PRODUCT_TERMS),
    ("use_case", USE_CASE_TERMS),
    ("comparison_axis", COMPARISON_AXIS_TERMS),
    ("contrast", CONTRAST_TERMS),
    ("conclusion", CONCLUSION_TERMS),
)


def extract_theme_components(text: str) -> dict[str, list[str]]:
    """textから、次元別（product/use_case/comparison_axis/contrast/conclusion）に
    マッチしたタグのリストを抽出する。マッチが無い次元は空リストのまま返す。
    """
    components: dict[str, list[str]] = {}
    for dim_name, term_map in _DIMENSIONS:
        matched = []
        for tag, keywords in term_map.items():
            if any(kw in text for kw in keywords):
                matched.append(tag)
        components[dim_name] = matched
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
