"""enrichment_record（学習モードLayer 2: 投稿後非同期enrichment）のpure function層。

minimal_run_log（Layer 1、本線必須、scripts/minimal_run_log.py）とは完全に独立し、
structure/hook/divergenceの研究情報を投稿後にbest-effortで追記するための層。
**失敗してもmainline_statusには一切波及しない。** 外部AI呼び出しは行わない
（既存のstructure_result/hook_result/divergence判定結果に対する後段パッケージングのみ）。

divergence判定ロジック自体はここで再計算しない。post_generation_pipeline.
evaluate_structure_hook_divergence()（EXP-20260828-METAGATE-DIVERGENCE-01）の
出力をそのまま受け取ることで、判定ロジックの重複を避ける。

設計文書: ops/reports/learning_mode_async_enrichment_design_2026-08-28.md

既存Run10〜13との整合（設計メモ）:
    - Run10: Step A disclosure contaminationのため、build_enrichment_record()へ
      step_a_disclosure_contamination=Trueを渡すとhuman_initial_topはNoneとして
      扱われる（Run10で確立したremediationパターン: initial側のみ無効化し、
      final側は有効データとして残す）。structure_vs_human_match/hook_vs_human_match
      はhuman_final_top基準で計算するため、汚染の影響を受けない
    - Run11/Run12: structure_hook_divergence=true。divergence/human双方のデータが
      揃うためenrichment_status="completed"
    - Run13/EXP-20260828-METAGATE-DIVERGENCE-01: 投稿runではなく評価器・判定ロジック
      そのものの研究開発資産のため、enrichment_record生成の対象外
      （build_enrichment_record()を呼ばない——無理に空レコードを作らない）
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from minimal_run_log import ENRICHMENT_STATUSES


class EnrichmentRecordError(ValueError):
    pass


@dataclass
class EnrichmentRecord:
    """投稿後に付与する研究情報。research-only、shipping decisionには一切接続しない。"""

    run_id: str
    structure_top_candidate_id: str | None = None
    hook_top_candidate_id: str | None = None
    structure_hook_divergence: bool | None = None
    divergence_type: str | None = None
    divergence_severity: str | None = None
    recommended_review_mode: str | None = None
    structure_vs_human_match: bool | None = None
    hook_vs_human_match: bool | None = None
    meta_gate_takeaway: str | None = None
    human_initial_top: str | None = None
    human_final_top: str | None = None
    recommendation_influence_level: str | None = None
    human_confidence_shift: str | None = None
    comparative_snapshot_persisted: bool | None = None
    mapping_version: str | None = None
    raw_normalized_scores: dict[str, float] | None = None
    mapped_normalized_scores: dict[str, float] | None = None
    step_a_disclosure_contamination: bool | None = None
    enrichment_status: str = "not_started"
    enrichment_failure_reason: str | None = None
    # 2026-08-31 X API実績値（scripts/x_post_analytics.py）への軽量接続。
    # 未取得のrunではNone/Falseのままでよい（後方互換）。
    post_analytics_available: bool = False
    post_analytics_file_path: str | None = None


def build_enrichment_record(
    run_id: str,
    divergence_result: dict[str, Any] | None = None,
    human_initial_top: str | None = None,
    human_final_top: str | None = None,
    human_initial_confidence: str | None = None,
    human_final_confidence: str | None = None,
    recommendation_influence_level: str | None = None,
    comparative_snapshot_persisted: bool | None = None,
    mapping_version: str | None = None,
    raw_normalized_scores: dict[str, float] | None = None,
    mapped_normalized_scores: dict[str, float] | None = None,
    step_a_disclosure_contamination: bool = False,
) -> EnrichmentRecord:
    """既存の保存済みstructure/hook/divergence結果とhuman selectionから、
    enrichment_recordを組み立てる純粋な後段計算。外部AI呼び出しは一切行わない。

    divergence_resultには、post_generation_pipeline.evaluate_structure_hook_divergence()
    の戻り値（dict）をそのまま渡すこと。divergenceの判定ロジック自体はこの関数内では
    再計算しない。divergence_result=Noneでも構わない（research情報が全く無い＝
    enrichment_status="not_started"のレコードとして組み立てられる）。

    step_a_disclosure_contamination=Trueの場合、human_initial_topはNoneとして扱う
    （Run10のremediationパターン: initial側のみ無効化、final側は有効データとして残す）。
    structure_vs_human_match/hook_vs_human_matchはhuman_final_top基準で計算するため、
    Step A汚染の影響を受けない。
    """
    if not run_id:
        raise EnrichmentRecordError("run_idは必須です")

    dr = divergence_result or {}
    structure_top = dr.get("structure_top_candidate_id")
    hook_top = dr.get("hook_top_candidate_id")

    effective_initial_top = None if step_a_disclosure_contamination else human_initial_top

    structure_vs_human_match: bool | None = None
    hook_vs_human_match: bool | None = None
    if human_final_top is not None:
        if structure_top is not None:
            structure_vs_human_match = structure_top == human_final_top
        if hook_top is not None:
            hook_vs_human_match = hook_top == human_final_top

    human_confidence_shift: str | None = None
    if (
        human_initial_confidence is not None
        and human_final_confidence is not None
        and not step_a_disclosure_contamination
    ):
        human_confidence_shift = f"{human_initial_confidence}->{human_final_confidence}"

    has_divergence_data = bool(dr)
    has_human_data = human_final_top is not None
    if has_divergence_data and has_human_data:
        enrichment_status = "completed"
    elif has_divergence_data or has_human_data:
        enrichment_status = "partial"
    else:
        enrichment_status = "not_started"

    return EnrichmentRecord(
        run_id=run_id,
        structure_top_candidate_id=structure_top,
        hook_top_candidate_id=hook_top,
        structure_hook_divergence=dr.get("structure_hook_divergence"),
        divergence_type=dr.get("divergence_type"),
        divergence_severity=dr.get("divergence_severity"),
        recommended_review_mode=dr.get("recommended_review_mode"),
        structure_vs_human_match=structure_vs_human_match,
        hook_vs_human_match=hook_vs_human_match,
        meta_gate_takeaway=dr.get("meta_gate_takeaway") or dr.get("divergence_reason_summary"),
        human_initial_top=effective_initial_top,
        human_final_top=human_final_top,
        recommendation_influence_level=recommendation_influence_level,
        human_confidence_shift=human_confidence_shift,
        comparative_snapshot_persisted=comparative_snapshot_persisted,
        mapping_version=mapping_version,
        raw_normalized_scores=raw_normalized_scores,
        mapped_normalized_scores=mapped_normalized_scores,
        step_a_disclosure_contamination=step_a_disclosure_contamination,
        enrichment_status=enrichment_status,
    )


def mark_post_analytics_available(record: EnrichmentRecord, file_path: str) -> EnrichmentRecord:
    """X API実績値（scripts/x_post_analytics.py）が取得済みであることを軽量に記録する。
    enrichment_statusには一切触れない。
    """
    record.post_analytics_available = True
    record.post_analytics_file_path = file_path
    return record


def build_failed_enrichment_record(run_id: str, reason: str) -> EnrichmentRecord:
    """enrichment処理中に例外が発生した場合のnon-blockingな結果を組み立てる。
    run_id以外のフィールドはすべてNoneのまま、enrichment_status="failed_non_blocking"
    として返す（mainline_statusには一切波及させないという設計保証を型で表現する）。
    """
    return EnrichmentRecord(
        run_id=run_id,
        enrichment_status="failed_non_blocking",
        enrichment_failure_reason=reason,
    )


def enrichment_record_to_dict(record: EnrichmentRecord) -> dict[str, Any]:
    return asdict(record)


def save_enrichment_record(
    record: EnrichmentRecord, repo_root: Path | str, date_str: str | None = None
) -> Path:
    """enrichment_recordをops/reports/enrichment_record_<date>_<run_id>.jsonとして保存する。
    minimal_run_log（ops/reports/minimal_run_log_*.json）とはファイルを分け、
    責務の分離をファイルシステム上でも可視化する。
    """
    repo_root = Path(repo_root)
    date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = repo_root / "ops" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"enrichment_record_{date_str}_{record.run_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(enrichment_record_to_dict(record), f, ensure_ascii=False, indent=2)
    return out_path
