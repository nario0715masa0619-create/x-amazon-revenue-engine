"""Comparative Gate Bのranking -> normalized scoreマッピング層（2026-08-26 R2-2追加）。

背景: EXP-20260825-QS-MULTIDRAFT-01・EXP-20260825-QS-SHADOWMODE-RUN1-01・
EXP-20260826-QS-SHADOWMODE-RUN2-01の3実験で、comparative Gate Bのv1変換
（external_audit_schema.convert_comparative_rankings_to_normalized_scores、
Borda count方式・0-100点フル活用）は、順位方向は正しく返す一方で、
70-30・0-100といった過大なgapを生む「gap over-amplification」を繰り返し起こしていた。

このモジュールは、v1変換が既に確定させた「順位方向」を一切変えずに、
score gapだけをoperational range（デフォルト67-84点）へ滑らかに圧縮する
tier_bounded_v1マッピングを提供する。

設計方針（PDCA台帳 EXP-20260826-QS-MAPPING-R2-2-01参照）:
- rank baseline（1位=78, 2位=75, 3位=72, 4位=69、3点刻みで外挿）をまず割り当てる
- 軸別tier（strong/medium/weak）の実測差から+0/+1/+2の調整幅を機械的に算出する
  （fabricationではなく、モデルが実際に返したtiersフィールドの集計）
- 軸別confidenceの実測平均から同様に+0/+1/+2の調整幅を算出する
- 最終的にmin/maxでcapし、67-84点のoperational rangeに収める
- comparative rankingそのもの（誰が1位か）は一切変更しない。変更するのは数値表現だけ

このモジュールは既存のGate B（single-draft）・teacher_reference_score・Gate A・
shipping decisionには一切影響しない。scripts/external_audit_schema.pyの
QUALITY_SCORE_WEIGHTS・classify_quality_band_from_score等は変更せず再利用する。
"""

from __future__ import annotations

from typing import Any

from external_audit_schema import classify_quality_band_from_score

MAPPING_VERSION = "tier_bounded_v1"

# rank baseline（1位〜4位）。5位以降は3点刻みで外挿する。
_RANK_BASELINE_SCORES = [78.0, 75.0, 72.0, 69.0]
_RANK_BASELINE_STEP = 3.0

_TIER_RANK = {"strong": 2, "medium": 1, "weak": 0}
_CONFIDENCE_RANK = {"high": 2, "medium": 1, "low": 0}

DEFAULT_MIN_SCORE = 67.0
DEFAULT_MAX_SCORE = 84.0


def build_rank_baseline_scores(ranking: list[str]) -> dict[str, float]:
    """順位（1位を先頭とするdraft_idの並び）から、rank baselineスコアを割り当てる。
    1位=78, 2位=75, 3位=72, 4位=69。5位以降は3点刻みで外挿する。"""
    result: dict[str, float] = {}
    for i, draft_id in enumerate(ranking):
        if i < len(_RANK_BASELINE_SCORES):
            result[draft_id] = _RANK_BASELINE_SCORES[i]
        else:
            result[draft_id] = _RANK_BASELINE_SCORES[-1] - _RANK_BASELINE_STEP * (i - len(_RANK_BASELINE_SCORES) + 1)
    return result


def _axis_field(axis: Any, key: str) -> Any:
    """axis_resultsの要素がdataclass（ComparativeAxisResult）でもdict（JSON往復後）でも
    同じように扱えるようにする薄いヘルパー。"""
    if isinstance(axis, dict):
        return axis.get(key)
    return getattr(axis, key, None)


