"""X API v2 呼び出し。requests のみを使用する（新規の重量級依存を避ける）。

フィールド名は X API v2 のドキュメントに準拠しているが、API仕様は変更されうるため、
実装前に最新のドキュメントで `non_public_metrics` / `organic_metrics` の
フィールド名（特に engagements 系）を確認すること。
"""

from __future__ import annotations

import requests

_API_BASE = "https://api.x.com/2"
_TIMEOUT_SECONDS = 15


class XApiError(Exception):
    """X API呼び出しに関する汎用エラー（レート制限・5xx・投稿not found等）。"""


class XApiAuthError(Exception):
    """認証情報が不足している、または無効な場合のエラー。"""


def fetch_tweet_metrics(
    tweet_id: str,
    *,
    bearer_token: str | None,
    user_access_token: str | None,
) -> tuple[dict, bool]:
    """指定 tweet_id のメトリクスを取得する。

    戻り値: (メトリクス辞書, non_public/organicを取得できたか)

    - user_access_token があれば public_metrics + non_public_metrics + organic_metrics を
      1回のリクエストで取得する（OAuth 2.0 User Context認証）
    - user_access_token がなく bearer_token のみなら public_metrics のみ取得する
      （App-only認証。non-publicは原理的に取得不可）
    - どちらも無ければ XApiAuthError
    """
    if user_access_token:
        token = user_access_token
        fields = "public_metrics,non_public_metrics,organic_metrics"
        want_non_public = True
    elif bearer_token:
        token = bearer_token
        fields = "public_metrics"
        want_non_public = False
    else:
        raise XApiAuthError("X_BEARER_TOKEN も X_USER_ACCESS_TOKEN も設定されていません")

    url = f"{_API_BASE}/tweets/{tweet_id}"
    params = {"tweet.fields": fields}
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

    metrics: dict = {}
    metrics.update(data.get("public_metrics", {}))
    if want_non_public:
        metrics.update(data.get("non_public_metrics", {}))
        metrics.update(data.get("organic_metrics", {}))

    return metrics, want_non_public
