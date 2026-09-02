"""essay_likeテンプレート（render_essay_reflection、GOV-20260902-ESSAY-LIKE-TEMPLATE-01）の
検証スクリプト。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイルに合わせ、
`python scripts/test_essay_like_template.py`で直接実行できるplain assertベースの
検証スクリプトとする。既存6テンプレートの実装・GenerationSlotsの既存バリデーション
ロジックには一切触れていない（新規テンプレートの単体テストのみ）。

実データ検証について: 検証3の5テキストは、実データ検証（2026-09-02実施、
watched_account_state.jsonに登録済みの6アカウントから実際に取得したteacher投稿、
昇格済み5件のtopic_group）で実際にclassify_source_structure_type()が['essay_like']を
返したものをそのまま固定した回帰フィクスチャである。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from draft_generation_templates import GenerationSlots, GenerationSlotsError, render_draft
from post_generation_pipeline import classify_source_structure_type

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


def test_essay_like_renders_without_error() -> None:
    print("\n=== 検証1: essay_like分類のslotsがGenerationSlotsErrorなくrender_draft()できること ===")
    slots = GenerationSlots(
        source_structure_type=["essay_like"],
        layer_primary="fashion",
        hook="結局よく着ているのは、昔から好きな定番の服ばかり",
        benefit="新しいものも試しつつ、自分の定番を今の気分に合わせて少しずつ更新していく",
        age_angle="40代の服選びは、これくらいのバランスがちょうどいい",
        concrete_items=["Tシャツ", "シャツ", "デニム", "軍パン", "ローファー"],
        reusable_elements=["定番と新しさのバランスを保つ姿勢"],
        must_keep_phrases_or_points=["定番", "バランス"],
    )
    try:
        draft = render_draft(slots)
        _check("no_error_raised", True)
        _check("draft_contains_hook", slots.hook in draft)
        _check("draft_contains_all_concrete_items", all(item in draft for item in slots.concrete_items))
        _check("draft_contains_nuance", slots.reusable_elements[0] in draft)
        _check("draft_contains_closing", slots.age_angle in draft)
    except GenerationSlotsError as e:
        _check("no_error_raised", False, str(e))


def test_essay_like_without_reusable_elements() -> None:
    print("\n=== 検証2: reusable_elements未指定でもrender_draft()できること（nuance行を省略） ===")
    slots = GenerationSlots(
        source_structure_type=["essay_like"],
        layer_primary="fashion",
        hook="観察のフック",
        benefit="ベネフィット",
        age_angle="",
        concrete_items=["アイテムA", "アイテムB"],
        reusable_elements=[],
    )
    try:
        draft = render_draft(slots)
        _check("no_error_raised", True)
        _check("closing_falls_back_to_benefit", slots.benefit in draft)
    except GenerationSlotsError as e:
        _check("no_error_raised", False, str(e))


def test_essay_like_priority_is_lowest() -> None:
    print("\n=== 検証3: essay_likeは他の構造ラベルと共存する場合は優先されないこと（フォールバック挙動の確認） ===")
    slots = GenerationSlots(
        source_structure_type=["essay_like", "how_to"],
        layer_primary="fashion",
        hook="hook",
        benefit="benefit",
        age_angle="age",
        concrete_items=["A", "B"],
        reusable_elements=[],
        key_difference_claim="差がつくポイント",
        where_to_look="見る場所",
        judgment_axis="判断軸",
    )
    draft = render_draft(slots)
    # how_toが優先されるため、essay_like固有の組み立て（hook。items。\nclosing）ではなく
    # render_how_toの出力（claim\nwhere。\naxis）になるはず。
    _check("how_to_takes_priority_over_essay_like", "差がつくポイント" in draft and "見る場所" in draft)


# 実データ検証で実際にessay_likeへ分類された5件（2026-09-02、5監視対象アカウント由来）の
# teacher投稿本文。回帰フィクスチャとして固定する。
_REAL_ESSAY_LIKE_TEXTS = [
    "平野紫耀は現代最強のロールモデル。白T×デニムの王道コーデ 色は3色以内でまとめる ワイドデニムで今っぽさを出す 白Tはジャスト〜ややゆるめ 黒ブーツで全体を締める ゴールドアクセは1点だけ",
    "良かれと思ってやってる男磨き、半分はムダかもしれない。代表的なやってはいけない垢抜け。筋トレだけ頑張る顔・髪・服と同時にやらないと効果が薄い。垢抜ける前に、恋愛アプリや商材に課金。リュック／手帳型スマホケース今日でやめていい",
    "結局よく着ているのは、Tシャツ、シャツ、デニム、軍パン、ローファーみたいな昔から好きな服ばかり。新しいものも試しつつ、自分の定番を今の気分に合わせて少しずつ更新していく。40代の服選びは、たぶんこれくらいのバランスがちょうどいい気がします。",
    "服に奥行きを出す簡単テクニック。よくある失敗コーデといえばオールブラック、オール同じ生地感。結論、生地感のバラつきを意識すれば服装に奥行きができる。例えばニットポロ×カーゴパンツ Tシャツ×デニム スウェットパンツ×シャツ",
    "大人の男性が新宿で服を買うならこの辺りのお店をチェックするのがおすすめ。ビューティ&ユース/ UA トゥモローランド アーバンリサーチ スティーブン・アラン グリーンレーベル エディフィス 伊勢丹メンズ館",
]


def test_real_data_5_candidates_all_essay_like_and_render() -> None:
    print("\n=== 検証4: 実データ5件が引き続きessay_like分類され、essay_likeテンプレートで下書き生成できること ===")
    for i, text in enumerate(_REAL_ESSAY_LIKE_TEXTS, start=1):
        structure_type = classify_source_structure_type(text)
        _check(f"candidate{i}_classified_essay_like", structure_type == ["essay_like"], str(structure_type))

        slots = GenerationSlots(
            source_structure_type=structure_type,
            layer_primary="fashion",
            hook="（検証用hook）",
            benefit="（検証用benefit）",
            age_angle="（検証用age_angle）",
            concrete_items=["item1", "item2"],
            reusable_elements=[],
        )
        try:
            render_draft(slots)
            _check(f"candidate{i}_renders_without_error", True)
        except GenerationSlotsError as e:
            _check(f"candidate{i}_renders_without_error", False, str(e))


if __name__ == "__main__":
    test_essay_like_renders_without_error()
    test_essay_like_without_reusable_elements()
    test_essay_like_priority_is_lowest()
    test_real_data_5_candidates_all_essay_like_and_render()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
