"""x_post_analytics（mainline実投稿の実績値取得）のfetch/保存/接続層。

mainline runの実投稿結果（impression/engagement等）をX API v2から取得し、
minimal_run_log/enrichment_recordと接続できる形でops/reports/へ保存する。
「候補生成の良し悪し」だけでなく「実際に何インプレッション出たか」を追跡可能にする。

既存の`scripts/x_metrics_collector/`（Google Sheets連携版、Phase1暫定評価フェーズ中で
正式レーンではない）とは別に、learning modeのminimal_run_log/enrichment_record運用に
直結する軽量な経路として新設する。ただし`tweet_id.py`のURL解析ロジックと
`x_api_client.py`の認証エラー型は再利用し、重複実装を避ける。

crawlerではなくX API v2を使う。owned postに対するanalytics取得が前提。
post本文の編集・再投稿は一切行わない。production scoring/Gate A/thresholds/
shipping decisionには一切触れない。

設計文書: なし（実装のみ、必要に応じて別途設計メモを作成する）
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from x_metrics_collector.tweet_id import extract_tweet_id
from x_metrics_collector.x_api_client import XApiAuthError, XApiError

_API_BASE = "https://api.x.com/2"
_TIMEOUT_SECONDS = 15
_TWEET_FIELDS = "public_metrics,non_public_metrics,organic_metrics,promoted_metrics"

FETCH_STATUSES = ("completed", "partial", "failed_non_blocking")


class PostAnalyticsError(ValueError):
    pass


@dataclass
class PostAnalyticsRecord:
    """1投稿分の実績値レコード。research/enrichment側の任意接続情報であり、
    mainline_status等の本線判定には一切関与しない。"""

    run_id: str
    post_url: str
    post_id: str | None
    fetched_at: str
    analytics_source: str
    public_metrics: dict[str, Any] | None = None
    non_public_metrics: dict[str, Any] | None = None
    organic_metrics: dict[str, Any] | None = None
    promoted_metrics: dict[str, Any] | None = None
    fetch_status: str = "failed_non_blocking"
    fetch_error: str | None = None
    notes: str | None = None


def normalize_post_id(post_url: str | None) -> str | None:
    """post_urlからpost_id（tweet_id）を正規化抽出する。クエリパラメータ（?s=20等）は無視する。
    x_metrics_collector.tweet_id.extract_tweet_id()をそのまま再利用する。
    """
    return extract_tweet_id(post_url)


def _load_x_api_tokens() -> tuple[str | None, str | None]:
    """X_BEARER_TOKEN/X_USER_ACCESS_TOKENを環境変数（.env）から読み込む。
    Google Sheets関連の設定（x_metrics_collector.config.load_config）には依存しない
    ——このモジュールはSheets連携なしで単独動作できるようにするため。
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    return os.environ.get("X_BEARER_TOKEN") or None, os.environ.get("X_USER_ACCESS_TOKEN") or None


def fetch_tweet_metrics_by_category(
    tweet_id: str, *, bearer_token: str | None, user_access_token: str | None
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, str]:
    """指定tweet_idのメトリクスをカテゴリ別（public/non_public/organic/promoted）に分けて取得する。

    戻り値: (public_metrics, non_public_metrics, organic_metrics, promoted_metrics, analytics_source)
    non_public/organic/promotedは、user_access_tokenが無い・レスポンスに含まれない場合はNoneのまま
    （graceful degradation。public_metricsだけ返ってきた場合は例外にしない）。
    """
    if user_access_token:
        token = user_access_token
        analytics_source = "x_api_v2_tweets_lookup_user_context"
    elif bearer_token:
        token = bearer_token
        analytics_source = "x_api_v2_tweets_lookup_app_only"
    else:
        raise XApiAuthError("X_BEARER_TOKEN も X_USER_ACCESS_TOKEN も設定されていません")

    url = f"{_API_BASE}/tweets/{tweet_id}"
    params = {"tweet.fields": _TWEET_FIELDS}
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise XApiError(f"X APIへの接続に失敗しました: {exc}") from exc

    if response.status_code == 401:
        raise XApiAuthError("X APIの認証に失敗しました（トークン失効の可能性があります）")
    if response.status_code == 404:
        raise XApiError("指定の投稿が見つかりません（削除・非公開の可能性があります）")
    if response.status_code == 429:
        raise XApiError("X APIのレート制限に達しました")
    if not response.ok:
        raise XApiError(f"X APIエラー: HTTP {response.status_code} {response.text[:200]}")

    payload = response.json()
    data = payload.get("data", {})

    public_metrics = data.get("public_metrics") or {}
    non_public_metrics = data.get("non_public_metrics") or None
    organic_metrics = data.get("organic_metrics") or None
    promoted_metrics = data.get("promoted_metrics") or None

    return public_metrics, non_public_metrics, organic_metrics, promoted_metrics, analytics_source


