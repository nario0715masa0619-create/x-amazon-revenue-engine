"""weekly_learning_review（学習モードLayer 3: 週次研究集計）のpure function層。

minimal_run_log（Layer 1、scripts/minimal_run_log.py）とenrichment_record
（Layer 2、scripts/enrichment_record.py）を入力に、run単位の詳細を毎回読む
運用ではなく、週次でまとめて研究知見として要約する。外部AI呼び出しは行わない
（既存の保存済みログに対する純粋な集計）。**週次集計はresearch assetであり、
本線完了条件にはしない。** 集計対象のrunが1件も無くても、あるいは集計自体が
失敗しても、投稿運用（minimal_run_log）には一切影響しない。

雛形（空テンプレート）: ops/reports/weekly_learning_review_template_2026-08-28.md
設計文書: ops/reports/learning_mode_async_enrichment_design_2026-08-28.md
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from topic_group_state import TopicGroupState, detect_theme_signature_splits


class WeeklyLearningReviewError(ValueError):
    pass


@dataclass
class WeeklyLearningReview:
    """週次研究集計の結果。research asset。shipping decisionには一切接続しない。"""

    period_start: str | None
    period_end: str | None
    run_ids: list[str] = field(default_factory=list)
    total_run_count: int = 0
    mainline_completed_count: int = 0
    mainline_closed_incomplete_count: int = 0
    mainline_failed_count: int = 0
    enrichment_completed_count: int = 0
    enrichment_partial_count: int = 0
    enrichment_failed_non_blocking_count: int = 0
    enrichment_not_started_count: int = 0
    structure_hook_divergence_count: int = 0
    non_divergence_count: int = 0
    split_human_matched_structure_count: int = 0
    split_human_matched_hook_count: int = 0
    split_human_matched_neither_count: int = 0
    contamination_count: int = 0
    fallback_source_used_count: int = 0
    fallback_source_usage_rate: float | None = None
    source_post_id_distribution: dict[str, int] = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)
    next_week_research_focus: list[str] = field(default_factory=list)
    one_line_takeaway: str | None = None
    # 2026-09-01追加（GOV-20260901-TOPIC-GROUP-SPLIT-DETECTION-01）: 同一theme_signatureが
    # 複数のtopic_group_idに分裂しているケースのread-only検出結果。既存フィールドは無変更。
    topic_group_signature_splits: list[dict[str, Any]] = field(default_factory=list)


def aggregate_weekly_learning_review(
    minimal_run_logs: list[dict[str, Any]],
    enrichment_records: list[dict[str, Any]],
    period_start: str | None = None,
    period_end: str | None = None,
    next_week_research_focus: list[str] | None = None,
    one_line_takeaway: str | None = None,
    topic_group_store: dict[str, TopicGroupState] | None = None,
) -> WeeklyLearningReview:
    """minimal_run_logとenrichment_record（run_idで対応付け）から週次集計を組み立てる。

    minimal_run_logsとenrichment_recordsの件数は一致していなくてよい（enrichment未実施の
    runがあっても集計は成立する）。run_idが一致しないenrichment_recordは無視する。
    集計対象が0件でも例外を投げず、全項目0/空のWeeklyLearningReviewを返す
    （「観察不可（n不足）」として扱えるようにするため）。

    topic_group_store（省略可、デフォルトNoneで既存呼び出し互換）を渡すと、
    同一theme_signatureが複数topic_group_idに分裂しているケースをread-onlyで検出し
    topic_group_signature_splitsへ格納する。detect_theme_signature_splits()自体は
    storeを一切変更しない（build_topic_group()のグルーピングロジックには触れない）。
    """
    topic_group_signature_splits = (
        detect_theme_signature_splits(topic_group_store) if topic_group_store else []
    )
    enrichment_by_run_id = {r.get("run_id"): r for r in enrichment_records if r.get("run_id")}

    run_ids = [log.get("run_id") for log in minimal_run_logs if log.get("run_id")]
    total_run_count = len(minimal_run_logs)

    mainline_status_counts = Counter(log.get("mainline_status") for log in minimal_run_logs)
    fallback_used_count = sum(1 for log in minimal_run_logs if log.get("used_fallback_source") is True)
    source_dist = Counter(
        log.get("source_post_id") for log in minimal_run_logs if log.get("source_post_id")
    )

    enrichment_status_counts: Counter[str] = Counter()
    divergence_count = 0
    non_divergence_count = 0
    human_matched_structure = 0
    human_matched_hook = 0
    human_matched_neither = 0
    contamination_count = 0

    for log in minimal_run_logs:
        run_id = log.get("run_id")
        record = enrichment_by_run_id.get(run_id)
        if record is None:
            enrichment_status_counts["not_started"] += 1
            continue
        status = record.get("enrichment_status", "not_started")
        enrichment_status_counts[status] += 1

        if record.get("step_a_disclosure_contamination"):
            contamination_count += 1

        divergence = record.get("structure_hook_divergence")
        if divergence is True:
            divergence_count += 1
            structure_match = record.get("structure_vs_human_match")
            hook_match = record.get("hook_vs_human_match")
            if structure_match:
                human_matched_structure += 1
            elif hook_match:
                human_matched_hook += 1
            else:
                human_matched_neither += 1
        elif divergence is False:
            non_divergence_count += 1

    fallback_usage_rate = (fallback_used_count / total_run_count) if total_run_count else None

    observations: list[str] = []
    if total_run_count == 0:
        observations.append("観察不可（n不足）: 対象期間にminimal_run_logが0件だった")
    else:
        if divergence_count > 0:
            observations.append(
                f"split発生{divergence_count}件のうち、structure側が的中{human_matched_structure}件、"
                f"hook側が的中{human_matched_hook}件、どちらとも不一致{human_matched_neither}件"
            )
        else:
            observations.append("split（structure_hook_divergence=true）は今週観測されなかった（n不足の可能性あり）")
        if contamination_count > 0:
            observations.append(f"Step A disclosure contaminationが{contamination_count}件発生した")
        if fallback_usage_rate is not None:
            observations.append(f"fallback source使用率: {fallback_usage_rate:.0%}（{fallback_used_count}/{total_run_count}件）")

    return WeeklyLearningReview(
        period_start=period_start,
        period_end=period_end,
        run_ids=run_ids,
        total_run_count=total_run_count,
        mainline_completed_count=mainline_status_counts.get("completed", 0),
        mainline_closed_incomplete_count=mainline_status_counts.get("closed_incomplete", 0),
        mainline_failed_count=mainline_status_counts.get("failed", 0),
        enrichment_completed_count=enrichment_status_counts.get("completed", 0),
        enrichment_partial_count=enrichment_status_counts.get("partial", 0),
        enrichment_failed_non_blocking_count=enrichment_status_counts.get("failed_non_blocking", 0),
        enrichment_not_started_count=enrichment_status_counts.get("not_started", 0),
        structure_hook_divergence_count=divergence_count,
        non_divergence_count=non_divergence_count,
        split_human_matched_structure_count=human_matched_structure,
        split_human_matched_hook_count=human_matched_hook,
        split_human_matched_neither_count=human_matched_neither,
        contamination_count=contamination_count,
        fallback_source_used_count=fallback_used_count,
        fallback_source_usage_rate=fallback_usage_rate,
        source_post_id_distribution=dict(source_dist),
        observations=observations,
        next_week_research_focus=list(next_week_research_focus or []),
        one_line_takeaway=one_line_takeaway,
        topic_group_signature_splits=topic_group_signature_splits,
    )


def weekly_learning_review_to_dict(review: WeeklyLearningReview) -> dict[str, Any]:
    return asdict(review)


def save_weekly_learning_review(
    review: WeeklyLearningReview, repo_root: Path | str, label: str | None = None
) -> Path:
    """weekly_learning_reviewをops/reports/weekly_learning_review_<label>.jsonとして保存する。
    labelを渡さない場合はperiod_end（無ければ実行日）を使う。
    """
    repo_root = Path(repo_root)
    label = label or review.period_end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = repo_root / "ops" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"weekly_learning_review_{label}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(weekly_learning_review_to_dict(review), f, ensure_ascii=False, indent=2)
    return out_path


def mark_run_weekly_aggregation_included(minimal_run_log_path: str | Path) -> dict[str, Any]:
    """指定したminimal_run_log JSONのweekly_aggregation_statusのみをpending->includedへ
    更新する。**更新に失敗してもmainlineを壊さない**（例外を送出せず、結果dictの
    successフラグで成否を示す。呼び出し元はこの結果を無視しても投稿運用には影響しない）。
    """
    try:
        path = Path(minimal_run_log_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["weekly_aggregation_status"] = "included"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"success": True, "path": str(path)}
    except Exception as e:  # noqa: BLE001 - 週次集計のマーキング失敗もnon-blocking
        return {"success": False, "error": str(e)}


def render_weekly_learning_review_markdown(review: WeeklyLearningReview, title: str) -> str:
    """weekly_learning_reviewを、ops/reports/weekly_learning_review_template_2026-08-28.mdの
    節構成に沿ったMarkdownへレンダリングする（1. 本線運用状況〜7. one_line_takeaway）。
    """
    r = review
    lines = [f"# {title}", ""]
    lines.append(f"対象期間: {r.period_start or '不明'} 〜 {r.period_end or '不明'}（対象run: {len(r.run_ids)}件）")
    lines.append("")
    lines.append("## 1. 今週の本線運用状況")
    lines.append("")
    lines.append(f"- 総run数: {r.total_run_count}")
    lines.append(f"- `mainline_status=completed`: {r.mainline_completed_count}件")
    lines.append(f"- `closed_incomplete`: {r.mainline_closed_incomplete_count}件")
    lines.append(f"- `failed`: {r.mainline_failed_count}件")
    lines.append("")
    lines.append("## 2. enrichment実行状況")
    lines.append("")
    lines.append(f"- `completed`: {r.enrichment_completed_count}件")
    lines.append(f"- `partial`: {r.enrichment_partial_count}件")
    lines.append(f"- `failed_non_blocking`: {r.enrichment_failed_non_blocking_count}件")
    lines.append(f"- `not_started`: {r.enrichment_not_started_count}件")
    lines.append("")
    lines.append("## 3. divergence発生状況")
    lines.append("")
    lines.append(f"- `structure_hook_divergence=true`: {r.structure_hook_divergence_count}件")
    lines.append(f"- non-divergence: {r.non_divergence_count}件")
    lines.append("")
    lines.append("## 4. human vs structure/hook傾向")
    lines.append("")
    lines.append(f"- split時にstructure側が的中: {r.split_human_matched_structure_count}件")
    lines.append(f"- split時にhook側が的中: {r.split_human_matched_hook_count}件")
    lines.append(f"- split時にどちらとも不一致: {r.split_human_matched_neither_count}件")
    lines.append("")
    lines.append("## 5. contamination / fallback / source variability")
    lines.append("")
    lines.append(f"- Step A disclosure contamination: {r.contamination_count}件")
    fallback_rate_str = f"{r.fallback_source_usage_rate:.0%}" if r.fallback_source_usage_rate is not None else "観察不可（n不足）"
    lines.append(f"- fallback source使用率: {fallback_rate_str}（{r.fallback_source_used_count}/{r.total_run_count}件）")
    lines.append(f"- source別分布: {r.source_post_id_distribution if r.source_post_id_distribution else '観察不可（n不足）'}")
    for obs in r.observations:
        lines.append(f"- {obs}")
    lines.append("")
    lines.append("## 6. 次週の研究フォーカス")
    lines.append("")
    if r.next_week_research_focus:
        for item in r.next_week_research_focus:
            lines.append(f"- {item}")
    else:
        lines.append("- （未設定）")
    lines.append("")
    lines.append("## 7. one_line_takeaway")
    lines.append("")
    lines.append(r.one_line_takeaway or "（未設定）")
    lines.append("")
    lines.append("## 8. topic_group分裂検出（read-only分析）")
    lines.append("")
    lines.append(
        "同一theme_signatureが複数のtopic_group_idに分裂しているケースを検出する。"
        "topic_group状態・mainline候補生成ロジックへの書き込みは行わない（分析のみ）。"
    )
    lines.append("")
    if not r.topic_group_signature_splits:
        lines.append("- 分裂は検出されなかった（または topic_group_store が集計に渡されていない）")
    else:
        for split in r.topic_group_signature_splits:
            if split["split_type"] == "exact_signature_match":
                lines.append(f"- [exact_signature_match] theme_signature: `{split['theme_signature']}`")
            else:
                lines.append(
                    f"- [near_duplicate_signature] signature類似度={split['similarity']}: "
                    f"`{split['theme_signature']}`"
                )
            lines.append(f"  - 分裂先topic_group_id数: {len(split['topic_group_ids'])}")
            for g in split["topic_groups"]:
                lines.append(
                    f"  - `{g['topic_group_id']}` (theme_signature=`{g['theme_signature']}`): "
                    f"status={g['topic_status']}, "
                    f"performance_band={g['topic_performance_band']}, "
                    f"last_published_at={g['topic_last_published_at'] or 'なし'}, "
                    f"mainline_run_count={g['mainline_run_count']}"
                )
            lines.append(
                f"  - 合算した場合の実質露出回数（mainline_run_count合計）: "
                f"{split['combined_mainline_run_count']}"
            )
    lines.append("")
    return "\n".join(lines)
