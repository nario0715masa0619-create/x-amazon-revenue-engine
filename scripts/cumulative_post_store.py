"""Phase 1収集結果を横断的に蓄積する累積ストア（JSONL、追記専用）のpure function層。

`outputs/x_api_phase1/merged_deduped.json`（.gitignore対象、実行ごとに`write_text()`で
完全上書きされる。scripts/x_api_phase1_collect.py:342参照）とは完全に別の、
追加専用の記録層である。post_id基準で既存レコードと突き合わせ、未登録のpost_idのみを
追記する。

**既存のPhase 1収集ロジック・Phase 2 classifyの入出力パスは一切変更しない**——
`merged_deduped.json`は引き続き実行ごとに上書きされ、`x_api_phase2_classify.py`は
引き続きこの単発ファイルのみを読む（GOV-20260901-DAILY-PIPELINE-01調査により、
この設計変更がPhase 2・topic_group連携に影響しないことを確認済み。累積ストアは
現時点ではPhase 2の入力として使われない、独立した蓄積専用レイヤー）。

**重要な設計判断（本文とテキストハッシュの除外）**: `.gitignore`は
`outputs/x_api_phase1/`を「実データ・投稿本文を含みうるためコミット対象外」と
明記しており、本リポジトリは**public**リポジトリである。累積ストアは
`ops/data/`配下のgit追跡対象ファイルとして永続化する設計のため、この既存方針との
整合を取り、**`text`（投稿本文そのもの）は累積ストアへ一切書き込まない**——
post_id・author_id・作成日時・エンゲージメント実測値・`text_hash`
（本文から算出済みのハッシュ値、本文そのものではない）・収集元クエリ・
収集日時のみを保持する。本文が必要な再分類等は、その日のうちに
`outputs/x_api_phase1/merged_deduped.json`（ローカル、gitignore対象）を使うか、
将来的に本文を別途非公開の場所で管理する設計を別途検討する必要がある
（本タスクでは対象外、未解決事項として記録する）。

外部AI呼び出しは行わない。Gate A/thresholds/shipping decision、
_apply_engagement_gate()、topic_groupのライフサイクル管理ロジックには一切触れない。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 累積ストアへ永続化するフィールド。"text"（投稿本文）は意図的に除外する
# （上記docstring「重要な設計判断」参照）。
_PERSISTED_FIELDS = (
    "id",
    "author_id",
    "created_at",
    "lang",
    "like_count",
    "reply_count",
    "repost_count",
    "quote_count",
    "impression_count",
    "bookmark_count",
    "query_source",
    "retrieved_at",
    "text_hash",
    "duplicate_count_by_text",
)


class CumulativePostStoreError(ValueError):
    pass


def load_existing_post_ids(path: str | Path) -> set[str]:
    """累積ストアJSONLから既存のpost_id集合を読み込む。ファイルが無ければ空集合を返す
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
            post_id = record.get("id")
            if post_id:
                ids.add(post_id)
    return ids


def append_new_posts(
    path: str | Path,
    posts: list[dict[str, Any]],
    collected_at: str | None = None,
) -> dict[str, Any]:
    """postsのうち、累積ストアに未登録のpost_idのみをJSONLへ追記する。

    既に登録済みのpost_id、および同一バッチ内での重複post_idはスキップする
    （どちらもskipped_duplicate_countへ計上）。id自体が無いレコードは無視する。
    追記対象が0件の場合はファイルへの書き込みを行わない（空のappendでファイル
    タイムスタンプだけ更新することを避ける）。

    戻り値: {"appended_count", "skipped_duplicate_count", "total_before", "total_after"}
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = load_existing_post_ids(path)
    total_before = len(existing_ids)

    appended_count = 0
    skipped_duplicate_count = 0
    new_lines: list[str] = []
    seen_in_batch: set[str] = set()
    for post in posts:
        post_id = post.get("id")
        if not post_id:
            continue
        if post_id in existing_ids or post_id in seen_in_batch:
            skipped_duplicate_count += 1
            continue
        seen_in_batch.add(post_id)
        # "text"（投稿本文）は意図的に除外する（モジュールdocstring「重要な設計判断」参照）。
        record = {k: post.get(k) for k in _PERSISTED_FIELDS}
        record["cumulative_first_seen_at"] = collected_at
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


def load_all_cumulative_posts(path: str | Path) -> list[dict[str, Any]]:
    """累積ストアの全レコードを読み込む（読み取り専用の参照用途）。"""
    path = Path(path)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records
