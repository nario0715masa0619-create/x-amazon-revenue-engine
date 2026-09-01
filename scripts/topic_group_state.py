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

# ============================================================================
# 2026-09-01追加（GOV-20260901-POST-OUTCOME-DESIGN-01）: post_outcome.classify_post_outcome()
# の結果（win/neutral/loss/insufficient_data）をtopic_groupのライフサイクル判断へ
# 配線するための暫定閾値。すべて暫定値であり、最終決定は人間が行う。
# 変更する場合はこのブロックの該当定数のみを書き換えればよい（他の計算式は
# 自動的に追随する）。
# ============================================================================

# win実績が一度もないtopic_groupがmainline試行に失敗した場合、通常の1に代えて
# この倍率分だけretry_budgetを消費する（record_mainline_attempt()参照）。
# 暫定値: 2。根拠: 「不発テーマの延命」をより早く止めるため、実績が未証明の
# テーマの消費ペースを通常の2倍にするという設計判断。この倍率の妥当性は
# 実運用データが蓄積されてから人間が再検証する必要がある。
NEVER_WON_RETRY_BUDGET_PENALTY_MULTIPLIER = 2

# 直近のpost_outcomeが"win"だった場合、cooldown期間を
# TOPIC_GROUP_COOLDOWN_DAYS // WIN_COOLDOWN_DIVISOR に短縮する（record_publication()参照）。
# 暫定値: 3（21日 -> 7日）。根拠: winしたテーマは再露出のリスクが相対的に低いと
# 仮定した暫定判断。実データによる検証はまだ行っていない。人間の確認が必要。
WIN_COOLDOWN_DIVISOR = 3

# win実績が一度もないまま、mainline_run_countがこの値を超えたtopic_groupは
# 候補プールから除外する（passes_mainline_candidate_filter()参照）。この判定は
# topic_group単体のmainline_run_countのみを見る（同一テーマがtheme_signature分裂
# （前タスクGOV-20260901-TOPIC-GROUP-SPLIT-DETECTION-01で検出可能になった問題）で
# 複数topic_group_idに割れている場合、この関数は分裂を横断した合算値までは見ない
# ——分裂の合算判定はweekly_learning_reviewのdetect_theme_signature_splits()側の
# 責務のままとし、本関数は意図的にシンプルなper-topic_group判定に留める）。
# 暫定値: 4。根拠: 実データで確認済みのATH-PRO5MK2テーマ系列は、theme_signature分裂
# により2つのtopic_group_id（mainline_run_count=5および2）に分かれており、win実績は
# 一度もない（GOV-20260901-INVESTIGATION-01調査より）。この暫定値4は、露出の多い側
# （5）を確実に検出できる水準として設定したものであり、4が適切な運用値かは
# 人間の判断が必要（特に、分裂した2つのtopic_group_idを横断した合算値（5+2=7）を
# 見るべきという設計変更も、次のfollow-upとして人間が検討する余地がある）。
NEVER_WON_MAX_RUN_COUNT_WITHOUT_WIN = 4


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
    # 2026-09-01追加（GOV-20260901-TOPIC-GROUP-SPLIT-DETECTION-01）:
    # このtopic_group_idがmainline run由来で観測された回数（実質露出回数）。
    # 既存の保存済みJSONにこのキーが無くても、dataclassのdefaultによりロード時エラーにならない
    # （追加のみで既存データを破壊しない）。record_topic_group_run_observed()でのみ増分する。
    mainline_run_count: int = 0
    # 2026-09-01追加（GOV-20260901-POST-OUTCOME-DESIGN-01）: post_outcome.classify_post_outcome()
    # の結果を反映するフィールド。record_post_outcome()でのみ更新する。has_ever_wonは
    # 一度Trueになったら以後Falseへ戻らない（「過去に一度でも勝ったか」の累積フラグ）。
    # 既存の保存済みJSONにこれらのキーが無くてもdataclassのdefaultでロード可能（追加のみ）。
    has_ever_won: bool = False
    latest_post_outcome: str | None = None


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


