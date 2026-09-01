"""topic_group_state（テーマのライフサイクル状態管理）のpure function層。

mainlineの候補選定における3症状——
  (1) posted-theme再流入（同一/近縁テーマがsource違いで繰り返しmainlineへ現れる）
  (2) 不発テーマの延命（Gate A不合格やclosed_incompleteを繰り返すテーマが際限なく
      再試行され続ける）
  (3) フィードバック不接続（実投稿後の実績値=post_analyticsが次の候補選定に
      一切反映されない）
——を、「テーマにライフサイクル状態がない」という共通原因から解消する状態ストア。

theme_signature/topic_groupの生成はtopic_dedupe.build_theme_signature()/
build_topic_group()を正とする（本モジュールはtopic_group単位の状態のみを扱い、
signature生成ロジック自体は持たない）。posted-theme block判定は
posted_theme_registry.check_posted_theme_guard()を正とし、本モジュールは
その判定結果をtopic_groupの状態遷移へ反映するだけ。

外部AI呼び出しは一切行わない。production scoring/Gate A/thresholds/
shipping decisionには一切触れない。

設計文書: ops/reports/topic_group_lifecycle_design_2026-08-31.md
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from posted_theme_registry import TOPIC_GROUP_COOLDOWN_DAYS

TOPIC_STATUSES = ("active", "cooldown", "exhausted", "published", "retired")
PERFORMANCE_BANDS = ("unknown", "low", "medium", "high")

# 初期値（保守的、設計文書に明記のうえコード上で定数化）。
TOPIC_GROUP_INITIAL_RETRY_BUDGET = 3
# post_analytics.public_metrics.impression_countに基づく暫定バンド境界。
# 実運用データが蓄積されたら見直す。
PERFORMANCE_BAND_THRESHOLDS = {"low": 50, "medium": 200}


class TopicGroupStateError(ValueError):
    pass


@dataclass
class TopicGroupState:
    """1 topic_group分のライフサイクル状態。research asset。shipping decisionには
    一切接続しない——mainlineの候補生成フィルタ（recommendation-only的な事前絞り込み）
    の入力としてのみ使う。
    """

    topic_group_id: str
    theme_signature: str
    topic_status: str = "active"
    topic_last_published_at: str | None = None
    topic_performance_band: str = "unknown"
    topic_retry_budget: int = TOPIC_GROUP_INITIAL_RETRY_BUDGET
    topic_cooldown_until: str | None = None
    topic_retired_from_mainline: bool = False
    route_to_research_only: bool = False
    source_diversity_tag: str | None = None
    created_at: str = ""
    updated_at: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_or_create_topic_group(
    store: dict[str, TopicGroupState],
    topic_group_id: str,
    theme_signature: str,
    source_diversity_tag: str | None = None,
) -> TopicGroupState:
    """storeにtopic_group_idが無ければ新規作成し、あれば既存のものを返す
    （既存のtheme_signature/statusを上書きしない）。
    """
    if topic_group_id in store:
        return store[topic_group_id]
    now = _now_iso()
    state = TopicGroupState(
        topic_group_id=topic_group_id,
        theme_signature=theme_signature,
        source_diversity_tag=source_diversity_tag,
        created_at=now,
        updated_at=now,
    )
    store[topic_group_id] = state
    return state


def record_mainline_attempt(state: TopicGroupState, succeeded: bool) -> TopicGroupState:
    """mainline試行結果をtopic_group状態へ反映する。

    succeeded=False（posted-theme block／Gate A生存不足／closed_incomplete等で
    human選定まで到達しなかった）ならtopic_retry_budgetを1消費する。0に達したら
    topic_status="exhausted"、route_to_research_only=Trueとし、以後の候補生成
    フィルタで自動的に除外されるようにする（「不発テーマの延命」への対処）。

    succeeded=True（human選定＝mainline_status=completedまで到達）なら消費しない。
    """
    if not succeeded:
        state.topic_retry_budget = max(0, state.topic_retry_budget - 1)
        if state.topic_retry_budget == 0 and state.topic_status == "active":
            state.topic_status = "exhausted"
            state.route_to_research_only = True
    state.updated_at = _now_iso()
    return state


def record_publication(
    state: TopicGroupState, published_at: str, cooldown_days: int = TOPIC_GROUP_COOLDOWN_DAYS
) -> TopicGroupState:
    """実投稿確定時にtopic_group状態を更新する。以後このtopic_groupはmainlineの
    候補生成フィルタから外れ、research専用扱いになる——posted_theme_registryの
    exact_source_match/high_theme_similarity判定と目的を揃える（「投稿済みテーマは
    もうmainlineの主対象ではない」というライフサイクル上の帰結を明示的に状態化する）。
    """
    state.topic_last_published_at = published_at
    state.topic_status = "published"
    state.topic_retired_from_mainline = True
    state.route_to_research_only = True
    try:
        published_date = datetime.strptime(published_at, "%Y-%m-%d").date()
        state.topic_cooldown_until = (published_date + timedelta(days=cooldown_days)).strftime("%Y-%m-%d")
    except ValueError:
        pass
    state.updated_at = _now_iso()
    return state


def update_performance_band(state: TopicGroupState, impression_count: int | None) -> TopicGroupState:
    """post_analyticsのimpression_countから、topic_performance_bandを更新する
    （階層的な暫定閾値。post_analyticsのfetch_status=failed_non_blocking時など
    impression_countがNoneの場合は"unknown"のままにし、0扱いで誤ってlowにしない）。
    """
    if impression_count is None:
        band = "unknown"
    elif impression_count < PERFORMANCE_BAND_THRESHOLDS["low"]:
        band = "low"
    elif impression_count < PERFORMANCE_BAND_THRESHOLDS["medium"]:
        band = "medium"
    else:
        band = "high"
    state.topic_performance_band = band
    state.updated_at = _now_iso()
    return state


def is_cooldown_active(state: TopicGroupState, today: date | None = None) -> bool:
    if not state.topic_cooldown_until:
        return False
    today = today or date.today()
    try:
        until = datetime.strptime(state.topic_cooldown_until, "%Y-%m-%d").date()
    except ValueError:
        return False
    return today <= until


def passes_mainline_candidate_filter(
    state: TopicGroupState,
    posted_theme_blocked: bool,
    exploration_quota_remaining: bool,
    today: date | None = None,
) -> dict[str, Any]:
    """mainline候補生成直前フィルタ。

    **注記（出典タスクの原文との整合について）**: 依頼文は本フィルタを「4条件」と
    呼びつつ、実際には独立した5つの条件節（topic_status=active／posted-theme
    exclusion／retry_budget>0／cooldown外／exploration quota内）を列挙していた。
    数え違いを黙って解消せず、ここでは列挙された5条件すべてをそのまま実装し、
    この食い違いをドキュメント上明記する（最終報告の「未解決事項」にも記載）。

    5条件すべてを満たす場合のみ`passes=True`（候補プールに残す）:
      1. topic_status == "active"
      2. posted-theme exclusionでblockされていない
         （posted_theme_registry.check_posted_theme_guard()の判定結果を
          呼び出し側から渡してもらう。本関数自体はguardを再実行しない）
      3. topic_retry_budget > 0
      4. cooldown外
      5. exploration quota内（呼び出し側が計算したbool値をそのまま受け取る）
    """
    reasons: list[str] = []

    status_ok = state.topic_status == "active"
    if not status_ok:
        reasons.append(f"topic_status={state.topic_status}（activeでない）")

    posted_theme_ok = not posted_theme_blocked
    if not posted_theme_ok:
        reasons.append("posted-theme exclusionでblock対象")

    retry_budget_ok = state.topic_retry_budget > 0
    if not retry_budget_ok:
        reasons.append(f"topic_retry_budget={state.topic_retry_budget}（0以下）")

    cooldown_ok = not is_cooldown_active(state, today=today)
    if not cooldown_ok:
        reasons.append(f"cooldown中（topic_cooldown_until={state.topic_cooldown_until}）")

    quota_ok = exploration_quota_remaining
    if not quota_ok:
        reasons.append("exploration quota超過")

    passes = status_ok and posted_theme_ok and retry_budget_ok and cooldown_ok and quota_ok
    return {
        "passes": passes,
        "topic_status_ok": status_ok,
        "posted_theme_ok": posted_theme_ok,
        "retry_budget_ok": retry_budget_ok,
        "cooldown_ok": cooldown_ok,
        "exploration_quota_ok": quota_ok,
        "reasons": reasons,
    }


def topic_group_state_to_dict(state: TopicGroupState) -> dict[str, Any]:
    return asdict(state)


def store_to_dict(store: dict[str, TopicGroupState]) -> dict[str, Any]:
    return {"topic_groups": {k: topic_group_state_to_dict(v) for k, v in store.items()}}


def save_topic_group_state_store(
    store: dict[str, TopicGroupState], repo_root: Path | str, label: str | None = None
) -> Path:
    repo_root = Path(repo_root)
    label = label or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = repo_root / "ops" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"topic_group_state_{label}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(store_to_dict(store), f, ensure_ascii=False, indent=2)
    return out_path


def load_topic_group_state_store(path: str | Path) -> dict[str, TopicGroupState]:
    """既存のtopic_group_state_*.jsonを読み込む。ファイルが無ければ空のstoreを返す
    （初回実行時にエラーにしないための安全側フォールバック）。
    """
    path = Path(path)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: TopicGroupState(**v) for k, v in data.get("topic_groups", {}).items()}
