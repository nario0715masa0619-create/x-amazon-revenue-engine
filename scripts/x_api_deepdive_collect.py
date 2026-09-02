"""teacher輩出アカウントの深掘り収集スクリプト。

scripts/x_api_phase1_collect.py（`search/recent`、キーワード広域収集）とは別に、
`GET /2/users/:id/tweets`で既知の監視対象アカウント（scripts/watched_account_state.py
の`watch_status=="active"`なauthor_id）の過去投稿を深掘りする。設計文書の比較調査
（フェーズ1）で確認済みのとおり、`search/recent`は日数（直近7日）で頭打ちになるのに対し、
本エンドポイントは件数（直近3,200件）で頭打ちになるため、「既知の反応良好アカウント」の
深掘りに向く。

**分類ロジックの再利用について（重要な設計判断）**: 卒業/継続条件
（consecutive_unproductive_deepdive_runs）の判定には、深掘りで新規収集した投稿が
pre_teacher_candidateかどうかを知る必要がある。「判定ロジックは完全に同一のものを使う、
新しい判定ロジックを作らない」という制約を満たすため、x_api_phase2_classify.pyの
`_observe()`/`_classify()`（内部で`_classify_core()`→`_apply_engagement_gate()`を
順に呼ぶ、既存の分類パイプラインの正本）を**そのままimportして呼び出す**（コードの
複製・再実装は一切行わない）。x_api_phase2_classify.py自体は一切変更していない
（importするだけ）。

**投稿本文の扱い**: 分類判定にはtext（本文）が必要なため、収集直後のメモリ上・
outputs/x_api_deepdive/（.gitignore対象、実データ含みうるためコミット対象外）への
デバッグ出力にはtextを含む。ただし**git管理下に入る永続化（累積ストアへのマージ）では
既存のcumulative_post_store.append_new_posts()を変更せずそのまま使うため、textは
自動的に除外される**（cumulative_post_store.py自身の設計判断を踏襲、変更不要）。

Gate A / thresholds / shipping decision、`_apply_engagement_gate()`本体、
既存の日次キーワード収集ワークフロー本体、Phase 1 query setには一切触れていない。

使い方:
    python scripts/x_api_deepdive_collect.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cumulative_post_store import append_new_posts
from teacher_theme_extraction import register_proposed_topic_group_from_teacher_post
from topic_group_state import load_topic_group_state_store, save_topic_group_state_store
from watched_account_state import (
    active_author_ids,
    load_watched_account_state_store,
    record_deepdive_run_result,
    save_watched_account_state_store,
)
from x_api_phase2_classify import _classify, _observe  # noqa: F401 — 既存分類ロジックの再利用のみ、変更なし

_API_URL_TEMPLATE = "https://api.x.com/2/users/{user_id}/tweets"
_TIMEOUT_SECONDS = 15
_POST_FIELDS = "created_at,lang,public_metrics"
_MAX_RESULTS = 100

_REPO_ROOT = Path(__file__).resolve().parent.parent
_OUTPUT_DIR = _REPO_ROOT / "outputs" / "x_api_deepdive"
_CUMULATIVE_STORE_PATH = _REPO_ROOT / "ops" / "data" / "x_api_phase1_cumulative.jsonl"
_WATCHED_ACCOUNT_STATE_PATH = _REPO_ROOT / "ops" / "data" / "watched_account_state.json"
# post_generation_pipeline.py の _DEFAULT_TOPIC_GROUP_STATE_PATH と同一パス
# （変更する場合は両方を同時に更新すること。理由はextract_topic_groups_from_teachers.py
# のコメント参照）。
_TOPIC_GROUP_STATE_PATH = _REPO_ROOT / "ops" / "reports" / "topic_group_state_2026-08-31.json"


def _load_bearer_token() -> str:
    """.env（プロジェクトルート）から X_BEARER_TOKEN を読み込む。無ければ os.environ にフォールバック。

    scripts/x_api_phase1_collect.py:_load_bearer_token()と同じロジック。既存コードの
    import・変更ではなく、リポジトリ内に前例のない cross-module private import を
    避けるため、この小さなヘルパーのみ複製している。
    """
    try:
        from dotenv import load_dotenv

        load_dotenv(_REPO_ROOT / ".env")
    except ImportError:
        pass

    token = os.environ.get("X_BEARER_TOKEN", "").strip()
    if not token:
        print(
            "エラー: X_BEARER_TOKEN が見つかりません。"
            "プロジェクトルートの .env に X_BEARER_TOKEN=... を設定してください。",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def _fetch_user_tweets(token: str, author_id: str, since_id: str | None) -> tuple[dict | None, dict | None]:
    """1アカウント分を実行する。成功なら (payload, None)、失敗なら (None, failure_info) を返す。"""
    headers = {"Authorization": f"Bearer {token}"}
    params: dict[str, Any] = {"max_results": _MAX_RESULTS, "tweet.fields": _POST_FIELDS}
    if since_id:
        params["since_id"] = since_id

    url = _API_URL_TEMPLATE.format(user_id=author_id)
    try:
        response = requests.get(url, headers=headers, params=params, timeout=_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        return None, {"author_id": author_id, "status_code": None, "reason": f"接続エラー: {exc}"}

    if not response.ok:
        reason = {
            401: "認証失敗（Bearer Token失効の可能性）",
            403: "アクセス拒否（権限設定を確認）",
            404: "アカウントが見つからない（削除・凍結の可能性）",
            429: "レート制限到達",
        }.get(response.status_code, "サーバーエラーまたは未分類のHTTPエラー")
        print(f"[失敗] author_id={author_id!r} HTTP {response.status_code}（{reason}）", file=sys.stderr)
        return None, {
            "author_id": author_id,
            "status_code": response.status_code,
            "reason": reason,
            "response_text": response.text[:2000],
        }

    return response.json(), None


def _flatten_post(post: dict, author_id: str, query_source: str, retrieved_at: str) -> dict:
    """1投稿を、Phase 1（x_api_phase1_collect.py:_flatten_post）と同じ形へ平坦化する。

    _observe()/_classify()（x_api_phase2_classify.py）はこのスキーマ（id/text/author_id/
    created_at/lang/like_count等）を前提にしており、Phase 1の出力と同じ形にすることで
    分類ロジックをそのまま流用できる。
    """
    metrics = post.get("public_metrics", {})
    return {
        "id": post.get("id"),
        "text": post.get("text"),
        "author_id": author_id,
        "created_at": post.get("created_at"),
        "lang": post.get("lang"),
        "like_count": metrics.get("like_count"),
        "reply_count": metrics.get("reply_count"),
        "repost_count": metrics.get("retweet_count"),
        "quote_count": metrics.get("quote_count"),
        "impression_count": metrics.get("impression_count"),
        "bookmark_count": metrics.get("bookmark_count"),
        "query_source": [query_source],
        "retrieved_at": retrieved_at,
    }


def main() -> None:
    token = _load_bearer_token()
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    state_store = load_watched_account_state_store(_WATCHED_ACCOUNT_STATE_PATH)
    targets = active_author_ids(state_store)
    topic_group_store = load_topic_group_state_store(_TOPIC_GROUP_STATE_PATH)
    newly_proposed_topic_groups: list[str] = []

    run_started_at = datetime.now(timezone.utc).isoformat()
    all_collected_posts: list[dict] = []
    per_account_results: list[dict] = []
    failures: list[dict] = []

    if not targets:
        print("監視対象アカウント（watch_status=active）が0件のため、収集を行いません。")

    for author_id in targets:
        state = state_store[author_id]
        payload, failure = _fetch_user_tweets(token, author_id, state.last_deepdive_since_id)

        raw_path = _OUTPUT_DIR / f"author_{author_id}.json"

        if failure is not None:
            failures.append(failure)
            raw_path.write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
            per_account_results.append({"author_id": author_id, "retrieved_count": 0, "status": "failed"})
            record_deepdive_run_result(
                state,
                found_new_pre_teacher_candidate=False,
                since_id=None,
                checked_at=run_started_at,
            )
            continue

        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        posts = payload.get("data", [])
        retrieved_at = datetime.now(timezone.utc).isoformat()
        query_source = f"deepdive:{author_id}"
        flattened = [_flatten_post(p, author_id, query_source, retrieved_at) for p in posts]
        all_collected_posts.extend(flattened)

        # 既存の_observe()/_classify()（x_api_phase2_classify.py、変更なし・importのみ）を
        # そのまま呼び出し、pre_teacher_candidateが新規に見つかったかを判定する
        # （卒業/継続条件の入力信号。分類ロジック自体はここでは一切実装し直さない）。
        #
        # 2026-09-02追加（GOV-20260902-TEACHER-THEME-AUTOEXTRACT-01）: 深掘り収集経路は
        # 本文（text）をcumulative_post_storeへ合流させる際に除外する設計のため、
        # topic_group自動抽出（本文が必要）はこの時点、本文がまだメモリ上にある間に
        # 行う必要がある。pre_teacher_candidateとなった投稿全件についてtopic_group抽出を
        # 試み、"proposed"状態でtopic_group_stateストアへ登録する
        # （register_proposed_topic_group_from_teacher_post()、既存のGate A/thresholds/
        # shipping decision/_apply_engagement_gate()/_classify_core()には一切触れない）。
        found_new_pre_teacher_candidate = False
        for post in flattened:
            obs = _observe(post)
            classification, _reasons, _confidence, _manual_reason = _classify(post, obs)
            if classification != "pre_teacher_candidate":
                continue
            found_new_pre_teacher_candidate = True
            extraction_result = register_proposed_topic_group_from_teacher_post(
                topic_group_store, post["text"], source_diversity_tag=post["id"]
            )
            if extraction_result is not None:
                extracted_state, _profile = extraction_result
                newly_proposed_topic_groups.append(extracted_state.topic_group_id)

        newest_id = payload.get("meta", {}).get("newest_id")
        record_deepdive_run_result(
            state,
            found_new_pre_teacher_candidate=found_new_pre_teacher_candidate,
            since_id=newest_id,
            checked_at=run_started_at,
        )
        per_account_results.append(
            {
                "author_id": author_id,
                "retrieved_count": len(posts),
                "found_new_pre_teacher_candidate": found_new_pre_teacher_candidate,
                "status": "ok",
            }
        )
        print(
            f"[成功] author_id={author_id!r} 取得件数={len(posts)} "
            f"pre_teacher_candidate新規検出={found_new_pre_teacher_candidate}"
        )

    save_watched_account_state_store(state_store, _WATCHED_ACCOUNT_STATE_PATH)
    if newly_proposed_topic_groups:
        save_topic_group_state_store(topic_group_store, _REPO_ROOT, label="2026-08-31")

    # 既存のcumulative_post_store.append_new_posts()をそのまま使い、日次キーワード収集分と
    # 同じ累積ストアへ合流させる（post_id基準の重複排除は関数側で自動的に効く。text本文は
    # append_new_posts()自体の既存設計により保存されない）。
    merge_result = append_new_posts(
        _CUMULATIVE_STORE_PATH, all_collected_posts, collected_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    run_summary = {
        "run_started_at": run_started_at,
        "target_account_count": len(targets),
        "accounts": per_account_results,
        "failures": failures,
        "total_collected_posts": len(all_collected_posts),
        "cumulative_store_merge": merge_result,
        "newly_proposed_topic_groups": sorted(set(newly_proposed_topic_groups)),
    }
    (_OUTPUT_DIR / "run_summary.json").write_text(
        json.dumps(run_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"監視対象アカウント数: {len(targets)}")
    print(f"収集投稿総数: {len(all_collected_posts)}")
    print(f"累積ストアへの新規追加: {merge_result['appended_count']}件")
    print(f"失敗アカウント数: {len(failures)} / {len(targets)}")
    print(f"新規proposed topic_group: {len(set(newly_proposed_topic_groups))}件")
    print(f"保存先: {_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