def record_topic_group_run_observed(state: TopicGroupState) -> TopicGroupState:
    """このtopic_group_idにmainline runが1件対応付けられたことを記録する
    （theme_signature分裂検出のための実質露出回数カウンタ。状態遷移・budget消費とは独立）。
    """
    state.mainline_run_count += 1
    state.updated_at = _now_iso()
    return state


def record_post_outcome(state: TopicGroupState, outcome: str) -> TopicGroupState:
    """post_outcome.classify_post_outcome()の判定結果（"win"/"neutral"/"loss"/
    "insufficient_data"の文字列）をtopic_group状態へ反映する。

    本モジュールはpost_outcome.pyをimportしない（post_outcome.pyがtopic_group_state.py
    のPERFORMANCE_BAND_THRESHOLDSをimportしているため、循環importを避けるために
    outcome文字列のみを受け取る）。has_ever_wonは一度Trueになったら以後Falseへ
    戻さない（「過去に一度でも勝ったことがあるか」という累積事実のフラグのため）。
    """
    state.latest_post_outcome = outcome
    if outcome == "win":
        state.has_ever_won = True
    state.updated_at = _now_iso()
    return state


# 分裂検出（near-duplicate側）のしきい値。posted_theme_registry.HIGH_SIMILARITY_THRESHOLD
# （0.6）と揃え、検出の厳しさに関する語彙をリポジトリ内で一貫させる。
THEME_SIGNATURE_NEAR_DUPLICATE_THRESHOLD = 0.6


def _theme_signature_tag_set(signature: str) -> set[str]:
    return set(tag for tag in signature.split("__") if tag)


def _theme_signature_jaccard(sig_a: str, sig_b: str) -> float:
    tags_a, tags_b = _theme_signature_tag_set(sig_a), _theme_signature_tag_set(sig_b)
    if not tags_a or not tags_b:
        return 0.0
    return len(tags_a & tags_b) / len(tags_a | tags_b)


def _split_entry(signature_label: str, states: list[TopicGroupState], split_type: str, similarity: float | None = None) -> dict[str, Any]:
    groups = []
    combined_run_count = 0
    for s in sorted(states, key=lambda x: x.topic_group_id):
        combined_run_count += s.mainline_run_count
        groups.append(
            {
                "topic_group_id": s.topic_group_id,
                "theme_signature": s.theme_signature,
                "topic_status": s.topic_status,
                "topic_performance_band": s.topic_performance_band,
                "topic_last_published_at": s.topic_last_published_at,
                "mainline_run_count": s.mainline_run_count,
            }
        )
    return {
        "theme_signature": signature_label,
        "split_type": split_type,
        "similarity": similarity,
        "topic_group_ids": [g["topic_group_id"] for g in groups],
        "topic_groups": groups,
        "combined_mainline_run_count": combined_run_count,
    }