def fetch_post_analytics(
    run_id: str,
    post_url: str,
    bearer_token: str | None = None,
    user_access_token: str | None = None,
) -> PostAnalyticsRecord:
    """post_urlからpost_idを抽出し、X APIから実績値を取得してPostAnalyticsRecordを組み立てる。
    **例外を送出しない**——認証不足・API error・URL解析失敗のいずれも
    fetch_status="failed_non_blocking"のレコードとして返し、呼び出し元のmainline処理には
    一切伝播させない（既存のrun_async_enrichment_experiment()と同じnon-blocking原則）。

    bearer_token/user_access_tokenを渡さない場合は.envから自動読み込みする。
    """
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    post_id = normalize_post_id(post_url)
    if not post_id:
        return PostAnalyticsRecord(
            run_id=run_id, post_url=post_url, post_id=None, fetched_at=fetched_at,
            analytics_source="none", fetch_status="failed_non_blocking",
            fetch_error="post_urlからpost_idを抽出できませんでした",
            notes="URL形式を確認してください（https://x.com/{user}/status/{tweet_id} 形式を想定）",
        )

    if bearer_token is None and user_access_token is None:
        bearer_token, user_access_token = _load_x_api_tokens()

    try:
        public_metrics, non_public_metrics, organic_metrics, promoted_metrics, analytics_source = (
            fetch_tweet_metrics_by_category(
                post_id, bearer_token=bearer_token, user_access_token=user_access_token
            )
        )
    except XApiAuthError as e:
        return PostAnalyticsRecord(
            run_id=run_id, post_url=post_url, post_id=post_id, fetched_at=fetched_at,
            analytics_source="none", fetch_status="failed_non_blocking", fetch_error=str(e),
            notes="X_BEARER_TOKEN/X_USER_ACCESS_TOKENの設定を確認してください",
        )
    except XApiError as e:
        return PostAnalyticsRecord(
            run_id=run_id, post_url=post_url, post_id=post_id, fetched_at=fetched_at,
            analytics_source="x_api_v2_tweets_lookup", fetch_status="failed_non_blocking", fetch_error=str(e),
        )

    has_non_public = bool(non_public_metrics or organic_metrics)
    fetch_status = "completed" if has_non_public else "partial"
    notes = None if has_non_public else "non_public_metrics/organic_metricsはuser context（X_USER_ACCESS_TOKEN）が必要。public_metricsのみ取得済み"

    return PostAnalyticsRecord(
        run_id=run_id, post_url=post_url, post_id=post_id, fetched_at=fetched_at,
        analytics_source=analytics_source,
        public_metrics=public_metrics, non_public_metrics=non_public_metrics,
        organic_metrics=organic_metrics, promoted_metrics=promoted_metrics,
        fetch_status=fetch_status, fetch_error=None, notes=notes,
    )


def post_analytics_to_dict(record: PostAnalyticsRecord) -> dict[str, Any]:
    return asdict(record)


def save_post_analytics(record: PostAnalyticsRecord, repo_root: Path | str, date_str: str | None = None) -> Path:
    """post_analyticsをops/reports/post_analytics_<date>_<run_id>.jsonとして保存する。"""
    repo_root = Path(repo_root)
    date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = repo_root / "ops" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"post_analytics_{date_str}_{record.run_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(post_analytics_to_dict(record), f, ensure_ascii=False, indent=2)
    return out_path


def find_pending_analytics_targets(reports_dir: str | Path) -> list[dict[str, str]]:
    """ops/reports/配下のminimal_run_log_*.jsonを走査し、published_at/post_urlを持つが
    まだpost_analyticsが未取得（analytics_status未設定 or not_fetched）のrunを列挙する。
    [{"run_id":..., "post_url":...}, ...] の形で返す（余力があれば一括取得に使える入口）。
    """
    import glob

    reports_dir = Path(reports_dir)
    targets = []
    for path in sorted(glob.glob(str(reports_dir / "minimal_run_log_*.json"))):
        log = json.loads(Path(path).read_text(encoding="utf-8"))
        if not (log.get("published_at") and log.get("post_url")):
            continue
        if log.get("analytics_status") in ("completed", "partial"):
            continue
        targets.append({"run_id": log.get("run_id", ""), "post_url": log.get("post_url", "")})
    return targets
