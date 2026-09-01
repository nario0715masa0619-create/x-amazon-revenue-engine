"""Gadget / Intersection 向けの具体名詞補助辞書と自動具体化ロジック。

背景: 監査ログ集計（ops/reports/generation_spec_refactor_2026-08-18.md）で、
required_fixesの支配的パターンが「具体名詞・具体物・製品カテゴリ不足」だった。
ブランド名・型番は捏造しない方針を維持したまま、
「カテゴリ名」「使用場面名」「比較軸名」「行為名」の4種で具体性を厚くする。

このモジュールは辞書と抽出/補完ロジックのみを持つ。生成そのもの
（draft_generation_templates.py）や監査（external_audit_client.py）には関与しない。
"""

from __future__ import annotations

import re
import unicodedata

# A. 物カテゴリ名
GADGET_CONCRETE_ITEM_KEYWORDS = [
    "イヤホン", "有線", "完全ワイヤレス", "ワイヤレス", "骨伝導", "モバイルバッテリー",
    "充電器", "ケーブル", "USB-C", "ノイキャン", "ケース", "充電ポート",
]
INTERSECTION_CONCRETE_ITEM_KEYWORDS = [
    "軽いバッグ", "バッグ", "スニーカー", "日傘", "モバイルバッテリー", "財布",
    "ポーチ", "バッグの中身", "小物", "持ち物", "充電器", "ケーブル", "バッグインバッグ",
]

# A''. Fashion許可アクセサリカテゴリ語（2026-08-21 production_pipeline_patch追補）
# ブランド名・型番ではなく一般カテゴリ語のみ。本番監査の「具体例が薄い」指摘に対して、
# 原文の「小物使い」という解決軸から自然に導ける範囲でのみ使う。
FASHION_ALLOWED_ACCESSORY_CATEGORIES = [
    "腕時計", "メガネ", "ベルト", "靴", "バッグ", "スニーカー", "レザー小物", "アクセサリー",
]

# A'. 上位概念語（カテゴリの頭語。2026-08-21追補）
# 「有線」「骨伝導」等は"型/方式"であり、それ単体では何の比較かが読み手に伝わらないことが
# teacher reproduction検証（ops/reports/teacher_reproduction_validation_2026-08-21.md）で判明した。
# 型・方式の羅列だけで上位概念語（例:「イヤホン」）が抜け落ちる圧縮を防ぐための必須語辞書。
CATEGORY_HEAD_NOUNS_BY_LAYER: dict[str, list[str]] = {
    "gadget": ["イヤホン", "充電器", "モバイルバッテリー", "ケーブル", "バッテリー"],
}

# B. 使用場面名
USAGE_SCENE_KEYWORDS = [
    "通勤", "街歩き", "出張", "カフェ作業", "長時間移動", "旅行", "外出",
    "打ち合わせ前", "荷物が増える日", "1日歩く日", "仕事帰り", "暑い日", "荷物が多い日",
]

# C. 比較軸名
COMPARISON_AXIS_KEYWORDS = [
    "軽さ", "疲れにくさ", "取り出しやすさ", "充電切れしにくさ", "邪魔しなさ",
    "見た目を崩さないこと", "バッグの中でかさばらないこと", "服装に馴染むこと",
    "持ち歩きやすさ", "ノイズキャンセル", "音漏れ", "装着感", "バッテリー持ち",
    "充電切れ", "かさばらない", "馴染む", "邪魔しない", "見た目を崩さない",
]

# 「見た目側」か「実用側」かの粗い分類（intersection候補の両軸チェックに使う）
_LOOK_AXIS_TERMS = {"見た目を崩さないこと", "服装に馴染むこと", "見た目を崩さない", "馴染む", "邪魔しなさ", "邪魔しない"}
_PRACTICAL_AXIS_TERMS = {
    "軽さ", "疲れにくさ", "取り出しやすさ", "充電切れしにくさ", "バッグの中でかさばらないこと",
    "持ち歩きやすさ", "ノイズキャンセル", "音漏れ", "装着感", "バッテリー持ち", "充電切れ", "かさばらない",
}

