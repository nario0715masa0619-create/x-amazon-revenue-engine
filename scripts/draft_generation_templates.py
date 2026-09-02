"""source_structure_type別の初稿生成テンプレート（自由作文の禁止）。

背景: 監査ログ集計（ops/reports/generation_spec_refactor_2026-08-18.md）で、
「候補の意味だけ抽出して自然な新規文に再構成する」自由作文が、元投稿の勝ち構造
（列挙・比較軸・優先順位逆転の骨格）を消してしまうことが分かった。
このモジュールは、Claude Codeが埋めるのは「スロットの中身（プロース）」までとし、
「骨格（どこに何を置くか）」はコードが強制する、という役割分担にする。

各テンプレート関数は GenerationSlots を受け取り、決定的な組み立てロジックで
文字列を返す（LLM呼び出しは行わない。ロジックはこのファイル内で完結する）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from concrete_item_enrichment import (
    has_look_axis,
    has_practical_axis,
    pick_dual_axis_pair,
    axis_short_phrase,
    soft_contains_phrase,
)


class GenerationSlotsError(ValueError):
    pass


@dataclass
class GenerationSlots:
    """初稿生成前に必ず埋める強制入力スロット（指示書5章、gadget/intersection追補済み）。

    埋まらない場合は初稿生成をしない（__post_init__でエラーにする）。
    """

    source_structure_type: list[str]
    layer_primary: str  # fashion / gadget / intersection
    hook: str
    benefit: str
    age_angle: str
    concrete_items: list[str]  # 最低2個（gadget/intersectionは最低3個）
    reusable_elements: list[str]
    must_keep_phrases_or_points: list[str] = field(default_factory=list)
    must_avoid_patterns: list[str] = field(default_factory=list)

    # --- gadget/intersection追補（2026-08-18）: 具体名詞不足対策 ---
    usage_scenes: list[str] = field(default_factory=list)  # 使用場面名（gadget最低1/intersection最低1）
    comparison_axes: list[str] = field(default_factory=list)  # 比較軸名（gadget/intersectionとも最低2）
    required_concrete_density: int = 2  # 120文字あたりの具体物最低数の目安（バリデーション補助）
    must_include_categories: list[str] = field(default_factory=list)  # 明示的に含めるべきカテゴリ語

    # --- gadget追補（2026-08-21）: 上位概念語保持対策 ---
    # 「有線」「骨伝導」等は型/方式であり、上位概念語（例:「イヤホン」）が抜け落ちると
    # 何の比較かが読み手に伝わらなくなる（teacher_reproduction_validation_2026-08-21で判明）。
    category_head_nouns: list[str] = field(default_factory=list)  # gadgetは最低1個必須

    # --- gadget追補（2026-08-21 production_pipeline_patch）: minimal/rich二段スロット ---
    # 先生原文にusage_scenes/comparison_axesの記述が無い場合、rich基準を満たすには
    # 捏造が必要になってしまう（production_selection_fashion_gadget_2026-08-21.mdで
    # 実際にGenerationSlotsErrorとして顕在化した）。slot_mode="gadget_minimal"のときは
    # usage_scenes/comparison_axes/concrete_items>=3の必須要件を緩める（下記__post_init__）。
    # None/"gadget_rich"のときは既存どおりの厳格な要件を維持する（後方互換）。
    slot_mode: str | None = None  # "gadget_minimal" | "gadget_rich" | None

    # --- fashion追補（2026-08-21）: 見出し断定型対策 ---
    # article_title_like（記事見出し調）の先生原文は、how_toの「悩み→解決軸」より
    # 「一文で言い切る」断定リズムが勝ち要素であることがteacher reproduction検証で判明した。
    headline_anchor: str | None = None  # 冒頭に置く具体起点（例: 服の組み合わせ）

    # --- fashion追補（2026-08-21 production_pipeline_patch）: 具体アクセサリカテゴリ ---
    # ブランド名・型番を使わず、腕時計/メガネ等の一般カテゴリ語で本番監査の
    # 「具体例が薄い」指摘に対応するための追加スロット（2〜4語を想定）。
    accessory_categories: list[str] = field(default_factory=list)

    # --- priority_reversal専用 ---
    past_state: str | None = None  # 「昔は/以前は」に相当する内容
    now_reason: str | None = None  # 逆転が40代で自然になった理由

    # --- comparison専用 ---
    comparison_targets: list[str] | None = None  # 比較対象（未指定ならconcrete_itemsを使う）
    comparison_axis: str | None = None  # 争点
    conclusion_or_choice: str | None = None  # 結論/選び方

    # --- experience_review専用 ---
    trial_trace: str | None = None  # 試行の痕跡
    selection_criterion: str | None = None  # 選ぶ基準

    # --- how_to専用 ---
    key_difference_claim: str | None = None  # 差がつくポイントの断言
    where_to_look: str | None = None  # 具体的に見る/選ぶ場所
    judgment_axis: str | None = None  # 読後に使える判断軸

    def __post_init__(self) -> None:
        if self.layer_primary not in ("fashion", "gadget", "intersection"):
            raise GenerationSlotsError(f"layer_primaryが不正です: {self.layer_primary}")
        if not self.source_structure_type:
            raise GenerationSlotsError("source_structure_typeが空です")

        is_gadget_minimal = self.layer_primary == "gadget" and self.slot_mode == "gadget_minimal"

        if is_gadget_minimal:
            min_items = 1  # 比較両端（例: 有線/骨伝導）が最低1個あれば良い
        else:
            min_items = 3 if self.layer_primary in ("gadget", "intersection") else 2
        if len(self.concrete_items) < min_items:
            raise GenerationSlotsError(
                f"concrete_itemsは{self.layer_primary}"
                f"{'（gadget_minimal）' if is_gadget_minimal else ''}"
                f"で最低{min_items}個必須です"
                f"（現在{len(self.concrete_items)}個）。候補抽出が曖昧ならmanual_reviewへ戻してください。"
            )

        if self.layer_primary == "gadget":
            # 上位概念語はminimal/richどちらでも必須（何の比較かが伝わらなくなるため）
            if len(self.category_head_nouns) < 1:
                raise GenerationSlotsError(
                    "gadget候補はcategory_head_nouns（上位概念語。例: イヤホン/充電器）が最低1個必須です"
                )
            if not is_gadget_minimal:
                if len(self.comparison_axes) < 2:
                    raise GenerationSlotsError(
                        f"gadget候補はcomparison_axesが最低2個必須です（現在{len(self.comparison_axes)}個）。"
                        "原文にusage_scenes/comparison_axesの記述が無い場合はslot_mode="
                        "'gadget_minimal'を使ってください（捏造せずに済みます）。"
                    )
                if len(self.usage_scenes) < 1:
                    raise GenerationSlotsError(
                        "gadget候補はusage_scenesが最低1個必須です。原文に記述が無い場合は"
                        "slot_mode='gadget_minimal'を使ってください（捏造せずに済みます）。"
                    )

        if self.layer_primary == "intersection":
            if len(self.usage_scenes) < 1:
                raise GenerationSlotsError("intersection候補はusage_scenesが最低1個必須です")
            if len(self.comparison_axes) < 2:
                raise GenerationSlotsError(
                    f"intersection候補はcomparison_axesが最低2個必須です（現在{len(self.comparison_axes)}個）"
                )
            if not (has_look_axis(self.comparison_axes) and has_practical_axis(self.comparison_axes)):
                raise GenerationSlotsError(
                    "intersection候補はcomparison_axesに見た目側・実用側の両方が必須です"
                )


def _bullets(items: list[str], limit: int = 5) -> str:
    return "\n".join(f"・{item}" for item in items[:limit])


def render_listicle(slots: GenerationSlots) -> str:
    """導入1文 + 具体物列挙(2個以上) + 締め1文。"""
    body = _bullets(slots.concrete_items)
    return f"{slots.hook}\n{body}\n{slots.benefit}"


def render_comparison(slots: GenerationSlots) -> str:
    """比較カテゴリ(最大3) + 使用場面 + 比較軸(2個以上) を前半に凝縮し、
    『何を重視するなら何を見るか』の判断軸で締める（gadget向け、2026-08-19改訂）。

    ブランド名・型番は入れない。カテゴリ名+比較軸+使用場面の組み合わせで
    十分な具体性とみなす方針（audit_criteria_adjustment_2026-08-19）に合わせ、
    それらを1文目に必ず同居させる構成にした。

    2026-08-21追補: 「有線」「骨伝導」等の型/方式名だけで押し切ると、上位概念語
    （例:「イヤホン」）が抜け落ち、"何の比較か"の輪郭が薄くなることがteacher
    reproduction検証で判明した。category_head_nounsが渡された場合、比較対象の
    型/方式名に上位概念語が既に含まれていなければ自動的に付け足す。

    2026-08-21 gadget_minimal_patch追補: 従来age_angleが本文組み立てに一切
    使われておらず、40代視点が本文から消失してreject（structure_preserved=false）
    になるケースが実測で確認された（production_selection_gadget_only_2026-08-21.md）。
    age_angleが渡された場合、比較の問いに短く添える形で必ず1回だけ反映する
    （長い内省文にはしない。comparison question/endpoints/category_head_nounsより
    優先して膨らませない）。
    """
    targets = (slots.comparison_targets or slots.concrete_items)[:3]
    targets_text = "、".join(targets)

    category_noun = slots.category_head_nouns[0] if slots.category_head_nouns else None
    if category_noun and not soft_contains_phrase(targets_text, category_noun)[0]:
        targets_text = f"{targets_text}の{category_noun}"

    scenes_text = "、".join(slots.usage_scenes)
    axes_text = "、".join(slots.comparison_axes)
    # comparison_axisは「結局どれが一番か」という比較の争点そのものを表す文で、
    # scenes/axesの有無に関わらず必ず残す（比較構造そのものを示すマーカーのため）。
    # comparison_axis未指定時は、category_head_nounがあれば原文由来の「結局どの{category_noun}が
    # 一番使えるのか」型に近づける（上位概念語をここでも二重に保持する）。
    if slots.comparison_axis:
        axis_intro = slots.comparison_axis
    elif category_noun:
        axis_intro = f"結局どの{category_noun}が一番使えるのか"
    else:
        axis_intro = "結局どれが一番使えるのか"

    # age_angle反映: targets_text/axis_introの時点で既に含まれていなければ、
    # 問いの直前に「{age_angle}で、」を1回だけ短く添える。
    if slots.age_angle and not soft_contains_phrase(f"{targets_text}{axis_intro}", slots.age_angle)[0]:
        axis_intro = f"{slots.age_angle}で、{axis_intro}"

    if scenes_text and axes_text:
        first_line = f"{targets_text}。{axis_intro}。{scenes_text}で選ぶなら、見るのは{axes_text}。"
    elif axes_text:
        first_line = f"{targets_text}。{axis_intro}。見るのは{axes_text}。"
    else:
        first_line = f"{targets_text}。{axis_intro}"

    conclusion = slots.conclusion_or_choice or slots.benefit
    return f"{first_line}\n{conclusion}"


def render_priority_reversal(slots: GenerationSlots) -> str:
    """短い逆転主張 + 具体項目3個以上の列挙 + 見た目/実用の短い締め1文（列挙型、2026-08-19改訂）。

    旧版は「〜のような場面ほど、これが効く」等の説明調つなぎ文を挟んでいたが、
    これが外部監査でarticle_intro_risk上昇の原因になっていた
    （ops/reports/concrete_item_enrichment_2026-08-18.md参照）。
    説明を増やす方向ではなく「逆転主張+列挙+短い締め」という元のlisticle構造へ寄せる。

    source_structure_typeに"listicle"も含まれる場合（intersection候補で多い）、
    具体項目は箇条書きで残す（列挙構造が消えるとローカルバリデーション・
    外部監査の両方でstructure_preserved違反になるため）。
    """
    if "listicle" in slots.source_structure_type:
        items_block = _bullets(slots.concrete_items)
    else:
        items_block = "、".join(slots.concrete_items)

    # 使用場面は逆転主張の一部として短く織り込む（独立した説明文にしない）
    scene_fragment = f"{slots.usage_scenes[0]}では" if slots.usage_scenes else ""
    opening = f"40代になると、{scene_fragment}おしゃれだけでは足りない。今は{slots.hook}。"

    look_axis, practical_axis = pick_dual_axis_pair(slots.comparison_axes)
    if look_axis and practical_axis:
        closing = f"{axis_short_phrase(look_axis)}、{axis_short_phrase(practical_axis)}。"
    else:
        closing = slots.now_reason or slots.age_angle

    return f"{opening}\n{items_block}\n{closing}"


def render_experience_review(slots: GenerationSlots) -> str:
    """実体験の前提 + 比較や試行の痕跡 + 何を基準に選ぶようになったか。"""
    trial = slots.trial_trace or (
        "、".join(slots.concrete_items) + "を実際に使って比べた"
    )
    criterion = slots.selection_criterion or slots.benefit
    return f"{slots.hook}。{trial}。\n{criterion}"


def render_how_to(slots: GenerationSlots) -> str:
    """差がつくポイントの断言 + 具体的な見る場所/選ぶ場所 + 読後に使える判断軸。"""
    claim = slots.key_difference_claim or slots.hook
    where = slots.where_to_look or "、".join(slots.concrete_items)
    axis = slots.judgment_axis or slots.benefit
    return f"{claim}\n{where}。\n{axis}"


def render_headline_assertion_fashion(slots: GenerationSlots) -> str:
    """見出し断定型（fashion専用、2026-08-21追加）。

    背景: article_title_like（【】記事見出し調）の先生原文は、how_toの
    「悩み/差分→解決軸→具体物」という説明的な型に落とすと、原文が本来持っていた
    「一文で言い切る」断定リズムと感情トリガーが薄まることがteacher reproduction
    検証（ops/reports/teacher_reproduction_validation_2026-08-21.md）で判明した。

    この関数は「悩みの説明」を挟まない。具体起点（headline_anchor）を先に置き、
    差がつくポイントを解決軸1つに絞って断定するだけの、原文に近い短さで組み立てる。

    2026-08-21パッチ追補: 最初の版（起点+断定のみ）はrhythmは保てたが、実監査で
    emotional_trigger_preservedが改善しないことが判明した
    （teacher_reproduction_patch_2026-08-21.md）。「同じ状態でも日によって差が出る」
    という対比（benefit由来）を1文だけ足すことで、悩み説明を挟まずに憧れ/期待の
    感情トリガーを補う。benefitは「〜する/〜な」等、「日」に続けられる状態句で
    渡すこと（例:「着映えする」。「着映えが変わる」のような動詞句は文法上つながらない）。

    2026-08-21 production_pipeline_patch追補: 本番監査（品質監査）はfidelity監査とは
    別基準で「具体アクセサリ例が薄い」という指摘を繰り返した
    （production_selection_fashion_gadget_2026-08-21.md）。axis自体を安易に長くする
    （例:「腕時計やメガネなどの小物」）と再度revise になったため、断定文はそのまま維持し、
    accessory_categoriesがあれば独立した最後の1文としてカテゴリ名を列挙する形にした
    （悩み説明ではなく列挙なので、断定リズムを壊さない）。
    """
    anchor = slots.headline_anchor or (slots.concrete_items[0] if slots.concrete_items else slots.hook)
    axis = slots.key_difference_claim or slots.judgment_axis or (
        slots.concrete_items[-1] if slots.concrete_items else slots.benefit
    )
    age_fragment = f"{slots.age_angle}でも、" if slots.age_angle else ""
    contrast_fragment = f"{slots.benefit}日と、そうじゃない日がある。" if slots.benefit else ""
    accessory_fragment = ""
    if slots.accessory_categories:
        cats = "、".join(slots.accessory_categories[:4])
        accessory_fragment = f"{cats}みたいな小さい部分で印象が整う。"
    return f"{anchor}。{age_fragment}{contrast_fragment}差がつくのは{axis}。{accessory_fragment}".rstrip()


def render_single_claim(slots: GenerationSlots) -> str:
    """主張を先に置く + 具体物で補う根拠 + 40代視点で納得感。"""
    items = "、".join(slots.concrete_items)
    return f"{slots.hook}。{items}。{slots.age_angle}"


def render_essay_reflection(slots: GenerationSlots) -> str:
    """essay_like（既存6テンプレートのいずれの検出条件にも該当しない、感想・所感型の
    元投稿）向けテンプレート（2026-09-02追加、GOV-20260902-ESSAY-LIKE-TEMPLATE-01）。

    背景: 広域収集（fashion）経由のteacher投稿を実際に`classify_source_structure_type()`
    へ通したところ、複数件が`essay_like`（列挙・比較・優先順位逆転・実体験・how_toの
    いずれの検出語にも一致しない、フォールバックラベル）に分類され、既存の
    `_TEMPLATE_DISPATCH`に対応するテンプレートが無いため`render_draft()`が
    `GenerationSlotsError`で下書き生成を一切ブロックしていた。

    骨格: 観察・結論の起点（hook）+ 具体物での裏付け（concrete_items）+
    任意の一段の含み（reusable_elementsの先頭1件、あれば）+ 年代視点の結び
    （age_angleまたはbenefit）。他の全テンプレートと同じく、Claude Codeが埋めるのは
    スロットの中身のみで、骨格の組み立てロジック自体はこの関数が決定的に行う
    （自由作文はしない）。
    """
    items = "、".join(slots.concrete_items)
    nuance = slots.reusable_elements[0] if slots.reusable_elements else None
    closing = slots.age_angle or slots.benefit
    if nuance:
        return f"{slots.hook}。{items}。\n{nuance}。\n{closing}"
    return f"{slots.hook}。{items}。\n{closing}"


_TEMPLATE_DISPATCH = {
    "priority_reversal": render_priority_reversal,
    "listicle": render_listicle,
    "comparison": render_comparison,
    "experience_review": render_experience_review,
    "how_to": render_how_to,
    "single_claim": render_single_claim,
    "essay_like": render_essay_reflection,
}

# 複数ラベルがある場合にどれを優先してテンプレート選択するか
# （intersection候補で優先順位逆転+列挙が両方立つ場合、逆転構造を骨格の主軸にする等）。
# essay_likeは他の全ラベルが不一致だった場合のフォールバックラベルのため最後尾に置く
# （2026-09-02追加）。
_TEMPLATE_PRIORITY_ORDER = [
    "priority_reversal",
    "listicle",
    "comparison",
    "experience_review",
    "how_to",
    "single_claim",
    "essay_like",
]


def render_draft(slots: GenerationSlots) -> str:
    """slots.source_structure_typeに応じて、優先順位に従いテンプレートを1つ選んで描画する。

    2026-08-21追補: layer_primary=fashion かつ source_structure_typeに
    article_title_like が含まれる場合、既存のhow_to優先ロジックより前に
    render_headline_assertion_fashion()を優先する（見出し断定の勢いを
    how_toの説明的な型で薄めないため。詳細: teacher_reproduction_patch_2026-08-21.md）。
    """
    if slots.layer_primary == "fashion" and "article_title_like" in slots.source_structure_type:
        return render_headline_assertion_fashion(slots)

    for structure_type in _TEMPLATE_PRIORITY_ORDER:
        if structure_type in slots.source_structure_type:
            return _TEMPLATE_DISPATCH[structure_type](slots)
    raise GenerationSlotsError(
        f"対応するテンプレートがありません: {slots.source_structure_type}"
    )
