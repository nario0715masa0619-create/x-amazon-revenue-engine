"""minimal_run_log（学習モードLayer 1: 投稿時最小ログ）のpure function層。

comparative Gate B・first-line hook evaluator・divergence meta-gate等のresearch/shadow層とは
完全に独立した、投稿運用が止まらないことを保証する最小事実ログ。「何を投稿候補として出し、
人間がどれを選んだか」だけを記録する。外部API呼び出しは一切行わない。

設計文書: ops/reports/learning_mode_async_enrichment_design_2026-08-28.md

既存Run10〜13との整合（設計メモ）:
    - Run10: Step A disclosure contaminationがあってもGate A survivors確保・human final
      judgment取得済みのため mainline_status=completed。汚染はenrichment側の問題であり
      本線には影響しない（このモジュールが表現する状態そのもの）
    - Run11: mainline_status=completed（human_selected_top=gadget-run11-C2）
    - Run12: mainline_status=completed（human_selected_top=gadget-run12-E）
    - Run13 / EXP-20260828-METAGATE-DIVERGENCE-01: 投稿runではなく評価器・判定ロジックの
      研究開発資産のため、そもそもminimal_run_logの対象外（新規draft投稿が発生していない）
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAINLINE_STATUSES = ("completed", "closed_incomplete", "failed")
ENRICHMENT_STATUSES = ("not_started", "partial", "completed", "failed_non_blocking")
WEEKLY_AGGREGATION_STATUSES = ("pending", "included")


class MinimalRunLogError(ValueError):
    pass


@dataclass
class MinimalRunLog:
    """投稿時に必ず残す最小事実ログ。research/enrichment情報は一切含まない。"""

    run_id: str
    source_post_id: str | None
    target_layer: str | None
    draft_ids: list[str] = field(default_factory=list)
    gate_a_pass_ids: list[str] = field(default_factory=list)
    human_selected_top: str | None = None
    published_draft_id: str | None = None
    selection_reason_short: str | None = None
    primary_source_post_id: str | None = None
    fallback_source_post_id: str | None = None
    used_fallback_source: bool = False
    mainline_status: str = "closed_incomplete"
    enrichment_status: str = "not_started"
    weekly_aggregation_status: str = "pending"
    research_followup_required: bool = False
    published_at: str | None = None
    post_url: str | None = None
    # 2026-08-30 posted-theme exclusion（投稿済みテーマのmainline再流入防止）ガード結果。
    # scripts/posted_theme_registry.check_posted_theme_guard()の出力をそのまま格納する。
    # ガード未実施のrunではすべてNone/未チェックのままでよい（既存run・後方互換）。
    posted_theme_check_status: str | None = None
    posted_theme_match_type: str | None = None
    matched_past_run_id: str | None = None
    matched_post_url: str | None = None
    matched_theme_signature: str | None = None
    block_mainline: bool | None = None
    route_to_research: bool | None = None
    cooldown_active: bool | None = None
    posted_theme_check_reason: str | None = None
    # 2026-08-31 X API実績値（impression/engagement等）の接続用フィールド。
    # scripts/x_post_analytics.pyが取得した結果を、mark_analytics_status()経由で
    # 反映する。未取得のrunではすべてNoneのままでよい（既存run・後方互換）。
    analytics_status: str | None = None
    analytics_file_path: str | None = None
    latest_impression_count: int | None = None


def build_minimal_run_log(
    run_id: str,
    source_post_id: str | None,
    target_layer: str | None,
    draft_ids: list[str] | None = None,
    gate_a_pass_ids: list[str] | None = None,
    human_selected_top: str | None = None,
    published_draft_id: str | None = None,
    selection_reason_short: str | None = None,
    primary_source_post_id: str | None = None,
    fallback_source_post_id: str | None = None,
    used_fallback_source: bool = False,
    research_followup_required: bool = False,
    published_at: str | None = None,
    post_url: str | None = None,
    posted_theme_check: dict[str, Any] | None = None,
) -> MinimalRunLog:
    """Gate A結果とhuman selectionからminimal_run_logを組み立てる唯一の入口。

    mainline完了ルール: human_selected_topが与えられていれば
    （＝人間が1本選べた時点で）mainline_status="completed"とする。
    与えられていなければ"closed_incomplete"（Gate A survivors不足等で本線が
    完走しなかった、という既存run（Run8/Run9等）と同じ位置づけ）とする。

    structure_top_candidate_id/hook_top_candidate_id等の研究情報はこの関数の
    引数に一切含まれない——それらはenrichment_record側の責務であり、本線の
    完了判定には使わない、という設計上の保証をシグネチャ自体で表現している。
    値が未取得の項目はNoneのまま保持し、欠損として扱う（捏造補完しない）。

    posted_theme_checkに`posted_theme_registry.check_posted_theme_guard()`の戻り値を
    渡すと、その判定結果（match_type/block_mainline/route_to_research等）をログへ
    そのまま格納する。渡さない場合はposted-theme guard未実施として全項目Noneのままになる
    （mainline_statusの判定ロジック自体には一切影響しない——guardはblockするかどうかを
    示すシグナルを記録するだけで、mainline_statusを直接書き換えることはしない。blockする
    場合の運用判断——例えばhuman selectionへ進めない等——は呼び出し側の責務とする）。
    """
    if not run_id:
        raise MinimalRunLogError("run_idは必須です")

    mainline_status = "completed" if human_selected_top else "closed_incomplete"

    posted_theme_check = posted_theme_check or {}

    return MinimalRunLog(
        run_id=run_id,
        source_post_id=source_post_id,
        target_layer=target_layer,
        draft_ids=list(draft_ids or []),
        gate_a_pass_ids=list(gate_a_pass_ids or []),
        human_selected_top=human_selected_top,
        published_draft_id=published_draft_id,
        selection_reason_short=selection_reason_short,
        primary_source_post_id=primary_source_post_id,
        fallback_source_post_id=fallback_source_post_id,
        used_fallback_source=bool(used_fallback_source),
        mainline_status=mainline_status,
        enrichment_status="not_started",
        weekly_aggregation_status="pending",
        research_followup_required=bool(research_followup_required),
        published_at=published_at,
        post_url=post_url,
        posted_theme_check_status=posted_theme_check.get("posted_theme_check_status"),
        posted_theme_match_type=posted_theme_check.get("posted_theme_match_type"),
        matched_past_run_id=posted_theme_check.get("matched_past_run_id"),
        matched_post_url=posted_theme_check.get("matched_post_url"),
        matched_theme_signature=posted_theme_check.get("matched_theme_signature"),
        block_mainline=posted_theme_check.get("block_mainline"),
        route_to_research=posted_theme_check.get("route_to_research"),
        cooldown_active=posted_theme_check.get("cooldown_active"),
        posted_theme_check_reason=posted_theme_check.get("posted_theme_check_reason"),
    )


def mark_mainline_failed(log: MinimalRunLog, reason: str | None = None) -> MinimalRunLog:
    """本線が構造的に完走できなかった明示的な失敗ケース（想定外の例外等）用。
    "closed_incomplete"（候補不足等での正直なクローズ）とは意図的に区別する。
    build_minimal_run_log()は自動でこの状態を推測しない——呼び出し側が実際の
    失敗を検知した場合にのみ明示的に呼ぶこと。
    """
    log.mainline_status = "failed"
    return log


def mark_enrichment_status(log: MinimalRunLog, status: str) -> MinimalRunLog:
    """enrichment_statusのみを更新する。mainline_statusには一切触れない
    （enrichment失敗をmainline失敗へ波及させない、という設計保証点）。"""
    if status not in ENRICHMENT_STATUSES:
        raise MinimalRunLogError(f"未知のenrichment_status: {status}（許容値: {ENRICHMENT_STATUSES}）")
    log.enrichment_status = status
    return log


def mark_weekly_aggregation_included(log: MinimalRunLog) -> MinimalRunLog:
    """週次集計に組み込まれたことを記録する。"""
    log.weekly_aggregation_status = "included"
    return log


def mark_analytics_status(
    log: MinimalRunLog,
    status: str,
    file_path: str | None = None,
    latest_impression_count: int | None = None,
) -> MinimalRunLog:
    """X API実績値取得（scripts/x_post_analytics.py）の結果をminimal_run_logへ反映する。
    mainline_statusには一切触れない（analytics取得の成否をmainline失敗へ波及させない）。
    """
    log.analytics_status = status
    log.analytics_file_path = file_path
    log.latest_impression_count = latest_impression_count
    return log


def minimal_run_log_to_dict(log: MinimalRunLog) -> dict[str, Any]:
    return asdict(log)


def save_minimal_run_log(
    log: MinimalRunLog, repo_root: Path | str, date_str: str | None = None
) -> Path:
    """minimal_run_logをops/reports/minimal_run_log_<date>_<run_id>.jsonとして保存する。
    structure/hook/divergence等の研究レポート（shadow_mode_run_*.json等）とはファイルを
    分け、責務の分離をファイルシステム上でも可視化する。
    """
    repo_root = Path(repo_root)
    date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = repo_root / "ops" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"minimal_run_log_{date_str}_{log.run_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(minimal_run_log_to_dict(log), f, ensure_ascii=False, indent=2)
    return out_path