# 比較軸の名詞形を、短い締め文に使える形容詞的な短句へ変換する辞書
# （2026-08-19: Intersectionテンプレートを説明文型から列挙+短い締め型へ戻すために追加）
_AXIS_SHORT_PHRASE = {
    "見た目を崩さないこと": "見た目を崩さない",
    "服装に馴染むこと": "服になじむ",
    "邪魔しなさ": "邪魔にならない",
    "見た目を崩さない": "見た目を崩さない",
    "馴染む": "服になじむ",
    "邪魔しない": "邪魔にならない",
    "疲れにくさ": "疲れにくい",
    "軽さ": "軽い",
    "取り出しやすさ": "取り出しやすい",
    "充電切れしにくさ": "充電切れしにくい",
    "充電切れ": "充電切れしにくい",
    "バッグの中でかさばらないこと": "かさばらない",
    "かさばらない": "かさばらない",
    "持ち歩きやすさ": "持ち歩きやすい",
}


def pick_dual_axis_pair(comparison_axes: list[str]) -> tuple[str | None, str | None]:
    """comparison_axesから見た目側1つ・実用側1つを選んで返す（無ければNone）。"""
    look = next((a for a in comparison_axes if a in _LOOK_AXIS_TERMS), None)
    practical = next((a for a in comparison_axes if a in _PRACTICAL_AXIS_TERMS), None)
    return look, practical


def axis_short_phrase(axis: str) -> str:
    """比較軸の名詞形を、短い締め文に使える形容詞的な短句へ変換する（無変換ならそのまま返す）。"""
    return _AXIS_SHORT_PHRASE.get(axis, axis)

# D. 行為名（テンプレート文の動詞に使う。辞書としては保持のみ）
ACTION_KEYWORDS = ["持ち歩く", "取り出す", "充電する", "入れ替える", "比べる", "試す", "絞る", "減らす", "まとめる", "整える"]


def extract_present_items(text: str, keyword_dict: list[str]) -> list[str]:
    """textに実際に含まれる辞書語だけを、辞書の順序で返す（原文優先の抽出）。"""
    return [kw for kw in keyword_dict if kw in text]


def extract_category_head_nouns(text: str, layer_primary: str) -> list[str]:
    """textに実際に含まれる上位概念語（カテゴリの頭語）だけを返す。"""
    return extract_present_items(text, CATEGORY_HEAD_NOUNS_BY_LAYER.get(layer_primary, []))


def enrich_fashion_concrete_categories(
    existing_categories: list[str], count: int = 3
) -> list[str]:
    """FASHION_ALLOWED_ACCESSORY_CATEGORIESから、既存に無い一般カテゴリ語をcount個まで補う。

    ブランド名・型番は生成しない（辞書に載っている一般カテゴリ語のみ）。countは2〜4を想定
    （production_pipeline_patch_2026-08-21.mdの「2〜4語まで」ルールに合わせる）。
    """
    count = max(2, min(count, 4))
    categories = list(existing_categories)
    for candidate in FASHION_ALLOWED_ACCESSORY_CATEGORIES:
        if len(categories) >= count:
            break
        if candidate not in categories:
            categories.append(candidate)
    return categories[:count]


# --------------------------------------------------------------------------
# 表記ゆれ耐性つき照合（2026-08-21追補）
#
# 背景: 「有線イヤホン」という具体名詞が生成文で「有線のイヤホン」のように
# 軽い助詞を挟んで表現されただけで、厳密文字列一致のローカル検証が誤ってrejectと
# 判定していたことがteacher reproduction検証で判明した
# （ops/reports/teacher_reproduction_validation_2026-08-21.md）。
# ここでの正規化は「表層の軽微な差」だけを吸収する。意味的な同義語展開はしない
# （例:「イヤホン」と「音」を一致扱いにしない。「小物」と「持ち物」も一致扱いにしない）。
# --------------------------------------------------------------------------
_URL_PATTERN_FOR_NORMALIZE = re.compile(r"https?://\S+")
_HASHTAG_PATTERN = re.compile(r"#\S+")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_QUOTE_SYMBOLS_PATTERN = re.compile(r"[「」『』\"'‘’“”]")
_MINOR_SYMBOLS_PATTERN = re.compile(r"[・/\-〜～〜~]")
# 複合名詞をつなぐだけの軽助詞のみを対象にする（意味を変える助詞「も」「は」等の
# 一部は文脈依存性が高いため対象から除外し、過度な吸収を避ける）。
_LIGHT_PARTICLES = ("の", "な", "が", "を")


def normalize_surface_text(text: str) -> str:
    """全角/半角・URL・ハッシュタグ・空白・引用符・軽微な記号差を吸収した表層正規化。"""
    text = unicodedata.normalize("NFKC", text)
    text = _URL_PATTERN_FOR_NORMALIZE.sub("", text)
    text = _HASHTAG_PATTERN.sub("", text)
    text = _QUOTE_SYMBOLS_PATTERN.sub("", text)
    text = _MINOR_SYMBOLS_PATTERN.sub("", text)
    text = _WHITESPACE_PATTERN.sub("", text)
    return text.lower()


