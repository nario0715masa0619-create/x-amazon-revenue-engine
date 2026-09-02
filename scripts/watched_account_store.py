"""teacher輩出アカウントの登録イベントログ（追記専用、author_idベース重複排除）のpure function層。

scripts/cumulative_post_store.py のpost_idベース重複排除パターンをauthor_id版として
複製実装したもの（設計文書のとおり、既存関数を書き換えるのではなく同じ設計パターンの
別モジュールとして持つ）。1つの`author_id`が初めて`pre_teacher_candidate`として観測された
時のみ1行追記し、2回目以降の観測では追記しない（post_id dedupと同じ挙動）。

**投稿本文（text）は一切扱わない**——本モジュールが保存するのは`author_id`・
`first_seen_as_teacher_post_id`（post_id）・`first_seen_as_teacher_query_source`・
`registered_at`のみであり、text/text_hash相当のフィールドすら持たない
（cumulative_post_store.pyより厳格。理由: ops/reports/teacher_account_deepdive_design_2026-09-01.md
2-1節）。

外部AI呼び出しは一切行わない。Gate A/thresholds/shipping decision、
_apply_engagement_gate()、topic_groupのライフサイクル管理ロジックには一切触れない。

設計文書: ops/reports/teacher_account_deepdive_design_2026-09-01.md（2-1節）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PERSISTED_FIELDS = (
    "author_id",
    "first_seen_as_teacher_post_id",
    "first_seen_as_teacher_query_source",
    "registered_at",
)


def load_existing_watched_author_ids(path: str | Path) -> set[str]:
    """登録イベントログから既存のauthor_id集合を読み込む。ファイルが無ければ空集合を返す
    （初回実行時にエラーにしないための安全側フォールバック）。
    """
    path = Path(path)
    if not path.exists():
        return set()
    ids: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            author_id = record.get("author_id")
            if author_id:
                ids.add(author_id)
    return ids


def append_new_watched_accounts(
    path: str | Path,
    candidates: list[dict[str, Any]],
    registered_at: str,
) -> dict[str, Any]:
    """candidatesのうち、登録イベントログに未登録のauthor_idのみをJSONLへ追記する。

    candidatesの各要素は{"author_id", "first_seen_as_teacher_post_id",
    "first_seen_as_teacher_query_source"}を持つ想定。既に登録済みのauthor_id、および
    同一バッチ内での重複author_idはスキップする（どちらもskipped_duplicate_countへ計上）。
    author_id自体が無いレコードは無視する。追記対象が0件の場合はファイルへの書き込みを
    行わない。

    戻り値: {"appended_count", "skipped_duplicate_count", "total_before", "total_after"}
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = load_existing_watched_author_ids(path)
    total_before = len(existing_ids)

    appended_count = 0
    skipped_duplicate_count = 0
    new_lines: list[str] = []
    seen_in_batch: set[str] = set()
    for candidate in candidates:
        author_id = candidate.get("author_id")
        if not author_id:
            continue
        if author_id in existing_ids or author_id in seen_in_batch:
            skipped_duplicate_count += 1
            continue
        seen_in_batch.add(author_id)
        record = {k: candidate.get(k) for k in _PERSISTED_FIELDS if k != "registered_at"}
        record["registered_at"] = registered_at
        new_lines.append(json.dumps(record, ensure_ascii=False))
        appended_count += 1

    if new_lines:
        with path.open("a", encoding="utf-8") as f:
            for line in new_lines:
                f.write(line + "\n")

    return {
        "appended_count": appended_count,
        "skipped_duplicate_count": skipped_duplicate_count,
        "total_before": total_before,
        "total_after": total_before + appended_count,
    }