def detect_theme_signature_splits(
    store: dict[str, TopicGroupState],
    near_duplicate_threshold: float = THEME_SIGNATURE_NEAR_DUPLICATE_THRESHOLD,
) -> list[dict[str, Any]]:
    """同一テーマが複数のtopic_group_idに分裂しているケースをread-onlyで検出する。

    storeの内容は一切変更しない（週次集計から呼ばれる想定の純粋な分析関数）。
    build_topic_group()のグルーピングロジック自体はここでは一切変更・再実装しない——
    既にstoreへ保存済みのtheme_signature/topic_group_idの組をそのまま集計するのみ。

    **依頼文の原文との整合について**: 依頼文は本チェックを「同一theme_signatureが複数の
    topic_group_idに分裂するケース」と表現していたが、実際にbackfill済みデータで観測された
    唯一の実分裂ケース（ATH-PRO5MK2×ジム用骨伝導）を検証したところ、2つのtopic_group_idは
    theme_signatureも互いに異なっていた（一方が他方に"__split-settled"タグ1つ分だけ
    長い、というほぼ同一の値）。theme_signatureはtopic_groupより細かい5次元タグを
    含むため、topic_groupが割れる原因（比較軸タグの検出ゆれ）はtheme_signature自体も
    ほぼ同時に割ってしまう——「theme_signatureが同一なのにtopic_groupだけ割れる」という
    狭い意味での検出だけでは、この既知の実ケースを取りこぼす。
    そのため、文字どおりの厳密一致（exact_signature_match）に加えて、signatureを
    "__"区切りのタグ集合として比較するJaccard類似度がしきい値（デフォルト0.6、
    posted_theme_registry.HIGH_SIMILARITY_THRESHOLDと同水準）以上のペアも
    near_duplicate_signatureとして検出する。数え違いを黙って解消せず、この食い違いは
    ここと最終報告の両方に明記する。
    """
    by_signature: dict[str, list[TopicGroupState]] = {}
    for state in store.values():
        by_signature.setdefault(state.theme_signature, []).append(state)

    results: list[dict[str, Any]] = []
    exact_signatures_used: set[str] = set()
    for signature, states in by_signature.items():
        if len(states) < 2:
            continue
        results.append(_split_entry(signature, states, split_type="exact_signature_match"))
        exact_signatures_used.add(signature)

    # near-duplicate側: 異なるtopic_group_idに属する、まだexact matchで報告済みでない
    # signature同士をペアごとに比較する。
    distinct_signature_to_states: dict[str, list[TopicGroupState]] = {
        sig: states for sig, states in by_signature.items() if sig not in exact_signatures_used
    }
    signatures = sorted(distinct_signature_to_states.keys())
    seen_pairs: set[frozenset[str]] = set()
    for i in range(len(signatures)):
        for j in range(i + 1, len(signatures)):
            sig_a, sig_b = signatures[i], signatures[j]
            similarity = _theme_signature_jaccard(sig_a, sig_b)
            if similarity < near_duplicate_threshold:
                continue
            pair_key = frozenset({sig_a, sig_b})
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            combined_states = distinct_signature_to_states[sig_a] + distinct_signature_to_states[sig_b]
            label = f"{sig_a} ~ {sig_b}"
            results.append(
                _split_entry(label, combined_states, split_type="near_duplicate_signature", similarity=round(similarity, 2))
            )

    return sorted(results, key=lambda r: (r["split_type"], r["theme_signature"]))


def record_mainline_attempt(state: TopicGroupState, succeeded: bool) -> TopicGroupState:
    """mainline試行結果をtopic_group状態へ反映する。

    succeeded=False（posted-theme block／Gate A生存不足／closed_incomplete等で
    human選定まで到達しなかった）ならtopic_retry_budgetを1消費する。0に達したら
    topic_status="exhausted"、route_to_research_only=Trueとし、以後の候補生成
    フィルタで自動的に除外されるようにする（「不発テーマの延命」への対処）。

    succeeded=True（human選定＝mainline_status=completedまで到達）なら消費しない。

    2026-09-01追加（GOV-20260901-POST-OUTCOME-DESIGN-01）: state.has_ever_won（過去に
    一度でも"win"判定を得たことがあるか、record_post_outcome()で更新）がFalseの場合、
    通常の1消費ではなくNEVER_WON_RETRY_BUDGET_PENALTY_MULTIPLIER倍を消費する
    （暫定ロジック、値の妥当性は人間の判断が必要。定数コメント参照）。
    """
    if not succeeded:
        penalty = 1 if state.has_ever_won else NEVER_WON_RETRY_BUDGET_PENALTY_MULTIPLIER
        state.topic_retry_budget = max(0, state.topic_retry_budget - penalty)
        if state.topic_retry_budget == 0 and state.topic_status == "active":
            state.topic_status = "exhausted"
            state.route_to_research_only = True
    state.updated_at = _now_iso()
    return state


