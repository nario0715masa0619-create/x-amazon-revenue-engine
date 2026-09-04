"""teacher輩出アカウントの監視状態（可変ストア）のpure function層。

「一度でもteacherを出したアカウントを深掘り収集の対象として監視し続けるかどうか」を
管理する。topic_group_state.pyの永続化パターン（IDをキーにした辞書、json.dump()で
毎回全体を書き換える）を踏襲するが、状態遷移の意味は作り直している——topic_groupの
cooldown/retireは「投稿というイベントを起点に消費される消費型リソース」の管理であるのに
対し、監視対象アカウントは「継続的に定期チェックする対象を維持するかどうか」という
購読（subscription）型の管理であり、性質が異なるため（設計文書2-3節）。

外部AI呼び出しは一切行わない。Gate A/thresholds/shipping decision、
_apply_engagement_gate()、topic_groupのライフサイクル管理ロジックには一切触れない。

設計文書: ops/reports/teacher_account_deepdive_design_2026-09-01.md（2-1節、2-3節）
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WATCH_STATUSES = ("active", "graduated", "excluded", "pending_review")

# 深掘りチェックで新規pre_teacher_candidateが0件だった連続回数がこの値に達したら
# graduated（休止）へ遷移する。暫定値: 10。根拠: 設計文書2-3節の提案値（N=10回、
# または30日相当）をそのまま採用した。この値の妥当性は実運用データが蓄積されてから
# 人間が再検証する必要がある（設計文書「未解決事項」3参照）。
GRADUATION_THRESHOLD_CONSECUTIVE_UNPRODUCTIVE_RUNS = 10


class WatchedAccountStateError(ValueError):
    pass


@dataclass
class WatchedAccountState:
    """1アカウント分の監視状態。research/collection asset。shipping decisionには
    一切接続しない——深掘り収集の対象アカウントを絞り込むためだけの入力として使う。
    """

    author_id: str
    watch_status: str = "active"
    teacher_count: int = 0
    first_registered_at: str = ""
    last_teacher_at: str | None = None
    last_deepdive_checked_at: str | None = None
    consecutive_unproductive_deepdive_runs: int = 0
    last_deepdive_since_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
    excluded_reason: str | None = None
    excluded_at: str | None = None
    pending_review_reason: str | None = None
    pending_review_detected_at: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def register_or_reactivate_watched_account(
    store: dict[str, WatchedAccountState],
    author_id: str,
    observed_at: str | None = None,
) -> WatchedAccountState:
    """author_idがteacher（pre_teacher_candidate）として観測されたことを反映する。

    新規登録・既存active観測・graduatedからの復帰の3ケースをすべてこの1つの入口関数で
    扱う（設計文書2-3節「新規登録と復帰の両方を扱う設計とする」に対応）:
      - 未登録のauthor_id: watch_status="active"で新規作成する。
      - 既存active: teacher_count/last_teacher_atのみ更新する。
      - 既存graduated: watch_status="active"へ復帰させ、
        consecutive_unproductive_deepdive_runsを0にリセットする
        （設計文書「日次キーワード収集で再度teacher観測時に自動復帰」）。
    いずれの場合もteacher_countを1加算する。

    2026-09-04追加（企業公式アカウント除外方針）: 既存watch_status=="excluded"
    （人間判断による恒久除外。exclude_watched_account()参照）または
    "pending_review"（企業アカウントの可能性で要人間確認、
    create_pending_review_watched_account()参照）の場合は、無条件には
    復帰・更新しない——状態を一切変更せずそのまま返す。呼び出し側
    （register_watched_accounts.py）で事前にスキップすることを推奨するが、
    防御的にここでも復帰を止める。
    """
    observed_at = observed_at or _now_iso()

    if author_id not in store:
        state = WatchedAccountState(
            author_id=author_id,
            watch_status="active",
            teacher_count=1,
            first_registered_at=observed_at,
            last_teacher_at=observed_at,
            created_at=observed_at,
            updated_at=observed_at,
        )
        store[author_id] = state
        return state

    state = store[author_id]
    if state.watch_status in ("excluded", "pending_review"):
        return state
    state.teacher_count += 1
    state.last_teacher_at = observed_at
    if state.watch_status == "graduated":
        state.watch_status = "active"
        state.consecutive_unproductive_deepdive_runs = 0
    state.updated_at = observed_at
    return state


def exclude_watched_account(
    state: WatchedAccountState,
    reason: str,
    excluded_at: str | None = None,
) -> WatchedAccountState:
    """人間判断による恒久除外を記録する（2026-09-04追加）。graduatedと異なり、深掘りの
    不発による自動遷移ではなく、人間が明示的に「監視対象として不適切」と判断した
    ケース専用（例: 企業公式アカウントの誤登録）。単純な削除ではなく除外理由・日時を
    残すことで、将来同じアカウントが再度teacherとして観測されても
    register_or_reactivate_watched_account()が無条件には復帰させないようにする。
    """
    excluded_at = excluded_at or _now_iso()
    state.watch_status = "excluded"
    state.excluded_reason = reason
    state.excluded_at = excluded_at
    state.updated_at = excluded_at
    return state


def create_pending_review_watched_account(
    store: dict[str, WatchedAccountState],
    author_id: str,
    reason: str,
    detected_at: str | None = None,
) -> WatchedAccountState:
    """企業アカウントらしいシグナルが検出された、未登録のauthor_idを
    watch_status="pending_review"で新規作成する（2026-09-04追加）。

    active_author_ids()の対象外のため深掘り収集は行われず、人間が確認するまで
    "active"へは昇格しない。author_idが既にstoreに存在する場合は
    WatchedAccountStateErrorを送出する（新規作成専用。既存アカウントの状態変更は
    exclude_watched_account()等、別の関数の責務とする）。
    """
    if author_id in store:
        raise WatchedAccountStateError(
            f"author_id={author_id!r} は既にstoreに存在するため、pending_reviewとして新規作成できません。"
        )
    detected_at = detected_at or _now_iso()
    state = WatchedAccountState(
        author_id=author_id,
        watch_status="pending_review",
        teacher_count=1,
        first_registered_at=detected_at,
        last_teacher_at=detected_at,
        created_at=detected_at,
        updated_at=detected_at,
        pending_review_reason=reason,
        pending_review_detected_at=detected_at,
    )
    store[author_id] = state
    return state


def record_deepdive_run_result(
    state: WatchedAccountState,
    found_new_pre_teacher_candidate: bool,
    since_id: str | None,
    checked_at: str | None = None,
    graduation_threshold: int = GRADUATION_THRESHOLD_CONSECUTIVE_UNPRODUCTIVE_RUNS,
) -> WatchedAccountState:
    """深掘り収集1回分の結果を監視状態へ反映する。

    found_new_pre_teacher_candidate=Trueなら不発カウンタを0へリセットする。Falseなら
    1加算し、graduation_thresholdに達した時点でwatch_status="graduated"へ遷移させる
    （以後、深掘り収集の対象から自動的に外れる＝API呼び出しコストを止める）。
    since_idは次回の増分チェック用カーソルとして、渡された場合のみ更新する
    （None＝そのAPI呼び出しで新規投稿が0件だった場合は据え置き、次回も同じ地点から
    再チェックできるようにする）。
    """
    checked_at = checked_at or _now_iso()
    state.last_deepdive_checked_at = checked_at
    if since_id:
        state.last_deepdive_since_id = since_id

    if found_new_pre_teacher_candidate:
        state.consecutive_unproductive_deepdive_runs = 0
    else:
        state.consecutive_unproductive_deepdive_runs += 1
        if (
            state.consecutive_unproductive_deepdive_runs >= graduation_threshold
            and state.watch_status == "active"
        ):
            state.watch_status = "graduated"

    state.updated_at = checked_at
    return state


def active_author_ids(store: dict[str, WatchedAccountState]) -> list[str]:
    """深掘り収集の対象とすべきauthor_id一覧（watch_status=="active"のみ）を返す。"""
    return [author_id for author_id, state in store.items() if state.watch_status == "active"]


def watched_account_state_to_dict(state: WatchedAccountState) -> dict[str, Any]:
    return asdict(state)


def store_to_dict(store: dict[str, WatchedAccountState]) -> dict[str, Any]:
    return {"watched_accounts": {k: watched_account_state_to_dict(v) for k, v in store.items()}}


def save_watched_account_state_store(store: dict[str, WatchedAccountState], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(store_to_dict(store), f, ensure_ascii=False, indent=2)
    return path


def load_watched_account_state_store(path: str | Path) -> dict[str, WatchedAccountState]:
    """既存のwatched_account_state.jsonを読み込む。ファイルが無ければ空のstoreを返す
    （初回実行時にエラーにしないための安全側フォールバック）。
    """
    path = Path(path)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: WatchedAccountState(**v) for k, v in data.get("watched_accounts", {}).items()}
