"""外部AI監査（Claude Code = 生成、外部AI = 監査）の入出力スキーマ定義。

このファイルはデータ構造とバリデーションのみを持つ。
判定基準そのもの（何がpassでrejectか）は外部AI側のプロンプト
（external_audit_client.py の _AUDIT_SYSTEM_PROMPT）に記述する。
詳細方針: ops/reports/external_audit_policy_2026-08-18.md

layer_primary別の「十分な具体性」の定義（2026-08-19、audit_criteria_adjustment）:
    - fashion: ファッション具体物 + 40代視点 + 見え方の差分 + 記事紹介臭の低さ
    - gadget: カテゴリ名 + 比較軸 + 使用場面 + 実体験or選定基準
      （ブランド名・型番は捏造禁止方針のため不要。要求しない）
    - intersection: 見た目側語 + 実用側語 + 具体物3個以上 + 列挙構造 + 優先順位逆転or両立課題
      （簡潔な列挙構造を記事紹介文体と混同しない。説明文の短さ自体は減点対象にしない）
実際の判定文言は external_audit_client.py の _AUDIT_SYSTEM_PROMPT に実装している。
詳細: ops/reports/audit_criteria_adjustment_2026-08-19.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 段階B（候補選定）で必ず1つ以上付与する元投稿の構造ラベル。
STRUCTURE_TYPES = [
    "listicle",
    "comparison",
    "priority_reversal",
    "experience_review",
    "how_to",
    "single_claim",
    "news_like",
    "thread_like",
    "essay_like",
    # 2026-08-21追加: 【】記事見出し調＋URL/媒体タグの先生原文用ラベル。
    # classify_source_structure_type()（post_generation_pipeline.py）が新たに
    # 出力するようになったため、Candidateのバリデーションにも追加する必要があった。
    "article_title_like",
]

VERDICTS = ("pass", "revise", "reject")
RISK_LEVELS = ("low", "medium", "high")
LAYER_FITS = ("fashion", "gadget", "intersection", "unclear")

_TARGET_ACCOUNT_AXIS = "40代ファッション×ガジェット"
_REVIEW_GOAL = "日記化防止 / 構造保持 / 勝ち筋維持"


class AuditSchemaError(ValueError):
    pass


@dataclass
class Candidate:
    """段階B（候補選定）でClaude Codeが構造化する候補情報。"""

    candidate_id: str
    layer_primary: str  # fashion / gadget / intersection
    source_post_id: str
    source_full_text: str
    source_structure_type: list[str]
    hook: str
    benefit: str
    age_40s_angle: str  # 「40代視点」
    reusable_elements: list[str]
    prohibited_elements: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.layer_primary not in ("fashion", "gadget", "intersection"):
            raise AuditSchemaError(f"layer_primaryが不正です: {self.layer_primary}")
        if not self.source_structure_type:
            raise AuditSchemaError("source_structure_typeは1つ以上必須です")
        unknown = [s for s in self.source_structure_type if s not in STRUCTURE_TYPES]
        if unknown:
            raise AuditSchemaError(f"未知のsource_structure_type: {unknown}")


@dataclass
class AuditRequest:
    """段階D（外部AI監査）への入力ペイロード。"""

    layer_primary: str
    source_post_id: str
    source_full_text: str
    source_structure_type: list[str]
    source_reusable_elements: list[str]
    generated_draft: str
    target_account_axis: str = _TARGET_ACCOUNT_AXIS
    review_goal: str = _REVIEW_GOAL
    # 2026-08-21 gadget_minimal_patch追補: slot_mode（"gadget_minimal"/"gadget_rich"）を
    # 監査官に明示的に渡す。渡さないと、原文が薄いminimal候補にもrich相当の具体性
    # （使用場面・比較軸・ブランド名等）を要求してしまう
    # （production_selection_gadget_only_2026-08-21.mdで実際に発生）。
    slot_mode: str | None = None

    def to_prompt_payload(self) -> dict[str, Any]:
        return {
            "layer_primary": self.layer_primary,
            "source_post_id": self.source_post_id,
            "source_full_text": self.source_full_text,
            "source_structure_type": self.source_structure_type,
            "source_reusable_elements": self.source_reusable_elements,
            "generated_draft": self.generated_draft,
            "target_account_axis": self.target_account_axis,
            "review_goal": self.review_goal,
            "slot_mode": self.slot_mode,
        }


@dataclass
class AuditResult:
    """段階D（外部AI監査）からの出力。外部AIは常にこの形式のJSONを返す想定。"""

    verdict: str
    score_overall: int
    structure_preserved: bool
    essay_risk: str
    article_intro_risk: str
    ad_like_risk: str
    layer_fit: str
    kept_strengths: list[str]
    problems: list[str]
    required_fixes: list[str]
    one_line_reason: str
    audited_by: str = "unknown"

    @classmethod
    def from_json(cls, data: dict[str, Any], audited_by: str = "unknown") -> "AuditResult":
        validate_audit_result(data)
        return cls(
            verdict=data["verdict"],
            score_overall=int(data["score_overall"]),
            structure_preserved=bool(data["structure_preserved"]),
            essay_risk=data["essay_risk"],
            article_intro_risk=data["article_intro_risk"],
            ad_like_risk=data["ad_like_risk"],
            layer_fit=data["layer_fit"],
            kept_strengths=list(data.get("kept_strengths") or []),
            problems=list(data.get("problems") or []),
            required_fixes=list(data.get("required_fixes") or []),
            one_line_reason=data.get("one_line_reason", ""),
            audited_by=audited_by,
        )


# --------------------------------------------------------------------------
# Gate A / Gate B 二段監査（2026-08-23 audit_gate_split_redesign追加）
#
# 背景: 従来のAuditResult（1回のLLM呼び出しでverdict/scoreを同時に返す設計）は、
# 「捏造・構造崩壊のような出してはいけない違反」と「もう少し良くできる、という
# 品質上の微調整」を同じpass/revise/rejectへ圧縮していた。そのため、正規化中間層が
# forbidden invention要求を0件に抑えられているsafe案でも、監査モデルの品質面での
# 気分次第でrevise→revise→discardに落ちる問題が繰り返し観測された
# （production_selection_restart_2026-08-23.md等）。
#
# Gate A（hard_gate）: 「出してはいけないか」だけを見るbinary判定。品質の細かい
#   良し悪しは見ない。scoreを返さない。
# Gate B（quality_score）: Gate Aを通過した案だけを対象に、score中心で比較する。
#   原則rejectを返さない（安全性はGate Aの責務）。
# 既存の1発監査（AuditResult/ExternalAuditClient.audit()）はlegacyとして残す
# （後方互換。新規コードはGate A/Bを使うこと）。
# --------------------------------------------------------------------------
AUDIT_MODES = ("hard_gate", "quality_score")
CONFIDENCE_LEVELS = ("low", "medium", "high")
# 2026-08-23 two_threshold_redesign改訂: "no_ship"/"usable_but_weak"という曖昧な名称を廃止し、
# 「先生基準を満たしているか」と「今日の出荷ラインに届くか」を分けて表す名称にした。
# 詳細: ops/reports/two_threshold_redesign_2026-08-23.md
QUALITY_BANDS = (
    "below_teacher_floor",  # 先生投稿として成立する最低ラインにも届かない
    "teacher_level_but_not_ship",  # 先生水準は満たすが、今日の出荷ラインには届かない（failureではない）
    "ship_candidate",  # 今日の投稿候補として採用可能
    "strong_ship_candidate",  # 特に強い候補
)

# Gate Bのscore配点（100点満点）。central_claim_preservationは独立配点を持たず、
# structure_preservationの一部として評価する（構造保持と主張保持は不可分のため）。
QUALITY_SCORE_WEIGHTS = {
    "structure_preservation": 20,
    "must_keep_preservation": 20,
    "source_fidelity_without_copying": 15,
    "x_native_feel": 10,
    "concrete_noun_density": 10,
    "readability": 10,
    "emotional_trigger_strength": 5,
    "layer_fit": 5,
    "overexplanation_control": 5,
}

# teacher_reference_scoreモード（先生原文そのものの採点。ExternalAuditClient.
# audit_teacher_reference_score()、_TEACHER_REFERENCE_SCORE_SYSTEM_PROMPT）専用の配点。
# 2026-08-25 teacher_gate_b_distribution_rerun追加: 当初QualityScoreResult.from_json()は
# audit_modeを区別せずQUALITY_SCORE_WEIGHTSで正規化していたが、teacher_reference_scoreは
# 「生成文の保持度」ではなく「先生原文そのものの強さ」を測る別ルーブリックであり、
# 軸名も配点も異なる（structure_strength/hook_strength/central_claim_clarityはGate Bの
# structure_preservation/must_keep_preservation/source_fidelity_without_copyingとは
# 別概念。安易にエイリアスできない）。teacher distribution再測定時に発覚したため、
# このモード専用の配点をここに切り出した。
TEACHER_REFERENCE_SCORE_WEIGHTS = {
    "structure_strength": 20,
    "hook_strength": 15,
    "central_claim_clarity": 15,
    "concrete_noun_density": 10,
    "x_native_feel": 10,
    "readability": 10,
    "emotional_trigger_strength": 10,
    "layer_fit": 5,
    "overexplanation_control": 5,
}

# 最終採用ライン（score_overall基準）。
#
# 2026-08-23 two_threshold_redesign改訂: 単一のSHIP_THRESHOLDだけで運用すると、
# 「先生投稿として成立しているか」（teacher floor）と「今日の投稿として採用できるか」
# （ship threshold）が混同される。teacher_gate_b_distribution_2026-08-23の実測
# （先生14件の分布: min=65, p25=75, median=75, p75=75, max=80。再採点ブレ±5程度）を
# 踏まえ、teacher floorとship thresholdを分離した:
#   - TEACHER_FLOOR: 先生投稿として成立する最低ライン（実測の最小値=65を採用）
#   - BORDERLINE_LOW/HIGH: teacher floorは超えるがship thresholdには届かない帯
#   - SHIP_THRESHOLD: 今日の投稿候補として採用できるライン（実測のp25/中央値=75）
#   - STRONG_SHIP_THRESHOLD: 特に強い候補のライン（実測の最大値=80）
# 「SHIP_THRESHOLD」という語をteacher基準の意味で使わないこと（用語の混同を禁止）。
# 詳細: ops/reports/two_threshold_redesign_2026-08-23.md、
#       ops/reports/teacher_gate_b_distribution_2026-08-23.md
TEACHER_FLOOR = 65  # 先生投稿として成立する最低ライン（teacher分布の実測min）
BORDERLINE_LOW = 66  # teacher floor超え〜ship threshold未満の帯の下端
BORDERLINE_HIGH = 74  # 同、上端（SHIP_THRESHOLD - 1）
SHIP_THRESHOLD = 75  # 今日の投稿候補として採用できるライン（teacher分布のp25/中央値）
STRONG_SHIP_THRESHOLD = 80  # 特に強い候補のライン（teacher分布の実測max）


def classify_quality_band(score_overall: int) -> str:
    """score_overallをQUALITY_BANDS（below_teacher_floor/teacher_level_but_not_ship/
    ship_candidate/strong_ship_candidate）のいずれかへ分類する。"""
    if score_overall >= STRONG_SHIP_THRESHOLD:
        return "strong_ship_candidate"
    if score_overall >= SHIP_THRESHOLD:
        return "ship_candidate"
    if score_overall >= TEACHER_FLOOR:
        return "teacher_level_but_not_ship"
    return "below_teacher_floor"


def classify_quality_band_from_score(score_overall: int) -> str:
    """classify_quality_band()のエイリアス（2026-08-24 gate_b_score_consistency_patch）。

    「score→band」の判定はこの1関数（実体はclassify_quality_band）だけが行う。
    band計算元を分散させないため、他の場所でband判定ロジックを書き直さないこと。
    """
    return classify_quality_band(score_overall)


# --------------------------------------------------------------------------
# Gate B スコア正規化（2026-08-24 gate_b_score_consistency_patch追加）
#
# 背景: 実運用（production_selection_rerun_2026-08-24）で以下が判明した:
#   - 監査モデル自己申告のquality_bandが、score_overallとclassify_quality_band()の
#     定義に矛盾する（score=75なのにteacher_level_but_not_shipを自己申告する等）
#   - score_breakdown（9軸内訳）の合計とscore_overallが一致しない（最大4点差、4件中3件）
# 原因は「モデルがscore_overall/quality_bandを自由記述で返し、score_breakdownとは
# 別経路で決めている」ため（原因仮説A・B・E）。対策として、score_overall/quality_bandの
# 最終値は常にこのモジュールの関数だけで算出し、モデルの自己申告値は
# model_reported_* として退避するだけで、採用判定には使わない。
# --------------------------------------------------------------------------

# 監査モデルが軸名を言い換えて返すことがある（例: "x_native" vs "x_native_feel"）。
# 既知の言い換えパターンをQUALITY_SCORE_WEIGHTSの正式キーへ正規化する。
_GATE_B_AXIS_NAME_ALIASES = {
    "x_native": "x_native_feel",
    "concrete_noun": "concrete_noun_density",
    "concrete_density": "concrete_noun_density",
    "must_keep": "must_keep_preservation",
    "structure": "structure_preservation",
    "source_fidelity": "source_fidelity_without_copying",
    "emotional_trigger": "emotional_trigger_strength",
    "overexplanation": "overexplanation_control",
}


def normalize_score_breakdown(
    raw_breakdown: dict[str, Any] | None,
    weights: dict[str, int] | None = None,
    axis_aliases: dict[str, str] | None = None,
) -> dict[str, int]:
    """score_breakdown（軸内訳）の型揺れ・欠損・範囲外値を正規化する（rubric非依存の汎用版）。

    2026-08-25 teacher_gate_b_distribution_rerun: 元々はGate B専用
    （normalize_gate_b_score_breakdown）だったが、teacher_reference_scoreモードは
    軸名・配点が異なる別ルーブリックのため、weights/axis_aliasesを引数化した。

    - 軸名の言い換え（axis_aliases）を正式キーへ吸収する
    - 文字列数値（"15"等）はintへ変換する
    - 欠損軸は0点として扱う（楽観的に配点上限で埋めない）
    - 範囲外値（負数・各軸の配点上限超過）はその軸の0〜配点上限にクリップする
    - 戻り値はweightsの全キーを必ず含む（欠損分は0）
    """
    weights = weights if weights is not None else QUALITY_SCORE_WEIGHTS
    axis_aliases = axis_aliases if axis_aliases is not None else {}
    raw_breakdown = raw_breakdown or {}
    aliased: dict[str, Any] = {}
    for key, value in raw_breakdown.items():
        canonical_key = axis_aliases.get(key, key)
        aliased[canonical_key] = value

    normalized: dict[str, int] = {}
    for axis, max_points in weights.items():
        raw_value = aliased.get(axis)
        if raw_value is None:
            normalized[axis] = 0
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            value = 0.0
        value = max(0.0, min(float(max_points), value))
        normalized[axis] = round(value)
    return normalized


def normalize_gate_b_score_breakdown(raw_breakdown: dict[str, Any] | None) -> dict[str, int]:
    """[Gate B専用の薄いラッパー] normalize_score_breakdown(weights=QUALITY_SCORE_WEIGHTS,
    axis_aliases=_GATE_B_AXIS_NAME_ALIASES)。既存呼び出し元との後方互換のため残す。"""
    return normalize_score_breakdown(raw_breakdown, QUALITY_SCORE_WEIGHTS, _GATE_B_AXIS_NAME_ALIASES)


def calculate_weighted_score(normalized_breakdown: dict[str, int], weights: dict[str, int] | None = None) -> int:
    """正規化済みbreakdown（各軸は既に0〜配点上限にクリップ済み）を合計し、score_overallとする
    （rubric非依存の汎用版）。

    丸め規則: 各軸は既にnormalize_score_breakdown()内でint丸め済みのため、
    ここでの合計は追加の丸め処理なしでそのまま整数になる（weightsの配点合計=100点満点）。
    """
    weights = weights if weights is not None else QUALITY_SCORE_WEIGHTS
    return sum(normalized_breakdown.get(axis, 0) for axis in weights)


def calculate_weighted_gate_b_score(normalized_breakdown: dict[str, int]) -> int:
    """[Gate B専用の薄いラッパー] calculate_weighted_score(weights=QUALITY_SCORE_WEIGHTS)。"""
    return calculate_weighted_score(normalized_breakdown, QUALITY_SCORE_WEIGHTS)


def detect_score_consistency_issues(
    model_score: int | float | None,
    model_band: str | None,
    raw_breakdown: dict[str, Any] | None,
    normalized_breakdown: dict[str, int],
    normalized_score: int,
    normalized_band: str,
    weights: dict[str, int] | None = None,
    axis_aliases: dict[str, str] | None = None,
) -> list[str]:
    """監査モデルの自己申告値とコード側正規化値の不一致を検出する（rubric非依存の汎用版）。

    raw_breakdownはSPEC上の関数シグネチャ（model_score, model_band, normalized_breakdown,
    normalized_score, normalized_band）に対して追加した引数。normalized_breakdownは既に
    欠損補完・範囲クリップ済みのため、それだけでは「何が元々欠けていたか／範囲外だったか」を
    再現できない。missing_required_axis / out_of_range_axis_score の検出にはraw_breakdownが
    必須なため、シグネチャを拡張した（2026-08-24 gate_b_score_consistency_patch）。
    """
    weights = weights if weights is not None else QUALITY_SCORE_WEIGHTS
    axis_aliases = axis_aliases if axis_aliases is not None else {}
    raw_breakdown = raw_breakdown or {}
    issues: list[str] = []

    if not raw_breakdown:
        issues.append("missing_score_breakdown")
    else:
        aliased_keys = {axis_aliases.get(k, k) for k in raw_breakdown}
        missing_axes = [a for a in weights if a not in aliased_keys]
        if missing_axes:
            issues.append("missing_required_axis")

        out_of_range = []
        for key, value in raw_breakdown.items():
            canonical_key = axis_aliases.get(key, key)
            max_points = weights.get(canonical_key)
            if max_points is None:
                continue
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                out_of_range.append(canonical_key)
                continue
            if not (0 <= numeric_value <= max_points):
                out_of_range.append(canonical_key)
        if out_of_range:
            issues.append("out_of_range_axis_score")

        if model_score is not None:
            try:
                raw_sum = sum(float(v) for v in raw_breakdown.values() if isinstance(v, (int, float, str)) and str(v).strip() != "")
            except (TypeError, ValueError):
                raw_sum = None
            if raw_sum is not None and abs(raw_sum - float(model_score)) >= 1:
                issues.append("breakdown_total_mismatch")

    if model_score is not None and int(model_score) != normalized_score:
        issues.append("model_score_mismatch")

    if model_band is not None and model_band != normalized_band:
        issues.append("model_band_mismatch")

    return issues


def detect_gate_b_consistency_issues(
    model_score: int | float | None,
    model_band: str | None,
    raw_breakdown: dict[str, Any] | None,
    normalized_breakdown: dict[str, int],
    normalized_score: int,
    normalized_band: str,
) -> list[str]:
    """[Gate B専用の薄いラッパー] detect_score_consistency_issues(weights=QUALITY_SCORE_WEIGHTS,
    axis_aliases=_GATE_B_AXIS_NAME_ALIASES)。"""
    return detect_score_consistency_issues(
        model_score, model_band, raw_breakdown, normalized_breakdown, normalized_score, normalized_band,
        weights=QUALITY_SCORE_WEIGHTS, axis_aliases=_GATE_B_AXIS_NAME_ALIASES,
    )


def build_normalized_score_result(
    raw_data: dict[str, Any],
    weights: dict[str, int] | None = None,
    axis_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    """監査の生JSON（モデル出力）から、正規化済みの採用判定用データを組み立てる
    （rubric非依存の汎用版）。

    ここがscore/band算出の唯一の起点（QualityScoreResult.from_json()がこれを呼ぶ）。
    呼び出し側はこの関数の戻り値（normalized_score_overall / normalized_quality_band）
    だけを採用判定に使い、model_reported_*はログ・差分記録専用として扱うこと。

    weights/axis_aliasesを省略するとGate B（quality_score）の配点になる。
    teacher_reference_scoreモードのように配点・軸名が異なるルーブリックには、
    対応するweights（例: TEACHER_REFERENCE_SCORE_WEIGHTS）を明示的に渡すこと
    （2026-08-25 teacher_gate_b_distribution_rerun: 当初はGate B配点で一律計算しており、
    teacher_reference_scoreの軸（structure_strength等）が正しく認識されない不具合があった）。
    """
    weights = weights if weights is not None else QUALITY_SCORE_WEIGHTS
    axis_aliases = axis_aliases if axis_aliases is not None else {}

    model_score = raw_data.get("score_overall")
    model_band = raw_data.get("quality_band")
    raw_breakdown = dict(raw_data.get("score_breakdown") or {})

    normalized_breakdown = normalize_score_breakdown(raw_breakdown, weights, axis_aliases)
    normalized_score = calculate_weighted_score(normalized_breakdown, weights)
    normalized_band = classify_quality_band_from_score(normalized_score)

    issues = detect_score_consistency_issues(
        model_score, model_band, raw_breakdown, normalized_breakdown, normalized_score, normalized_band,
        weights=weights, axis_aliases=axis_aliases,
    )

    if not raw_breakdown or model_score is None:
        status = "insufficient_data"
    elif issues:
        status = "mismatch_detected"
    else:
        status = "consistent"

    return {
        "model_reported_score_overall": int(model_score) if isinstance(model_score, (int, float)) else None,
        "model_reported_quality_band": model_band,
        "score_breakdown_raw": raw_breakdown,
        "normalized_score_breakdown": normalized_breakdown,
        "normalized_score_overall": normalized_score,
        "normalized_quality_band": normalized_band,
        "score_consistency_status": status,
        "score_consistency_issues": issues,
    }


def build_gate_b_normalized_result(raw_data: dict[str, Any]) -> dict[str, Any]:
    """[Gate B専用の薄いラッパー] build_normalized_score_result(weights=QUALITY_SCORE_WEIGHTS,
    axis_aliases=_GATE_B_AXIS_NAME_ALIASES)。"""
    return build_normalized_score_result(raw_data, QUALITY_SCORE_WEIGHTS, _GATE_B_AXIS_NAME_ALIASES)


def build_teacher_reference_normalized_result(raw_data: dict[str, Any]) -> dict[str, Any]:
    """[teacher_reference_score専用の薄いラッパー]
    build_normalized_score_result(weights=TEACHER_REFERENCE_SCORE_WEIGHTS)。

    軸名の言い換え（axis_aliases）は現時点で既知のパターンが無いため空のまま
    （teacher_reference_scoreの軸名ゆらぎが今後観測されたら、Gate Bと同様に
    専用のaliasテーブルを追加すること）。
    """
    return build_normalized_score_result(raw_data, TEACHER_REFERENCE_SCORE_WEIGHTS, {})


@dataclass
class HardGateResult:
    """Gate A（禁止違反ゲート）の判定結果。binary判定のみ、scoreは持たない。"""

    hard_gate_pass: bool
    hard_violation_reasons: list[str]
    must_not_ship: bool
    confidence: str
    one_line_reason: str
    audit_mode: str = "hard_gate"
    audited_by: str = "unknown"

    @classmethod
    def from_json(cls, data: dict[str, Any], audited_by: str = "unknown") -> "HardGateResult":
        validate_hard_gate_result(data)
        return cls(
            hard_gate_pass=bool(data["hard_gate_pass"]),
            hard_violation_reasons=list(data.get("hard_violation_reasons") or []),
            must_not_ship=bool(data["must_not_ship"]),
            confidence=data["confidence"],
            one_line_reason=data.get("one_line_reason", ""),
            audit_mode=data.get("audit_mode", "hard_gate"),
            audited_by=audited_by,
        )


@dataclass
class QualityScoreResult:
    """Gate B（採用品質スコア）の判定結果。原則rejectを返さない（安全性はGate Aの責務）。

    2026-08-24 gate_b_score_consistency_patch: score_overall/score_breakdown/quality_bandは
    常に「コード側で正規化・再計算した最終値」であり、監査モデルの自己申告そのものではない
    （build_gate_b_normalized_result()がfrom_json()内で唯一の算出元として動く）。
    モデルの自己申告値はmodel_reported_score_overall/model_reported_quality_bandに退避する。
    採用判定に使ってよいのはnormalized_score_overall/normalized_quality_band
    （=score_overall/quality_bandと同値）だけで、model_reported_*は差分ログ専用。
    """

    score_overall: int  # 正規化済み最終値（= normalized_score_overall）
    score_breakdown: dict[str, int]  # 正規化済み内訳（= normalized_score_breakdown）
    strengths: list[str]
    weaknesses: list[str]
    improvement_suggestions: list[str]
    quality_band: str  # 正規化済み最終値（= normalized_quality_band）
    confidence: str
    one_line_reason: str
    audit_mode: str = "quality_score"
    audited_by: str = "unknown"
    # 監査モデルの自己申告値（採用判定には使わない。差分ログ専用）
    model_reported_score_overall: int | None = None
    model_reported_quality_band: str | None = None
    score_breakdown_raw: dict[str, Any] = field(default_factory=dict)
    # コード側正規化値（score_overall/quality_band/score_breakdownと同値だが、
    # 「これが採用判定の起点である」ことを名前で明示するための別名フィールド）
    normalized_score_overall: int = 0
    normalized_score_breakdown: dict[str, int] = field(default_factory=dict)
    normalized_quality_band: str = "below_teacher_floor"
    score_consistency_status: str = "insufficient_data"  # consistent / mismatch_detected / insufficient_data
    score_consistency_issues: list[str] = field(default_factory=list)
    score_source: str = "code_normalized"  # model_reported / code_normalized（採用判定は常にcode_normalized）
    band_source: str = "code_normalized"
    # 2026-08-25 quality_score_compression_fix: どのprompt/rubric定義でこのscoreが
    # 出たかを追跡する（圧縮再発時に「どのバージョンの問題か」を切り分けるための診断用）。
    rubric_version: str = "unknown"
    prompt_version: str = "unknown"

    @classmethod
    def from_json(
        cls, data: dict[str, Any], audited_by: str = "unknown",
        rubric_version: str = "unknown", prompt_version: str = "unknown",
    ) -> "QualityScoreResult":
        validate_quality_score_result(data)
        # 2026-08-25 teacher_gate_b_distribution_rerun修正: teacher_reference_scoreモードは
        # Gate B（quality_score）とは軸名・配点が異なる別ルーブリック（structure_strength等）
        # のため、audit_modeでweightsを切り替える。旧実装はaudit_modeを見ずに常に
        # build_gate_b_normalized_result()（=QUALITY_SCORE_WEIGHTS固定）を使っており、
        # teacher_reference_scoreの軸がほぼ丸ごと「未知の軸」として無視される不具合があった。
        if data.get("audit_mode") == "teacher_reference_score":
            normalized = build_teacher_reference_normalized_result(data)
        else:
            normalized = build_gate_b_normalized_result(data)
        return cls(
            score_overall=normalized["normalized_score_overall"],
            score_breakdown=normalized["normalized_score_breakdown"],
            strengths=list(data.get("strengths") or []),
            weaknesses=list(data.get("weaknesses") or []),
            improvement_suggestions=list(data.get("improvement_suggestions") or []),
            quality_band=normalized["normalized_quality_band"],
            confidence=data["confidence"],
            one_line_reason=data.get("one_line_reason", ""),
            audit_mode=data.get("audit_mode", "quality_score"),
            audited_by=audited_by,
            model_reported_score_overall=normalized["model_reported_score_overall"],
            model_reported_quality_band=normalized["model_reported_quality_band"],
            score_breakdown_raw=normalized["score_breakdown_raw"],
            normalized_score_overall=normalized["normalized_score_overall"],
            normalized_score_breakdown=normalized["normalized_score_breakdown"],
            normalized_quality_band=normalized["normalized_quality_band"],
            score_consistency_status=normalized["score_consistency_status"],
            score_consistency_issues=normalized["score_consistency_issues"],
            score_source="code_normalized",
            band_source="code_normalized",
            rubric_version=rubric_version,
            prompt_version=prompt_version,
        )


def validate_hard_gate_result(data: dict[str, Any]) -> None:
    required = ("hard_gate_pass", "must_not_ship", "confidence")
    missing = [k for k in required if k not in data]
    if missing:
        raise AuditSchemaError(f"Gate A監査結果に必須フィールドが不足しています: {missing}")
    if not isinstance(data["hard_gate_pass"], bool):
        raise AuditSchemaError(f"hard_gate_passはbool必須です: {data['hard_gate_pass']}")
    if not isinstance(data["must_not_ship"], bool):
        raise AuditSchemaError(f"must_not_shipはbool必須です: {data['must_not_ship']}")
    if data["confidence"] not in CONFIDENCE_LEVELS:
        raise AuditSchemaError(f"confidenceが不正です: {data['confidence']}（許容値: {CONFIDENCE_LEVELS}）")


def validate_quality_score_result(data: dict[str, Any]) -> None:
    required = ("score_overall", "confidence")
    missing = [k for k in required if k not in data]
    if missing:
        raise AuditSchemaError(f"Gate B監査結果に必須フィールドが不足しています: {missing}")
    if not isinstance(data["score_overall"], (int, float)) or not (0 <= data["score_overall"] <= 100):
        raise AuditSchemaError(f"score_overallが不正です: {data['score_overall']}（0-100の数値が必要）")
    if data["confidence"] not in CONFIDENCE_LEVELS:
        raise AuditSchemaError(f"confidenceが不正です: {data['confidence']}（許容値: {CONFIDENCE_LEVELS}）")
    quality_band = data.get("quality_band")
    if quality_band is not None and quality_band not in QUALITY_BANDS:
        raise AuditSchemaError(f"quality_bandが不正です: {quality_band}（許容値: {QUALITY_BANDS}）")


# --------------------------------------------------------------------------
# audit fix 正規化層（2026-08-21 audit_fix_normalization_layer追加）
#
# 背景: external audit の required_fixes をそのまま生成側へ流すと、「もっと具体的に」
# 「比較軸を増やして」等の指摘が、原文にない scene/axis/brand/spec を足す方向へ流れうる
# （production_selection_fashion_gadget_2026-08-21.md / production_selection_gadget_only_
# 2026-08-21.md / gadget_minimal_patch_2026-08-21.md で繰り返し観測）。
# raw fix text → 意図（FixIntent） → 安全性（FixSafety） → 生成制約、という
# 正規化パイプラインを挟み、「捏造禁止ポリシーに適合する修正指示」だけを通す。
# 判定ロジック本体は post_generation_pipeline.py にある。ここはデータ構造のみ。
# --------------------------------------------------------------------------
FIX_INTENTS = (
    "increase_concreteness",
    "clarify_comparison_question",
    "reinforce_category_head_noun",
    "retain_age_angle",
    "preserve_structure",
    "reduce_article_intro",
    "reduce_diary_tone",
    "tighten_claim_focus",
    "reinforce_endpoints",
    "clarify_conclusion_frame",
    "add_usage_scene",
    "add_comparison_axis",
    "add_brand_or_model_detail",
    "add_product_specific_examples",
    "other_unknown",
)

FIX_SAFETY_LEVELS = (
    "safe_from_source",  # 原文にある情報だけで対応できる
    "safe_by_rephrasing",  # 新情報追加なしで再配置・再表現すれば対応できる
    "ambiguous_needs_manual",  # 自動判定が危険。保留し、人間の判断を仰ぐ
    "forbidden_requires_invention",  # 原文外の補完が必要で、捏造禁止に反する
)


@dataclass
class NormalizedAuditFix:
    """external auditの1件のraw fixを正規化した結果。"""

    raw_fix_text: str
    intent: str  # FIX_INTENTSのいずれか
    safety: str  # FIX_SAFETY_LEVELSのいずれか
    alternative_intents: list[str] = field(default_factory=list)
    resulting_constraints: list[str] = field(default_factory=list)
    was_applied: bool = False  # このraw fix（または代替intent経由）が制約として反映されたか
    was_blocked: bool = False  # raw fixそのものがそのままの形では適用されなかったか
    blocked_reason: str | None = None


@dataclass
class FixNormalizationResult:
    """1回分のaudit required_fixes全体を正規化した結果。"""

    normalized_fixes: list[NormalizedAuditFix]
    safe_constraints: list[str]  # 実際に生成へ渡してよい制約IDの重複排除済みリスト
    blocked_count: int
    forbidden_intents: list[str]  # forbidden_requires_inventionと判定されたintentのリスト（ループ再発検知用）
    all_forbidden: bool  # safe_constraintsが1つも得られなかったか（構造衝突の疑い）


def validate_audit_result(data: dict[str, Any]) -> None:
    """外部AIが返したJSONの型・enumを検証する（信頼できない入力として扱う）。"""
    required = (
        "verdict",
        "score_overall",
        "structure_preserved",
        "essay_risk",
        "article_intro_risk",
        "ad_like_risk",
        "layer_fit",
    )
    missing = [k for k in required if k not in data]
    if missing:
        raise AuditSchemaError(f"外部AI監査結果に必須フィールドが不足しています: {missing}")

    if data["verdict"] not in VERDICTS:
        raise AuditSchemaError(f"verdictが不正です: {data['verdict']}（許容値: {VERDICTS}）")
    if not isinstance(data["score_overall"], (int, float)) or not (0 <= data["score_overall"] <= 100):
        raise AuditSchemaError(f"score_overallが不正です: {data['score_overall']}（0-100の数値が必要）")
    for field_name in ("essay_risk", "article_intro_risk", "ad_like_risk"):
        if data[field_name] not in RISK_LEVELS:
            raise AuditSchemaError(f"{field_name}が不正です: {data[field_name]}（許容値: {RISK_LEVELS}）")
    if data["layer_fit"] not in LAYER_FITS:
        raise AuditSchemaError(f"layer_fitが不正です: {data['layer_fit']}（許容値: {LAYER_FITS}）")


# --------------------------------------------------------------------------
# Comparative Gate B（multi-draft比較評価、2026-08-25 quality_score_multidraft_gate_b追加）
#
# 背景: EXP-20260825-QS-COMPRESSION-01・EXP-20260825-QS-NEXT-01の2実験で、single-draft
# 絶対採点（1draftずつ独立に監査し、あとから比較する方式）では、数値アンカーの追加/除去/
# 軸境界のシャープ化のいずれを試しても圧縮が解消しないことが確認された
# （pairwise gapが5→1→0まで一貫して縮小）。root_cause_familyとして
# single_draft_absolute_scoringが2実験連続で支持されたため、本モジュールでは
# 「まず比較・順位付けさせ、点数はコード側が算出する」設計（comparative judgment ->
# code-side normalization）を追加する。
#
# 重要な設計原則: モデルには絶対スコア（0-100点）を一切返させない。モデルが返すのは
# 「同一候補から作られた複数draftのうち、どれが軸ごとに相対的に強いか」という順位付けの
# みであり、normalized_score_overall/normalized_quality_bandは常に
# convert_comparative_rankings_to_normalized_scores()というコード側の1関数だけが算出する
# （score算出元の単一化という既存方針をcomparative Gate Bにも継承する）。
# 詳細: ops/reports/quality_score_multidraft_gate_b_2026-08-25.md
# --------------------------------------------------------------------------

# 比較評価の対象軸は既存quality_scoreの9軸（QUALITY_SCORE_WEIGHTS）をそのまま使う。
# teacher_reference_score専用の軸名（structure_strength/central_claim_clarity等）は混ぜない
# （EXP-20260825-TEACHERBUG-01で軸名の取り違えが実際に不具合を起こした教訓を踏まえる）。
COMPARATIVE_AXES = tuple(QUALITY_SCORE_WEIGHTS.keys())
COMPARATIVE_TIER_LEVELS = ("strong", "medium", "weak")


class ComparativeAuditSchemaError(AuditSchemaError):
    pass


@dataclass
class ComparativeAxisResult:
    """1軸分の比較評価結果。ranking_tiersは同一tier内が同順位（タイ）を表す
    （例: [["d1"], ["d2","d3"], ["d4"]] は d1が1位、d2とd3が2位タイ、d4が4位）。"""

    axis_name: str
    ranking_tiers: list[list[str]]  # best -> worst の順、各要素はtier内draft_idのリスト
    tiers: dict[str, str]  # draft_id -> strong/medium/weak
    confidence: str
    rationale: str


@dataclass
class ComparativeQualityScoreResult:
    """Comparative Gate B（同一候補由来の複数draftをまとめて比較評価）の結果。

    score_overall/score_breakdown/quality_bandに相当する数値は、モデルからは一切
    受け取らない。normalized_scores/normalized_bands/normalized_axis_breakdownが
    唯一のスコア算出結果であり、build_comparative_normalized_result()（本モジュール）
    だけがこれを計算する。
    """

    batch_id: str
    draft_ids: list[str]
    axis_results: list[ComparativeAxisResult]
    overall_ranking: list[str]  # モデル自身の総合順位認識（参考値。採用判定には使わない）
    top_candidate_id: str | None
    comparative_summary: str
    compression_warning: str | None
    model_reported_notes: list[str] = field(default_factory=list)
    audit_mode: str = "quality_score_multidraft_v1"
    audited_by: str = "unknown"
    # コード側正規化結果（v1 Borda。順位方向は正しいがgapが過大になりやすい。後方互換のため残す）
    normalized_axis_breakdown: dict[str, dict[str, int]] = field(default_factory=dict)  # draft_id -> {axis: points}
    normalized_scores: dict[str, int] = field(default_factory=dict)  # draft_id -> score_overall
    normalized_bands: dict[str, str] = field(default_factory=dict)  # draft_id -> quality_band
    # 2026-08-26 R2-2追加: tier_bounded_v1マッピング（順位保持・gap抑制）。
    # scripts/comparative_score_mapping.pyが算出する。recommendation表示にはこちらを使う。
    mapped_normalized_scores: dict[str, int] = field(default_factory=dict)  # draft_id -> bounded score
    mapped_normalized_bands: dict[str, str] = field(default_factory=dict)  # draft_id -> quality_band(bounded score基準)
    mapping_version: str | None = None
    mapping_diagnostics: dict[str, Any] = field(default_factory=dict)
    # 2026-08-26 EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01追加。
    # legacy 9軸のスコア計算（上記フィールド群）は一切変更しない。hook軸は追加の
    # 観測データとして別枠で保持し、numeric anchorを持たない（既存スコアに混ぜない）。
    comparative_rubric_version: str = "legacy_v1"
    hook_axis_results: list["HookAxisResult"] = field(default_factory=list)
    overall_ranking_hook_augmented: list[str] = field(default_factory=list)
    hook_augmented_top_candidate_id: str | None = None
    legacy_axes_top_candidate_id: str | None = None


def validate_comparative_quality_score_result(data: dict[str, Any], expected_draft_ids: list[str]) -> None:
    """外部AIが返したcomparative JSONの型・整合性を検証する（信頼できない入力として扱う）。"""
    required = ("draft_ids", "axis_results", "overall_ranking")
    missing = [k for k in required if k not in data]
    if missing:
        raise ComparativeAuditSchemaError(f"Comparative Gate B結果に必須フィールドが不足しています: {missing}")

    returned_ids = set(data["draft_ids"])
    expected_ids = set(expected_draft_ids)
    if returned_ids != expected_ids:
        raise ComparativeAuditSchemaError(
            f"draft_idsが依頼内容と一致しません。期待={expected_ids}, 返却={returned_ids}"
        )

    axis_results = data["axis_results"]
    if not isinstance(axis_results, list) or not axis_results:
        raise ComparativeAuditSchemaError("axis_resultsは1件以上のリストである必要があります")

    seen_axes = set()
    for entry in axis_results:
        axis_name = entry.get("axis_name")
        if axis_name not in COMPARATIVE_AXES:
            raise ComparativeAuditSchemaError(f"未知のaxis_name: {axis_name}（許容値: {COMPARATIVE_AXES}）")
        seen_axes.add(axis_name)

        tiers_field = entry.get("ranking_tiers")
        if not isinstance(tiers_field, list) or not tiers_field:
            raise ComparativeAuditSchemaError(f"axis={axis_name}のranking_tiersが不正です")
        flattened = [did for tier in tiers_field for did in tier]
        if set(flattened) != expected_ids:
            raise ComparativeAuditSchemaError(
                f"axis={axis_name}のranking_tiersに含まれるdraft_idが期待値と一致しません: {set(flattened)} != {expected_ids}"
            )
        confidence = entry.get("confidence")
        if confidence not in CONFIDENCE_LEVELS:
            raise ComparativeAuditSchemaError(f"axis={axis_name}のconfidenceが不正です: {confidence}")

    missing_axes = set(COMPARATIVE_AXES) - seen_axes
    if missing_axes:
        raise ComparativeAuditSchemaError(f"axis_resultsに不足している軸があります: {missing_axes}")

    overall_ranking = data["overall_ranking"]
    if not isinstance(overall_ranking, list) or set(overall_ranking) != expected_ids:
        raise ComparativeAuditSchemaError(f"overall_rankingが不正です: {overall_ranking}")


def convert_comparative_rankings_to_normalized_scores(
    draft_ids: list[str],
    axis_results: list[dict[str, Any]] | list["ComparativeAxisResult"],
    weights: dict[str, int] | None = None,
) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    """比較順位（軸ごとのranking_tiers）を、コード側でnormalized_score_overallへ変換する。

    各軸の配点上限（weights、デフォルトはQUALITY_SCORE_WEIGHTS）を、そのdraftの相対順位に
    応じた割合で配分するBorda count方式。n件中の位置（0-indexed、0=最良）をposとすると、
    fraction = (n-1-pos)/(n-1)（n=1のときは1.0固定）。tier内（タイ）のdraftは、そのtierが
    占める順位レンジの平均位置を使う（=平均順位点。指示書の「ties は平均順位点」に対応）。
    軸ごとの点数はfraction * 配点上限を四捨五入。overallは全軸合計（配点合計100点なので
    追加の丸めは発生しない）。

    normalized_quality_bandの判定はclassify_quality_band_from_score()（既存関数）を
    そのまま使う。閾値（TEACHER_FLOOR/SHIP_THRESHOLD/STRONG_SHIP_THRESHOLD）は変更しない。
    """
    weights = weights if weights is not None else QUALITY_SCORE_WEIGHTS
    n = len(draft_ids)
    breakdown: dict[str, dict[str, int]] = {did: {} for did in draft_ids}

    for axis, max_points in weights.items():
        axis_entry = next(
            (a for a in axis_results if (a.axis_name if isinstance(a, ComparativeAxisResult) else a.get("axis_name")) == axis),
            None,
        )
        tiers = (
            axis_entry.ranking_tiers if isinstance(axis_entry, ComparativeAxisResult) else (axis_entry or {}).get("ranking_tiers")
        ) if axis_entry is not None else None
        if not tiers:
            # 軸データが欠落している場合、全draftを同率（真ん中）として扱う（楽観的に埋めない）
            tiers = [list(draft_ids)]

        position_of: dict[str, float] = {}
        pos = 0
        for tier in tiers:
            tier_ids = [d for d in tier if d in draft_ids]
            if not tier_ids:
                continue
            span = list(range(pos, pos + len(tier_ids)))
            avg_pos = sum(span) / len(span)
            for did in tier_ids:
                position_of[did] = avg_pos
            pos += len(tier_ids)
        for did in draft_ids:
            if did not in position_of:
                position_of[did] = n - 1  # ranking_tiersに出現しないdraftは最下位扱い

        for did in draft_ids:
            fraction = (n - 1 - position_of[did]) / (n - 1) if n > 1 else 1.0
            breakdown[did][axis] = round(fraction * max_points)

    scores = {did: sum(breakdown[did].values()) for did in draft_ids}
    return breakdown, scores


def build_comparative_normalized_result(
    data: dict[str, Any], expected_draft_ids: list[str], weights: dict[str, int] | None = None
) -> dict[str, Any]:
    """Comparative Gate Bの生JSON（モデル出力）から、正規化済みスコアを組み立てる唯一の入口。"""
    validate_comparative_quality_score_result(data, expected_draft_ids)
    breakdown, scores = convert_comparative_rankings_to_normalized_scores(
        expected_draft_ids, data["axis_results"], weights=weights
    )
    bands = {did: classify_quality_band_from_score(s) for did, s in scores.items()}
    return {
        "normalized_axis_breakdown": breakdown,
        "normalized_scores": scores,
        "normalized_bands": bands,
    }


# --------------------------------------------------------------------------
# 2026-08-26 EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01追加。
# Run5/Run6でcomparative推奨(structure/fidelity寄り)とreal human final judgment
# (冒頭フック寄り)のmismatchがn=2で再現したことを受け、comparative Gate Bの
# 比較対象軸に「冒頭フック系」4軸を追加検証する。既存のCOMPARATIVE_AXES（9軸、
# Borda変換、tier_bounded_v1マッピング）は一切変更しない。hook軸は数値アンカーを
# 持たず、相対順位（ranking、タイなし）+一言rationaleのみで表現し、
# 既存の重み付きスコア計算（convert_comparative_rankings_to_normalized_scores）
# には混ぜない。詳細: ops/reports/shadow_mode_run_2026-08-26_run7_gadget_hookaxis.md
# --------------------------------------------------------------------------
HOOK_AXES = (
    "opening_hook_strength",
    "first_phrase_sharpness",
    "timeline_stop_power",
    "instant_comparison_clarity",
)
HOOK_AXIS_DEFINITIONS = {
    "opening_hook_strength": "冒頭数語で読者を止める力",
    "first_phrase_sharpness": "冒頭句そのものの切れ味",
    "timeline_stop_power": "タイムライン上でスクロールを止める引力",
    "instant_comparison_clarity": "比較の論点が一瞬で伝わる強さ",
}


@dataclass
class HookAxisResult:
    """1軸分のhook系比較評価結果。数値アンカーは持たず、相対順位（best->worst、
    タイなしのフラットなリスト）と一言rationaleのみで表現する。"""

    axis_name: str
    ranking: list[str]  # best -> worst、タイを許容しないフラットなdraft_idリスト
    rationale: str


def validate_hook_augmented_comparative_result(data: dict[str, Any], expected_draft_ids: list[str]) -> None:
    """hook_augmented_v1のcomparative JSONの型・整合性を検証する。

    既存のvalidate_comparative_quality_score_result()（legacy 9軸）はこの関数の
    呼び出し元が別途呼ぶ想定（本関数はhook軸+overall_ranking_hook_augmentedのみ検証）。
    """
    expected_ids = set(expected_draft_ids)

    hook_results = data.get("hook_axis_results")
    if not isinstance(hook_results, list) or not hook_results:
        raise ComparativeAuditSchemaError("hook_axis_resultsは1件以上のリストである必要があります")

    seen_axes = set()
    for entry in hook_results:
        axis_name = entry.get("axis_name")
        if axis_name not in HOOK_AXES:
            raise ComparativeAuditSchemaError(f"未知のhook axis_name: {axis_name}（許容値: {HOOK_AXES}）")
        seen_axes.add(axis_name)

        ranking = entry.get("ranking")
        if not isinstance(ranking, list) or set(ranking) != expected_ids or len(ranking) != len(expected_ids):
            raise ComparativeAuditSchemaError(
                f"hook axis={axis_name}のrankingが不正です（タイなしの完全な順列が必要）: {ranking}"
            )
        rationale = entry.get("rationale")
        if not rationale or not isinstance(rationale, str):
            raise ComparativeAuditSchemaError(f"hook axis={axis_name}のrationaleが必須です")

    missing_axes = set(HOOK_AXES) - seen_axes
    if missing_axes:
        raise ComparativeAuditSchemaError(f"hook_axis_resultsに不足している軸があります: {missing_axes}")

    overall_hook = data.get("overall_ranking_hook_augmented")
    if not isinstance(overall_hook, list) or set(overall_hook) != expected_ids or len(overall_hook) != len(expected_ids):
        raise ComparativeAuditSchemaError(f"overall_ranking_hook_augmentedが不正です: {overall_hook}")


def build_hook_augmented_comparative_result(
    data: dict[str, Any], expected_draft_ids: list[str], weights: dict[str, int] | None = None
) -> dict[str, Any]:
    """hook_augmented_v1のcomparative JSONから、legacy(9軸)側とhook軸側の両方を組み立てる。

    legacy側はbuild_comparative_normalized_result()をそのまま再利用する（既存ロジック不変）。
    hook軸側はスコア化せず、ranking+rationaleのみをそのまま保持する
    （numeric anchorの再導入禁止という設計方針のため）。
    """
    legacy = build_comparative_normalized_result(data, expected_draft_ids, weights=weights)
    validate_hook_augmented_comparative_result(data, expected_draft_ids)
    hook_axis_results = [
        HookAxisResult(axis_name=a["axis_name"], ranking=a["ranking"], rationale=a.get("rationale", ""))
        for a in data["hook_axis_results"]
    ]
    overall_ranking_hook_augmented = list(data["overall_ranking_hook_augmented"])
    return {
        **legacy,
        "hook_axis_results": hook_axis_results,
        "overall_ranking_hook_augmented": overall_ranking_hook_augmented,
        "hook_augmented_top_candidate_id": overall_ranking_hook_augmented[0] if overall_ranking_hook_augmented else None,
    }


# ==============================================================================
# 2026-08-27 EXP-20260827-FLHOOK-01実装。
#
# first-line hook evaluator: comparative Gate B本体（legacy 9軸 + hook_augmented_v1、
# 上記のCOMPARATIVE_AXES/HOOK_AXES）とは完全に独立したresearch-onlyの補助判定器。
# 本文全体・構造・must_keep・source fidelityは一切見せず、draft冒頭のopening_textのみを
# 比較対象にする。既存のcomparative Gate B（legacy/hook_augmented_v1）のコードは
# 一切変更しない。production shipping decisionには接続しない。
# 設計文書: ops/reports/first_line_hook_evaluator_design_2026-08-27.md
# ==============================================================================
FIRST_LINE_HOOK_AXES = (
    "first_phrase_sharpness",
    "scroll_stop_power",
    "instant_topic_lockin",
    "comparison_axis_immediacy",
)
FIRST_LINE_HOOK_AXIS_DEFINITIONS = {
    "first_phrase_sharpness": "冒頭句の切れ味。最初の数語だけで論点が立つか",
    "scroll_stop_power": "タイムライン上で視線を止める力。スクロール中でも引っかかるか",
    "instant_topic_lockin": "何の話かを即座に固定できるか。読む前にテーマが頭に入るか",
    "comparison_axis_immediacy": "何と何を比べるのかが一瞬で伝わるか",
}
FIRST_LINE_HOOK_RUBRIC_VERSION = "first_line_hook_v1"


class FirstLineHookSchemaError(AuditSchemaError):
    pass


@dataclass
class FirstLineHookAxisResult:
    """1軸分のfirst-line hook評価結果。numeric anchor・tier分類は持たず、
    相対順位（ranking、タイなしの完全な順列）と一言reasonのみで表現する。"""

    axis_name: str
    ranking: list[str]  # best -> worst、タイを許容しないフラットなdraft_idリスト
    reason: str


@dataclass
class FirstLineHookEvaluationResult:
    """first-line hook evaluatorの結果。comparative Gate B本体のスコアリング
    （normalized_scores/mapped_normalized_scores等）とは完全に別系統であり、
    ここで得られるhook_top_candidate_idはrecommendation-onlyの補助信号に留まる。"""

    batch_id: str
    draft_ids: list[str]
    rubric_version: str
    candidate_openings: dict[str, str]  # draft_id -> opening_text（実際に評価に使われた冒頭抜粋）
    axis_rankings: list[FirstLineHookAxisResult]
    axis_reasons: dict[str, str] = field(default_factory=dict)  # axis_name -> reason（axis_rankingsから複製、参照しやすさのため）
    overall_hook_ranking: list[str] = field(default_factory=list)
    hook_top_candidate_id: str | None = None
    hook_summary_reason: str = ""
    audited_by: str = "unknown"
    # comparative Gate B本体との比較用（pipeline層がstructure側の結果を渡して埋める。
    # このスキーマ単体では未確定＝Noneのままでよい）
    structure_top_candidate_id: str | None = None
    structure_hook_alignment: bool | None = None
    structure_reason_summary: str | None = None
    hook_reason_summary: str | None = None


def validate_first_line_hook_result(data: dict[str, Any], expected_draft_ids: list[str]) -> None:
    """外部AIが返したfirst-line hook評価JSONの型・整合性を検証する（信頼できない入力として扱う）。"""
    expected_ids = set(expected_draft_ids)

    axis_rankings = data.get("axis_rankings")
    if not isinstance(axis_rankings, list) or not axis_rankings:
        raise FirstLineHookSchemaError("axis_rankingsは1件以上のリストである必要があります")

    seen_axes = set()
    for entry in axis_rankings:
        axis_name = entry.get("axis_name")
        if axis_name not in FIRST_LINE_HOOK_AXES:
            raise FirstLineHookSchemaError(f"未知のfirst-line hook axis_name: {axis_name}（許容値: {FIRST_LINE_HOOK_AXES}）")
        seen_axes.add(axis_name)

        ranking = entry.get("ranking")
        if not isinstance(ranking, list) or set(ranking) != expected_ids or len(ranking) != len(expected_ids):
            raise FirstLineHookSchemaError(
                f"axis={axis_name}のrankingが不正です（タイなしの完全な順列が必要）: {ranking}"
            )
        reason = entry.get("reason")
        if not reason or not isinstance(reason, str):
            raise FirstLineHookSchemaError(f"axis={axis_name}のreasonが必須です")

    missing_axes = set(FIRST_LINE_HOOK_AXES) - seen_axes
    if missing_axes:
        raise FirstLineHookSchemaError(f"axis_rankingsに不足している軸があります: {missing_axes}")

    overall = data.get("overall_hook_ranking")
    if not isinstance(overall, list) or set(overall) != expected_ids or len(overall) != len(expected_ids):
        raise FirstLineHookSchemaError(f"overall_hook_rankingが不正です: {overall}")

    hook_summary_reason = data.get("hook_summary_reason")
    if not hook_summary_reason or not isinstance(hook_summary_reason, str):
        raise FirstLineHookSchemaError("hook_summary_reasonが必須です")


def build_first_line_hook_result(
    data: dict[str, Any], expected_draft_ids: list[str], candidate_openings: dict[str, str],
    batch_id: str | None = None, audited_by: str = "unknown",
) -> "FirstLineHookEvaluationResult":
    """first-line hook evaluatorの生JSON（モデル出力）から結果オブジェクトを組み立てる唯一の入口。

    candidate_openingsは呼び出し側（client層）が実際にモデルへ送ったopening_textをそのまま
    渡すこと（モデルの自己申告ではなく、実際に何を評価対象として渡したかを正として記録する）。
    """
    validate_first_line_hook_result(data, expected_draft_ids)
    axis_rankings = [
        FirstLineHookAxisResult(axis_name=a["axis_name"], ranking=a["ranking"], reason=a.get("reason", ""))
        for a in data["axis_rankings"]
    ]
    axis_reasons = {a.axis_name: a.reason for a in axis_rankings}
    overall_hook_ranking = list(data["overall_hook_ranking"])
    hook_top_candidate_id = overall_hook_ranking[0] if overall_hook_ranking else None
    return FirstLineHookEvaluationResult(
        batch_id=data.get("batch_id", batch_id) or (batch_id or ""),
        draft_ids=list(expected_draft_ids),
        rubric_version=data.get("rubric_version", FIRST_LINE_HOOK_RUBRIC_VERSION),
        candidate_openings=dict(candidate_openings),
        axis_rankings=axis_rankings,
        axis_reasons=axis_reasons,
        overall_hook_ranking=overall_hook_ranking,
        hook_top_candidate_id=hook_top_candidate_id,
        hook_summary_reason=data.get("hook_summary_reason", ""),
        audited_by=audited_by,
    )


# ==============================================================================
# 2026-08-28 EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01実装。
#
# hook_v2 (opening span evaluator): first-line hook evaluator（hook_v1、上記の
# FIRST_LINE_HOOK_*）とは別系統のresearch-onlyの補助判定器。hook_v1が冒頭8〜20文字の
# 固定窓のみを評価対象にするのに対し、hook_v2は「冒頭句」「比較軸が成立する位置まで」
# 「結論/収束ニュアンスが現れる位置まで」の3スパン候補から実際に評価対象とするスパンを
# 選定して評価する（first_line_hook_evaluator.pyのselect_opening_span()が選定を担う）。
# hook_v1のコード・スキーマは一切変更しない。comparative Gate B本体・production
# shipping decisionには接続しない。
# 設計文書: ops/reports/hook_evaluator_window_redesign_2026-08-28.md
# ==============================================================================
OPENING_SPAN_HOOK_AXES = (
    "opening_phrase_sharpness",
    "comparison_axis_lockin_speed",
    "use_case_contrast_emergence",
    "conclusion_landing_compactness",
    "scroll_stop_power",
    "ambiguity_penalty",
    "theme_clarity_at_first_read",
)
OPENING_SPAN_HOOK_AXIS_DEFINITIONS = {
    "opening_phrase_sharpness": "冒頭句そのものの切れ味（hook_v1のfirst_phrase_sharpnessに相当）",
    "comparison_axis_lockin_speed": "何と何を比べているかが、選定spanの中でどれだけ早く固定されるか",
    "use_case_contrast_emergence": "用途・場面の対比（例: ジム用/自宅用）がspan内でどれだけ明確に立ち上がるか",
    "conclusion_landing_compactness": "span内に結論・収束のニュアンスが含まれる場合、その着地がどれだけ簡潔にまとまっているか",
    "scroll_stop_power": "タイムライン上で視線を止める力（hook_v1と同義だが、選定spanの長さを踏まえて再評価する）",
    "ambiguity_penalty": "「これ」等の指示語で指示先が不明瞭な弱さ。強いほど順位を下げる要因として明記すること",
    "theme_clarity_at_first_read": "spanを一度読んだだけでテーマ全体（何についての投稿か）が把握できるか（任意補助軸）",
}
OPENING_SPAN_HOOK_RUBRIC_VERSION = "opening_span_hook_v2"


class OpeningSpanHookSchemaError(AuditSchemaError):
    pass


@dataclass
class OpeningSpanHookAxisResult:
    """1軸分のhook_v2評価結果。numeric anchor・tier分類は持たず、相対順位（ranking、
    タイなしの完全な順列）と一言reasonのみで表現する（hook_v1と同じ思想）。"""

    axis_name: str
    ranking: list[str]
    reason: str


@dataclass
class OpeningSpanHookEvaluationResult:
    """hook_v2（opening span evaluator）の結果。hook_v1・comparative Gate B本体の
    スコアリングとは完全に別系統であり、ここで得られるhook_v2_top_candidate_idは
    recommendation-onlyの補助信号に留まる。"""

    batch_id: str
    draft_ids: list[str]
    rubric_version: str
    evaluated_opening_span_by_candidate: dict[str, str]  # draft_id -> 実際に評価に使われたspan本文
    opening_span_selection_reason_by_candidate: dict[str, str]  # draft_id -> 選定理由
    comparison_axis_detected_by_candidate: dict[str, bool]
    conclusion_landing_detected_by_candidate: dict[str, bool]
    axis_rankings: list[OpeningSpanHookAxisResult]
    axis_reasons: dict[str, str] = field(default_factory=dict)
    hook_v2_overall_ranking: list[str] = field(default_factory=list)
    hook_v2_top_candidate_id: str | None = None
    hook_v2_summary_reason: str = ""
    audited_by: str = "unknown"
    # comparative Gate B本体・hook_v1との比較用（pipeline層が埋める。未確定＝Noneのままでよい）
    structure_top_candidate_id: str | None = None
    structure_vs_hook_v2_alignment: bool | None = None
    hook_v1_top_candidate_id: str | None = None
    hook_v1_vs_hook_v2_alignment: bool | None = None
    structure_reason_summary: str | None = None
    hook_v1_reason_summary: str | None = None


def validate_opening_span_hook_result(data: dict[str, Any], expected_draft_ids: list[str]) -> None:
    """外部AIが返したhook_v2評価JSONの型・整合性を検証する（信頼できない入力として扱う）。"""
    expected_ids = set(expected_draft_ids)

    axis_rankings = data.get("axis_rankings")
    if not isinstance(axis_rankings, list) or not axis_rankings:
        raise OpeningSpanHookSchemaError("axis_rankingsは1件以上のリストである必要があります")

    seen_axes = set()
    for entry in axis_rankings:
        axis_name = entry.get("axis_name")
        if axis_name not in OPENING_SPAN_HOOK_AXES:
            raise OpeningSpanHookSchemaError(f"未知のopening span hook axis_name: {axis_name}（許容値: {OPENING_SPAN_HOOK_AXES}）")
        seen_axes.add(axis_name)

        ranking = entry.get("ranking")
        if not isinstance(ranking, list) or set(ranking) != expected_ids or len(ranking) != len(expected_ids):
            raise OpeningSpanHookSchemaError(
                f"axis={axis_name}のrankingが不正です（タイなしの完全な順列が必要）: {ranking}"
            )
        reason = entry.get("reason")
        if not reason or not isinstance(reason, str):
            raise OpeningSpanHookSchemaError(f"axis={axis_name}のreasonが必須です")

    missing_axes = set(OPENING_SPAN_HOOK_AXES) - seen_axes
    if missing_axes:
        raise OpeningSpanHookSchemaError(f"axis_rankingsに不足している軸があります: {missing_axes}")

    overall = data.get("hook_v2_overall_ranking")
    if not isinstance(overall, list) or set(overall) != expected_ids or len(overall) != len(expected_ids):
        raise OpeningSpanHookSchemaError(f"hook_v2_overall_rankingが不正です: {overall}")

    summary_reason = data.get("hook_v2_summary_reason")
    if not summary_reason or not isinstance(summary_reason, str):
        raise OpeningSpanHookSchemaError("hook_v2_summary_reasonが必須です")


def build_opening_span_hook_result(
    data: dict[str, Any],
    expected_draft_ids: list[str],
    span_meta: dict[str, dict[str, Any]],
    batch_id: str | None = None,
    audited_by: str = "unknown",
) -> "OpeningSpanHookEvaluationResult":
    """hook_v2の生JSON（モデル出力）から結果オブジェクトを組み立てる唯一の入口。

    span_metaはfirst_line_hook_evaluator.format_candidates_for_prompt_v2()が返す
    draft_id -> select_opening_span()出力の辞書をそのまま渡すこと（モデルの自己申告ではなく、
    実際に何をspanとして渡したかを正として記録する）。
    """
    validate_opening_span_hook_result(data, expected_draft_ids)
    axis_rankings = [
        OpeningSpanHookAxisResult(axis_name=a["axis_name"], ranking=a["ranking"], reason=a.get("reason", ""))
        for a in data["axis_rankings"]
    ]
    axis_reasons = {a.axis_name: a.reason for a in axis_rankings}
    hook_v2_overall_ranking = list(data["hook_v2_overall_ranking"])
    hook_v2_top_candidate_id = hook_v2_overall_ranking[0] if hook_v2_overall_ranking else None
    return OpeningSpanHookEvaluationResult(
        batch_id=data.get("batch_id", batch_id) or (batch_id or ""),
        draft_ids=list(expected_draft_ids),
        rubric_version=data.get("rubric_version", OPENING_SPAN_HOOK_RUBRIC_VERSION),
        evaluated_opening_span_by_candidate={did: m["effective_span"] for did, m in span_meta.items()},
        opening_span_selection_reason_by_candidate={did: m["selection_reason"] for did, m in span_meta.items()},
        comparison_axis_detected_by_candidate={did: m["comparison_axis_detected"] for did, m in span_meta.items()},
        conclusion_landing_detected_by_candidate={did: m["conclusion_landing_detected"] for did, m in span_meta.items()},
        axis_rankings=axis_rankings,
        axis_reasons=axis_reasons,
        hook_v2_overall_ranking=hook_v2_overall_ranking,
        hook_v2_top_candidate_id=hook_v2_top_candidate_id,
        hook_v2_summary_reason=data.get("hook_v2_summary_reason", ""),
        audited_by=audited_by,
    )


# ==============================================================================
# 2026-08-28 EXP-20260828-METAGATE-DIVERGENCE-01実装。
#
# meta divergence判定: structure evaluator（comparative Gate B本体）とhook_v1
# （first-line hook evaluator）の不一致（structure_top_candidate_id != hook_top_candidate_id）を、
# 「どちらが正しいか」を決める勝敗判定ではなく、「人間確認の価値が高い局面」を示す
# review priority signalとして扱うための研究用layer。外部AI呼び出しは行わない
# （既存のstructure/hook_v1結果に対する純粋な後段分析）。hook_v2はこの判定の入力に
# 採用しない（Run13で優位性が確認できなかったため）。production shipping decision
# には接続しない。
# 設計文書: ops/reports/meta_gate_divergence_design_2026-08-28.md
# ==============================================================================
DIVERGENCE_TYPES = ("none", "structure_only", "hook_only", "mutual_disagreement")
DIVERGENCE_SEVERITIES = ("low", "medium", "high")
RECOMMENDED_REVIEW_MODES = ("auto_candidate_ok", "human_review_required", "human_review_priority_high")


class MetaGateDivergenceSchemaError(AuditSchemaError):
    pass


@dataclass
class MetaGateDivergenceResult:
    """structure/hook_v1のsplitをreview priority signalとして表現する結果。
    どのフィールドもshipping decisionには接続しない（recommendation-only）。"""

    structure_top_candidate_id: str | None
    hook_top_candidate_id: str | None
    structure_hook_alignment: bool | None
    structure_hook_divergence: bool
    divergence_type: str
    divergence_severity: str
    recommended_review_mode: str
    divergence_reason_summary: str
    structure_mapped_gap: float | None = None
    hook_v1_axis_consensus: float | None = None
    human_initial_top: str | None = None
    human_final_top: str | None = None
    divergence_vs_human_observation: str | None = None
    meta_gate_takeaway: str | None = None


def validate_meta_gate_divergence_result(data: dict[str, Any]) -> None:
    """meta_gate_divergence結果の型・許容値を検証する（内部生成物の防御的チェック。
    外部AI出力の検証ではないため、AuditSchemaErrorのサブクラスを流用しつつ
    信頼できない入力向けの厳格さまでは求めない）。"""
    if data.get("divergence_type") not in DIVERGENCE_TYPES:
        raise MetaGateDivergenceSchemaError(f"未知のdivergence_type: {data.get('divergence_type')}（許容値: {DIVERGENCE_TYPES}）")
    if data.get("divergence_severity") not in DIVERGENCE_SEVERITIES:
        raise MetaGateDivergenceSchemaError(f"未知のdivergence_severity: {data.get('divergence_severity')}（許容値: {DIVERGENCE_SEVERITIES}）")
    if data.get("recommended_review_mode") not in RECOMMENDED_REVIEW_MODES:
        raise MetaGateDivergenceSchemaError(f"未知のrecommended_review_mode: {data.get('recommended_review_mode')}（許容値: {RECOMMENDED_REVIEW_MODES}）")
    if not isinstance(data.get("structure_hook_divergence"), bool):
        raise MetaGateDivergenceSchemaError("structure_hook_divergenceはbool必須です")
