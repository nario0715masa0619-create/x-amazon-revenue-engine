"""posted_url から X の tweet_id を抽出するユーティリティ。

対応するURL形式:
- https://x.com/{user}/status/{tweet_id}
- https://twitter.com/{user}/status/{tweet_id}
- クエリパラメータ付き（例: ?s=20）も許容する
"""

from __future__ import annotations

import re

_TWEET_ID_PATTERN = re.compile(r"status/(\d+)")


def extract_tweet_id(posted_url: str | None) -> str | None:
    """posted_url から tweet_id を抽出する。抽出できなければ None を返す。"""
    if not posted_url:
        return None
    match = _TWEET_ID_PATTERN.search(posted_url)
    return match.group(1) if match else None