def calculate_tier_adjustment(axis_results: list[Any], winner_id: str, loser_id: str) -> float:
    """winner_id/loser_idそれぞれの軸別tier（strong/medium/weak）を比較し、
    平均tier差から+0.0/+1.0/+2.0の調整幅を算出する（winnerに+delta、loserに-deltaを
    適用する想定。符号の適用は呼び出し側が行う）。

    fabricationではなく、モデルが実際に返したtiersフィールドの実測集計である。
    """
    gaps = []
    for axis in axis_results:
        tiers = _axis_field(axis, "tiers") or {}
        w_tier = tiers.get(winner_id)
        l_tier = tiers.get(loser_id)
        if w_tier in _TIER_RANK and l_tier in _TIER_RANK:
            gaps.append(_TIER_RANK[w_tier] - _TIER_RANK[l_tier])
    if not gaps:
        return 0.0
    avg_gap = sum(gaps) / len(gaps)
    if avg_gap >= 1.5:
        return 2.0
    if avg_gap >= 0.5:
        return 1.0
    return 0.0


def calculate_confidence_adjustment(axis_results: list[Any]) -> float:
    """axis_results全体のconfidence（low/medium/high）の平均から+0.0/+1.0/+2.0の
    調整幅を算出する（winnerに+delta、loserに-deltaを適用する想定）。"""
    vals = []
    for axis in axis_results:
        conf = _axis_field(axis, "confidence")
        if conf in _CONFIDENCE_RANK:
            vals.append(_CONFIDENCE_RANK[conf])
    if not vals:
        return 0.0
    avg = sum(vals) / len(vals)
    if avg >= 1.5:
        return 2.0
    if avg >= 0.5:
        return 1.0
    return 0.0


def apply_score_caps(
    score: float, min_score: float = DEFAULT_MIN_SCORE, max_score: float = DEFAULT_MAX_SCORE
) -> tuple[float, bool]:
    """scoreをmin_score/max_scoreの範囲へクリップする。(clipped_score, capが適用されたか)を返す。"""
    capped = max(min_score, min(max_score, score))
    return capped, (capped != score)


def convert_comparative_rankings_to_bounded_scores(
    draft_ids: list[str],
    axis_results: list[Any],
    overall_ranking: list[str] | None = None,
    original_normalized_scores: dict[str, int] | None = None,
    min_score: float = DEFAULT_MIN_SCORE,
    max_score: float = DEFAULT_MAX_SCORE,
) -> dict[str, Any]:
    """comparative rankingの順位方向を保ったまま、score gapを滑らかにする（tier_bounded_v1）。

    順位の決定方法（優先順）:
    1. original_normalized_scores（v1 Borda。external_audit_schema.
       convert_comparative_rankings_to_normalized_scores()の出力）が渡されていれば、
       それを降順ソートして順位を決める。v1が既に確定させた「誰が1位か」という
       方向性を、そのままこの関数でも維持するため。
    2. 無ければoverall_ranking（モデル自己申告の参考順位）を使う。
    3. どちらも無ければdraft_idsの入力順をそのまま順位とみなす。

    現時点ではn=2バッチ（同一候補の2draft比較）を主用途として設計しており、
    tier/confidence調整は先頭（1位）と末尾（最下位）の間でのみ計算する
    （n>=3の場合、中間順位はrank baselineのみを使い、調整は加えない簡易実装）。
    """
    if original_normalized_scores:
        ranking = sorted(draft_ids, key=lambda d: original_normalized_scores.get(d, 0), reverse=True)
    elif overall_ranking:
        ranking = [d for d in overall_ranking if d in draft_ids]
        for d in draft_ids:
            if d not in ranking:
                ranking.append(d)
    else:
        ranking = list(draft_ids)

    rank_baseline = build_rank_baseline_scores(ranking)

    tier_adjustment = {d: 0.0 for d in draft_ids}
    confidence_adjustment = {d: 0.0 for d in draft_ids}
    if len(ranking) >= 2:
        winner_id, loser_id = ranking[0], ranking[-1]
        t_delta = calculate_tier_adjustment(axis_results, winner_id, loser_id)
        c_delta = calculate_confidence_adjustment(axis_results)
        tier_adjustment[winner_id] = t_delta
        tier_adjustment[loser_id] = -t_delta
        confidence_adjustment[winner_id] = c_delta
        confidence_adjustment[loser_id] = -c_delta

    final_before_cap = {
        d: rank_baseline[d] + tier_adjustment[d] + confidence_adjustment[d] for d in draft_ids
    }

    mapped_scores: dict[str, int] = {}
    cap_applied: dict[str, bool] = {}
    for d in draft_ids:
        capped, was_capped = apply_score_caps(final_before_cap[d], min_score, max_score)
        mapped_scores[d] = round(capped)
        cap_applied[d] = was_capped

    mapped_bands = {d: classify_quality_band_from_score(s) for d, s in mapped_scores.items()}

    return {
        "mapping_version": MAPPING_VERSION,
        "mapping_strategy": "rank_baseline + tier_adjustment + confidence_adjustment, capped[min,max]",
        "ranking_used_for_baseline": ranking,
        "rank_baseline_scores": rank_baseline,
        "tier_adjustment": tier_adjustment,
        "confidence_adjustment": confidence_adjustment,
        "final_mapped_scores_before_cap": final_before_cap,
        "mapped_scores": mapped_scores,
        "mapped_bands": mapped_bands,
        "mapping_cap_applied": cap_applied,
        "mapping_notes": f"min={min_score}, max={max_score}",
    }