def normalize_noun_phrase(phrase: str) -> str:
    """normalize_surface_textに加え、複合名詞をつなぐ軽助詞（の/な/が/を）を除去する。

    意味的な同義語展開は行わない（例:「イヤホン」→「音」等の変換はしない）。
    """
    phrase = normalize_surface_text(phrase)
    for particle in _LIGHT_PARTICLES:
        phrase = phrase.replace(particle, "")
    return phrase


def soft_contains_phrase(haystack: str, needle: str) -> tuple[bool, str]:
    """needleがhaystackに含まれるかを3段階で判定する。

    戻り値は (matched, match_level)。match_levelは "exact" / "normalized" / "soft" / "fail"。
    "soft" は軽助詞差のみを吸収した一致で、呼び出し側はログにsoft_match_used=trueを残すこと。
    """
    if not needle:
        return True, "exact"
    if needle in haystack:
        return True, "exact"
    if normalize_surface_text(needle) in normalize_surface_text(haystack):
        return True, "normalized"
    soft_needle = normalize_noun_phrase(needle)
    if soft_needle and soft_needle in normalize_noun_phrase(haystack):
        return True, "soft"
    return False, "fail"


def soft_match_any_phrase(haystack: str, phrases: list[str]) -> tuple[bool, str | None, str]:
    """phrasesのうちいずれかがhaystackにsoft_contains_phrase基準で含まれるか。

    戻り値は (matched, matched_phrase, match_level)。1つも一致しなければ (False, None, "fail")。
    """
    for phrase in phrases:
        matched, level = soft_contains_phrase(haystack, phrase)
        if matched:
            return True, phrase, level
    return False, None, "fail"


def has_required_category_head_noun(draft: str, category_head_nouns: list[str]) -> bool:
    """category_head_nounsが空なら要求なしとしてTrue。1個以上あれば表記ゆれ耐性つきで判定する。"""
    if not category_head_nouns:
        return True
    matched, _, _ = soft_match_any_phrase(draft, category_head_nouns)
    return matched


def has_look_axis(comparison_axes: list[str]) -> bool:
    return any(axis in _LOOK_AXIS_TERMS for axis in comparison_axes)


def has_practical_axis(comparison_axes: list[str]) -> bool:
    return any(axis in _PRACTICAL_AXIS_TERMS for axis in comparison_axes)


def enrich_concrete_items(
    source_text: str,
    layer_primary: str,
    existing_items: list[str],
    min_count: int = 3,
) -> list[str]:
    """原文にある具体物を優先しつつ、layer_primaryの辞書からカテゴリ語で不足分を補う。

    ブランド名・型番は一切生成しない（辞書に載っているカテゴリ語のみを追加する）。
    existing_itemsに既にある語は重複追加しない。
    """
    dict_ = GADGET_CONCRETE_ITEM_KEYWORDS if layer_primary == "gadget" else INTERSECTION_CONCRETE_ITEM_KEYWORDS
    from_source = extract_present_items(source_text, dict_)

    items = list(existing_items)
    for item in from_source:
        if item not in items:
            items.append(item)

    if len(items) < min_count:
        for candidate in dict_:
            if candidate not in items:
                items.append(candidate)
            if len(items) >= min_count:
                break

    return items


def enrich_comparison_axes(
    layer_primary: str,
    existing_axes: list[str],
    min_count: int = 2,
    require_dual_axis: bool = False,
) -> list[str]:
    """比較軸をmin_count以上に補う。intersectionではrequire_dual_axis=Trueで
    見た目側/実用側の両方が最低1つずつ入るよう保証する。
    """
    axes = list(existing_axes)

    if require_dual_axis:
        if not has_look_axis(axes):
            axes.append("見た目を崩さないこと")
        if not has_practical_axis(axes):
            axes.append("疲れにくさ")

    if len(axes) < min_count:
        for candidate in COMPARISON_AXIS_KEYWORDS:
            if candidate not in axes:
                axes.append(candidate)
            if len(axes) >= min_count:
                break

    return axes


def enrich_usage_scenes(existing_scenes: list[str], min_count: int = 1) -> list[str]:
    scenes = list(existing_scenes)
    if len(scenes) < min_count:
        for candidate in USAGE_SCENE_KEYWORDS:
            if candidate not in scenes:
                scenes.append(candidate)
            if len(scenes) >= min_count:
                break
    return scenes
