"""24hメトリクス回収のオーケストレーション（Sheets/X APIへの実アクセスはここでは行わず、
呼び出し側のクライアントに委譲する。ロジックを単体で検証しやすくするため）。
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from .config import Config
from .tweet_id import extract_tweet_id
from .x_api_client import XApiAuthError, XApiError, fetch_tweet_metrics

CHECK_WINDOW = "24h"

DATA_QUALITY_VALUES = {"ok", "partial", "auth_missing", "api_error", "url_unresolved", "manual"}


@dataclass
class CollectionResult:
    post_id: str
    data_quality: str
    notes: str
    metrics: dict[str, Any] = field(default_factory=dict)


def resolve_tweet_id(post: dict[str, Any]) -> str | None:
    """posts.tweet_id が埋まっていればそれを優先し、なければ posted_url から抽出する。"""
    existing = str(post.get("tweet_id") or "").strip()
    if existing:
        return existing
    return extract_tweet_id(post.get("posted_url"))


def collect_for_post(
    post: dict[str, Any],
    config: Config,
    now: dt.datetime | None = None,
) -> CollectionResult:
    """1件の投稿についてメトリクスを取得する（Sheetsへの書き込みは呼び出し側の責務）。"""
    del now  # このステップでは未使用（将来の時刻依存ロジック拡張に備えて引数だけ残す）
    post_id = post.get("post_id", "")

    tweet_id = resolve_tweet_id(post)
    if not tweet_id:
        return CollectionResult(
            post_id=post_id,
            data_quality="url_unresolved",
            notes="posted_url からtweet_idを抽出できず、posts.tweet_idも空でした",
        )

    try:
        metrics, got_non_public = fetch_tweet_metrics(
            tweet_id,
            bearer_token=config.x_bearer_token,
            user_access_token=config.x_user_access_token,
        )
    except XApiAuthError as exc:
        return CollectionResult(post_id=post_id, data_quality="auth_missing", notes=str(exc))
    except XApiError as exc:
        return CollectionResult(post_id=post_id, data_quality="api_error", notes=str(exc))

    if got_non_public:
        data_quality, notes = "ok", ""
    else:
        data_quality = "partial"
        notes = "non-public metrics未取得(User Context未設定のためpublic_metricsのみ)"

    return CollectionResult(post_id=post_id, data_quality=data_quality, notes=notes, metrics=metrics)


def _next_snapshot_id(existing_rows: list[dict[str, Any]], today: dt.date) -> str:
    """m24-YYYYMMDD-### 形式でsnapshot_idを発番する（当日分の既存行と重複しないように）。"""
    date_str = today.strftime("%Y%m%d")
    prefix = f"m24-{date_str}-"
    existing_seqs = []
    for row in existing_rows:
        snapshot_id = str(row.get("snapshot_id", ""))
        if snapshot_id.startswith(prefix) and snapshot_id[len(prefix):].isdigit():
            existing_seqs.append(int(snapshot_id[len(prefix):]))
    next_seq = (max(existing_seqs) + 1) if existing_seqs else 1
    return f"{prefix}{next_seq:03d}"


def _compute_profile_visit_rate(user_profile_clicks: Any, impression_count: Any) -> str:
    """profile_visit_rate = user_profile_clicks / impression_count。

    0除算・欠損時は空欄（"未取得"扱い）を返す。X管理画面UIの「プロフィール訪問数」との
    完全一致は保証されない近似値であることに注意（詳細はdocs参照）。
    """
    if user_profile_clicks in (None, "") or impression_count in (None, "", 0, "0"):
        return ""
    try:
        rate = float(user_profile_clicks) / float(impression_count)
    except (TypeError, ValueError, ZeroDivisionError):
        return ""
    return f"{rate:.4f}"


def build_metrics_row(
    result: CollectionResult,
    existing_rows: list[dict[str, Any]],
    existing_snapshot_id: str | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """CollectionResultをmetrics_24hシートの1行(dict)に整形する。

    既存行を更新する場合は existing_snapshot_id を渡し、同じsnapshot_idを維持する。
    新規行の場合は _next_snapshot_id で新しいIDを発番する。
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    metrics = result.metrics
    impression_count = metrics.get("impression_count", "")

    snapshot_id = existing_snapshot_id or _next_snapshot_id(existing_rows, now.date())

    return {
        "snapshot_id": snapshot_id,
        "post_id": result.post_id,
        "check_window": CHECK_WINDOW,
        "checked_at": now.isoformat(timespec="seconds"),
        "impression_count": impression_count,
        "like_count": metrics.get("like_count", ""),
        "reply_count": metrics.get("reply_count", ""),
        "bookmark_count": metrics.get("bookmark_count", ""),
        "user_profile_clicks": metrics.get("user_profile_clicks", ""),
        "url_link_clicks": metrics.get("url_link_clicks", ""),
        "engagements": metrics.get("engagements", ""),
        "profile_visit_rate": _compute_profile_visit_rate(
            metrics.get("user_profile_clicks"), impression_count
        ),
        "data_quality": result.data_quality,
        "notes": result.notes,
    }