def detect_gap_over_amplification(
    scores: dict[str, float], pairwise_threshold: float = 7.0, spread_threshold: float = 15.0
) -> bool:
    """scoresのspread（またはn=2の場合のpairwise gap）が閾値を超えていればTrue。
    デフォルト閾値は運用ガイドライン「top-1 vs top-2 gapは通常2〜5点、極端でも7点まで、
    4案バッチで15点超のspreadは原則出さない」に基づく。"""
    vals = list(scores.values())
    if len(vals) < 2:
        return False
    spread = max(vals) - min(vals)
    if len(vals) == 2:
        return spread > pairwise_threshold
    return spread > spread_threshold


def summarize_mapping_changes(
    before_scores: dict[str, float], after_scores: dict[str, float]
) -> dict[str, Any]:
    """マッピング適用前後のスコアを比較し、spread縮小・top-1維持可否を要約する。"""
    if not before_scores or not after_scores:
        return {
            "score_spread_before": None, "score_spread_after": None,
            "top_candidate_before": None, "top_candidate_after": None,
            "top_candidate_changed": None,
        }
    before_vals = list(before_scores.values())
    after_vals = list(after_scores.values())
    top_before = max(before_scores, key=before_scores.get)
    top_after = max(after_scores, key=after_scores.get)
    return {
        "score_spread_before": max(before_vals) - min(before_vals),
        "score_spread_after": max(after_vals) - min(after_vals),
        "top_candidate_before": top_before,
        "top_candidate_after": top_after,
        "top_candidate_changed": top_before != top_after,
        "gap_over_amplification_before": detect_gap_over_amplification(before_scores),
        "gap_over_amplification_after": detect_gap_over_amplification(after_scores),
    }


def build_comparative_bounded_mapping_result(
    draft_ids: list[str],
    axis_results: list[Any],
    original_normalized_scores: dict[str, int],
    overall_ranking: list[str] | None = None,
    min_score: float = DEFAULT_MIN_SCORE,
    max_score: float = DEFAULT_MAX_SCORE,
) -> dict[str, Any]:
    """1バッチ分のraw comparative結果（既存のv1 Borda正規化済みnormalized_scoresと
    axis_results）から、tier_bounded_v1マッピングとbefore/after比較をまとめて返す。
    新規API呼び出し不要（既存の実監査結果を再利用するオフライン再計算に対応）。
    """
    mapping = convert_comparative_rankings_to_bounded_scores(
        draft_ids, axis_results, overall_ranking=overall_ranking,
        original_normalized_scores=original_normalized_scores,
        min_score=min_score, max_score=max_score,
    )
    change_summary = summarize_mapping_changes(original_normalized_scores, mapping["mapped_scores"])
    return {**mapping, "change_summary": change_summary}
