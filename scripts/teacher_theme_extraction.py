"""teacher投稿（pre_teacher_candidate）本文から、topic_group自動登録用のテーマ要素を
機械的に抽出するpure function層。

**再利用方針（2026-09-02改訂、GOV-20260902-TOPIC-GROUP-IDENTITY-UNIFICATION-01）**:
componentsの抽出・theme_signature/topic_group_idの組み立てのいずれも、
topic_dedupe.extract_theme_components()/build_theme_signature()/build_topic_group()
（既存、正本）をそのまま使う。

従来、本モジュールは独自に「商品名・カテゴリ語（GADGET_CORE_KEYWORDS/FASHION_CORE_
KEYWORDS_SPECIFIC）・訴求切り口（DECISION_KEYWORDS）をproduct/comparison_axisへ合流
させる」処理を複製実装していたが、これは`evaluate_topic_group_for_mainline()`が使う
topic_dedupe.build_theme_profile()側には反映されておらず、同じteacher投稿本文から
本モジュール経由（"proposed"登録時）とmainline候補判定経由（昇格後の再評価時）とで
**別々のtopic_group_idが計算されてしまう**という実データで確認された不整合の原因になって
いた（詳細: ops/reports/以下のtopic_group identity統合タスクの報告参照）。

この不整合を解消するため、広いジャンル辞書によるproduct/comparison_axis拡張ロジック
自体をtopic_dedupe.extract_theme_components()側へ統合し（同モジュールが
x_api_phase2_classify.GADGET_CORE_KEYWORDS/FASHION_CORE_KEYWORDS_SPECIFIC/
DECISION_KEYWORDSを直接importして合流させるようになった）、本モジュールは
topic_dedupe.extract_theme_components()をそのまま呼ぶだけの薄いラッパーへ変更した。
これにより、"proposed"登録時と昇格後のmainline候補判定時とで、常に同一の
topic_group_id計算経路を通ることが保証される（実装が2箇所に分かれていた状態を解消）。

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

_COMPONENT_DIMENSIONS = ("product", "use_case", "comparison_axis", "contrast", "conclusion")


def extract_teacher_theme_components(text: str) -> dict[str, list[str]]:
    """teacher投稿本文から、topic_dedupe.build_theme_signature()/build_topic_group()へ
    渡せる形のcomponents辞書（product/use_case/comparison_axis/contrast/conclusion）を
    組み立てる。

    2026-09-02改訂: topic_dedupe.extract_theme_components()（既に広いジャンル辞書との
    合流ロジックを含む、正本）をそのまま呼び出すだけの薄いラッパー。以前ここにあった
    独自の合流ロジックは削除し、evaluate_topic_group_for_mainline()側と完全に同一の
    抽出結果を返すことを保証する。
    """
    return extract_theme_components(text)


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