def record_publication(
    state: TopicGroupState,
    published_at: str,
    cooldown_days: int = TOPIC_GROUP_COOLDOWN_DAYS,
    latest_outcome: str | None = None,
) -> TopicGroupState:
    """実投稿確定時にtopic_group状態を更新する。以後このtopic_groupはmainlineの
    候補生成フィルタから外れ、research専用扱いになる——posted_theme_registryの
    exact_source_match/high_theme_similarity判定と目的を揃える（「投稿済みテーマは
    もうmainlineの主対象ではない」というライフサイクル上の帰結を明示的に状態化する）。

    2026-09-01追加（GOV-20260901-POST-OUTCOME-DESIGN-01）: latest_outcome
    （post_outcome.classify_post_outcome()の結果。この*同じ*投稿の実績値はまだ
    取得できていない時点で呼ばれるため、通常は直前のサイクルのstate.latest_post_outcome
    を渡す想定）に応じてcooldown期間・statusを可変にする（暫定ロジック、値の妥当性は
    人間の判断が必要。WIN_COOLDOWN_DIVISOR等の定数コメント参照）:
      - "loss": 即座にtopic_status="retired"とし、topic_cooldown_untilは設定しない
        （cooldown経過による自動復帰の対象から外す＝実質的な卒業）
      - "win": cooldown期間をcooldown_days // WIN_COOLDOWN_DIVISORへ短縮する
      - "neutral"／"insufficient_data"／None（デフォルト、既存呼び出し互換）:
        既存どおりcooldown_daysをそのまま使う
    """
    state.topic_last_published_at = published_at
    state.topic_retired_from_mainline = True
    state.route_to_research_only = True

    if latest_outcome == "loss":
        state.topic_status = "retired"
        state.topic_cooldown_until = None
        state.updated_at = _now_iso()
        return state

    state.topic_status = "published"
    effective_cooldown_days = cooldown_days
    if latest_outcome == "win":
        effective_cooldown_days = max(1, cooldown_days // WIN_COOLDOWN_DIVISOR)
    try:
        published_date = datetime.strptime(published_at, "%Y-%m-%d").date()
        state.topic_cooldown_until = (published_date + timedelta(days=effective_cooldown_days)).strftime("%Y-%m-%d")
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

    2026-09-01追加（GOV-20260901-POST-OUTCOME-DESIGN-01）: 上記5条件に加え、
    「win実績が一度もないまま、mainline_run_countがNEVER_WON_MAX_RUN_COUNT_WITHOUT_WIN
    を超えたtopic_groupを除外する」第6条件を追加した（暫定値、人間の判断が必要。
    定数コメント参照）。

    6条件すべてを満たす場合のみ`passes=True`（候補プールに残す）:
      1. topic_status == "active"
      2. posted-theme exclusionでblockされていない
         （posted_theme_registry.check_posted_theme_guard()の判定結果を
          呼び出し側から渡してもらう。本関数自体はguardを再実行しない）
      3. topic_retry_budget > 0
      4. cooldown外
      5. exploration quota内（呼び出し側が計算したbool値をそのまま受け取る）
      6. win実績が一度もなく、かつmainline_run_countが
         NEVER_WON_MAX_RUN_COUNT_WITHOUT_WINを超えている、という状態ではない
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

    never_won_exhausted_ok = not (
        not state.has_ever_won and state.mainline_run_count > NEVER_WON_MAX_RUN_COUNT_WITHOUT_WIN
    )
    if not never_won_exhausted_ok:
        reasons.append(
            f"win実績なしのままmainline_run_count={state.mainline_run_count}が"
            f"NEVER_WON_MAX_RUN_COUNT_WITHOUT_WIN({NEVER_WON_MAX_RUN_COUNT_WITHOUT_WIN})を超過"
        )

    passes = (
        status_ok
        and posted_theme_ok
        and retry_budget_ok
        and cooldown_ok
        and quota_ok
        and never_won_exhausted_ok
    )
    return {
        "passes": passes,
        "topic_status_ok": status_ok,
        "posted_theme_ok": posted_theme_ok,
        "retry_budget_ok": retry_budget_ok,
        "cooldown_ok": cooldown_ok,
        "exploration_quota_ok": quota_ok,
        "never_won_exhausted_ok": never_won_exhausted_ok,
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
