"""X API v2 recent search — Phase 1 最小収集スクリプト。

Phase 0（scripts/x_api_smoke_test.py）で確認した単一クエリ疎通確認を、
複数クエリ・重複除外・確認用ファイル出力へ拡張したもの。

目的（これ以上は範囲外）:
    - 2〜3本のクエリを順番に実行できる
    - 合計取得件数を50件以内に抑える
    - post id ベースで重複除外できる
    - 生レスポンス保存に加え、人間確認用の一覧（JSON/CSV）を保存できる

やらないこと:
    自動スコアリング／勝ち投稿自動判定／アプローチ教師・構造教師の自動選定／
    採否判定ロジック／UI／DB化／スケジューラ化／Webhook／書き込みAPI

認証:
    プロジェクトルートの .env の X_BEARER_TOKEN を読み込む（コード直書き禁止）。

使い方:
    python scripts/x_api_phase1_collect.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

_API_URL = "https://api.x.com/2/tweets/search/recent"
_TIMEOUT_SECONDS = 15
_POST_FIELDS = "created_at,lang,public_metrics,author_id"  # id, text はデフォルト応答に常時含まれる

# クエリ一覧（固定配列。動的生成・最適化ロジックはまだ入れない）
# 1クエリあたりmax_resultsは10〜20の範囲。
#
# 2026-09-01（広域収集への全面置き換え、GOV-20260901-BROAD-COLLECTION-01）:
# 商品カテゴリ（イヤホン/骨伝導等）を人間が先読みして列挙する旧クエリ設計
# （2026-08-15〜08-27の反復改訂、直下の履歴コメント参照）は、収集の入口を
# 単一カテゴリに閉じ込めてしまう構造的欠陥だったと判明した（詳細:
# ops/reports/broad_teacher_collection_design_2026-09-01.md）。人間の明示的な
# 承認により「Phase 1 query setは変えない」制約を今回に限り解除し、同設計文書
# フェーズ2の6クエリ案（年代語×ジャンル語のOR集約、特定商品名・型番は一切
# 使用しない）へ全面的に置き換えた。旧18クエリは削除し、並行稼働はしない。
#
# 「比較」「実体験」等をAND必須語に含めない方針は維持する（gadget_query_redesign_
# 2026-08-27.mdで「比較」をAND条件に含めると0件に収束すると実証済みのため）。
# 比較構造の有無の判定は引き続きPhase 2分類器（下流）に委ねる。
# OR演算子は大文字`OR`＋`( )`グループ化（X API検索構文）。各クエリは日本語で
# 30〜40文字程度であり、512文字制限に対して十分な余裕がある。
#
# 以下は旧設計（2026-08-15〜08-27）の履歴コメント（参考として保持）:
# 2026-08-15（3回目改訂）: 3語ANDクエリ（40代 持ち物 更新 等）は3本とも0件だったため、
# 2語クエリへ緩めて母数確保を優先する。入口は広めにし、絞り込みはPhase 2の
# 「40代ファッション×ガジェット」分類器（topic_fit/structure_fit/approach_value）に委ねる。
# 旧事件型クエリ（会議/商談/仕事/ペン/出ない等）は引き続き使わない。
# 2026-08-16: 三層探索方針（ops/reports/three_layer_exploration_policy_2026-08-16.md）
# 反映後の初回検証バッチ。「40代 イヤホン」を意図的に再採用し、三層化で追加した
# gadget-only候補化パス（fashion_only_but_reusable/gadget_only_but_reusable）が
# 実データで機能するかを確認する（交点不足でも失敗扱いにしない）。
# 2026-08-27（gadget query再設計）: 「40代 イヤホン」単独クエリはRun1〜7で同一の
# 既知先生（source_post_id=2086972244987900332）にほぼ依存しており、Run8/Run9の
# 2run・通算4回の収集試行で0件（教師要件を満たす候補が無い状態）が継続した。
# manual_review落ちの候補もニュース/愚痴/雑談が中心で、比較構造・実体験・
# usage_scenes・comparison_axesを欠いていた。このため「対象語（イヤホン）だけの
# クエリ」から「teacher-post構造を直接クエリへ埋め込む」方針へ切り替えた
# （詳細: ops/reports/gadget_query_redesign_2026-08-27.md、
# ops/reports/gadget_query_redesign_round3_2026-08-27.md）。この方針も
# 「対象語（商品カテゴリ）を人間が先読みする」という同根の構造的限界を持って
# いたため、2026-09-01の全面置き換えに至った。
QUERIES: list[dict[str, Any]] = [
    # Q1 (gadget): ジャンル語そのもの＋Phase2 GADGET_KEYWORDSと同じ語彙で広く網をかける
    {"query": "(40代 OR アラフォー) (ガジェット OR デバイス OR EDC OR 携帯性)", "max_results": 20},
    # Q2 (gadget): 商品名に依存しない「所有・愛用」を表す一般語
    {"query": "(40代 OR アラフォー) (愛用 OR 手放せない OR 買ってよかった OR 使い分け)", "max_results": 20},
    # Q3 (gadget): 特定製品名を出さない機能・シーン語（複数カテゴリに横断する）
    {"query": "(40代 OR アラフォー) (充電 OR バッテリー OR ケーブル OR 持ち歩き)", "max_results": 20},
    # Q4 (fashion): 既存fashionクエリの延長、商品名は出さない
    {"query": "(40代 OR アラフォー) (小物 OR コーデ OR 身につける OR 着映え)", "max_results": 20},
    # Q5 (fashion): 装身具カテゴリの網（個別ブランド名・型番は含まない）
    {"query": "(40代 OR アラフォー) (バッグ OR 財布 OR 時計 OR ベルト OR メガネ)", "max_results": 20},
    # Q6 (intersection): 初期コミット時点の`服 ガジェット`クエリの精神を踏襲し、交点を直接狙う
    {"query": "(ガジェット OR デバイス) (服 OR コーデ OR ファッション)", "max_results": 20},
]

_REPO_ROOT = Path(__file__).resolve().parent.parent
_OUTPUT_DIR = _REPO_ROOT / "outputs" / "x_api_phase1"
_RAW_DIR = _OUTPUT_DIR / "raw"
_MERGED_BEFORE_PATH = _OUTPUT_DIR / "merged_before_dedup.json"
_MERGED_DEDUPED_JSON_PATH = _OUTPUT_DIR / "merged_deduped.json"
_MERGED_DEDUPED_CSV_PATH = _OUTPUT_DIR / "merged_deduped.csv"
_TEXT_DUPLICATE_GROUPS_PATH = _OUTPUT_DIR / "text_duplicate_groups.json"
_RUN_SUMMARY_PATH = _OUTPUT_DIR / "run_summary.json"

_CSV_COLUMNS = [
    "id",
    "created_at",
    "author_id",
    "lang",
    "text",
    "like_count",
    "reply_count",
    "repost_count",
    "quote_count",
    "impression_count",
    "bookmark_count",
    "query_source",
    "text_hash",
    "duplicate_count_by_text",
    "duplicate_post_ids",
]

# Phase 1.1（2026-08-16）: 本文ハッシュ second-pass dedup。
# id単位のdedupだけでは、同じ元投稿の別ユーザーによるRTや同文再掲を別件として
# 残してしまう（例: 「演劇ジャンキー」投稿が同文リツイートで10件に水増しされた実例、
# 詳細はops/reports/manual_review_review_2026-08-15.md）。RTプレフィックス除去・URL
# プレースホルダ化・空白/改行正規化・大小文字統一までの最小正規化のみを行い、
# 意味類似judgeやLLM判定は行わない（過剰に似ているだけの別投稿はまとめない）。
_RT_PREFIX_PATTERN = re.compile(r"^(?:RT|QT)\s+@[A-Za-z0-9_]+:\s*")
_URL_PATTERN = re.compile(r"https?://\S+")
_WHITESPACE_RUN_PATTERN = re.compile(r"[ \t　]+")


def normalize_post_text(text: str) -> str:
    """本文dedup用の最小正規化。別投稿まで同一視しないよう、意味を変える正規化はしない。"""
    normalized = (text or "").strip()
    normalized = _RT_PREFIX_PATTERN.sub("", normalized)
    normalized = _URL_PATTERN.sub("[URL]", normalized)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.strip() for line in normalized.split("\n"))
    normalized = _WHITESPACE_RUN_PATTERN.sub(" ", normalized)
    return normalized.strip().lower()


def compute_text_hash(normalized_text: str) -> str:
    """正規化済みテキストからsha256ハッシュを計算する（標準ライブラリのみ）。"""
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def _select_representative(group: list[dict]) -> dict:
    """同一本文グループの代表投稿を選ぶ。優先順位: impression数 > like数 > created_atが新しい > 最初の1件。

    sorted(reverse=True)はCPythonの安定ソート特性により、キーが同点の要素は
    元の出現順を保つ（=最初に見つかった投稿が優先される）。
    """
    ranked = sorted(
        group,
        key=lambda p: (
            p.get("impression_count") or 0,
            p.get("like_count") or 0,
            p.get("created_at") or "",
        ),
        reverse=True,
    )
    return ranked[0]


def _load_bearer_token() -> str:
    """.env（プロジェクトルート）から X_BEARER_TOKEN を読み込む。無ければ os.environ にフォールバック。"""
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


def _fetch_query(token: str, query: str, max_results: int) -> tuple[dict | None, dict | None]:
    """1クエリ分を実行する。成功なら (payload, None)、失敗なら (None, failure_info) を返す。"""
    headers = {"Authorization": f"Bearer {token}"}
    params = {"query": query, "max_results": max_results, "tweet.fields": _POST_FIELDS}

    try:
        response = requests.get(_API_URL, headers=headers, params=params, timeout=_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        return None, {"query": query, "status_code": None, "reason": f"接続エラー: {exc}"}

    if not response.ok:
        reason = {
            401: "認証失敗（Bearer Token失効の可能性）",
            403: "アクセス拒否（権限設定を確認）",
            429: "レート制限到達",
        }.get(response.status_code, "サーバーエラーまたは未分類のHTTPエラー")
        print(f"[失敗] query={query!r} HTTP {response.status_code}（{reason}）", file=sys.stderr)
        print(response.text, file=sys.stderr)
        return None, {
            "query": query,
            "status_code": response.status_code,
            "reason": reason,
            "response_text": response.text[:2000],
        }

    return response.json(), None


def _flatten_post(post: dict, query_sources: list[str], retrieved_at: str) -> dict:
    """1投稿を、後段のJSON/CSV両方で使える平坦な形にする。"""
    metrics = post.get("public_metrics", {})
    return {
        "id": post.get("id"),
        "text": post.get("text"),
        "author_id": post.get("author_id"),
        "created_at": post.get("created_at"),
        "lang": post.get("lang"),
        "like_count": metrics.get("like_count"),
        "reply_count": metrics.get("reply_count"),
        "repost_count": metrics.get("retweet_count"),  # X API側の名称はretweet_count
        "quote_count": metrics.get("quote_count"),
        "impression_count": metrics.get("impression_count"),
        "bookmark_count": metrics.get("bookmark_count"),
        "query_source": query_sources,
        "retrieved_at": retrieved_at,
    }


def main() -> None:
    token = _load_bearer_token()
    _RAW_DIR.mkdir(parents=True, exist_ok=True)

    run_started_at = datetime.now(timezone.utc).isoformat()
    per_query_results: list[dict] = []
    failures: list[dict] = []
    before_dedup: list[dict] = []

    for i, q in enumerate(QUERIES, start=1):
        query, max_results = q["query"], q["max_results"]
        payload, failure = _fetch_query(token, query, max_results)

        raw_path = _RAW_DIR / f"query_{i:02d}.json"

        if failure is not None:
            failures.append(failure)
            raw_path.write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
            per_query_results.append({"query": query, "max_results": max_results, "retrieved_count": 0, "status": "failed"})
            continue

        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        posts = payload.get("data", [])
        retrieved_at = datetime.now(timezone.utc).isoformat()
        for post in posts:
            before_dedup.append(_flatten_post(post, [query], retrieved_at))

        per_query_results.append(
            {"query": query, "max_results": max_results, "retrieved_count": len(posts), "status": "ok"}
        )
        print(f"[成功] query={query!r} 取得件数={len(posts)}")

    if not before_dedup and len(failures) == len(QUERIES):
        # 全クエリ失敗
        print("全クエリが失敗しました。", file=sys.stderr)
        _RUN_SUMMARY_PATH.write_text(
            json.dumps(
                {
                    "run_started_at": run_started_at,
                    "queries": per_query_results,
                    "total_before_dedup": 0,
                    "total_after_dedup": 0,
                    "duplicate_count": 0,
                    "status": "failed",
                    "failures": failures,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        sys.exit(1)

    _MERGED_BEFORE_PATH.write_text(json.dumps(before_dedup, ensure_ascii=False, indent=2), encoding="utf-8")

    # id ベースで重複除外。query_sourceは配列にまとめ、どのクエリで重複ヒットしたか分かるようにする。
    deduped: dict[str, dict] = {}
    for post in before_dedup:
        post_id = post["id"]
        if post_id in deduped:
            existing_sources = deduped[post_id]["query_source"]
            for src in post["query_source"]:
                if src not in existing_sources:
                    existing_sources.append(src)
        else:
            deduped[post_id] = dict(post)

    deduped_list = list(deduped.values())
    dedup_by_id_count = len(before_dedup) - len(deduped_list)

    # Phase 1.1: idベースdedup後の後段として、本文正規化ハッシュでsecond-pass dedupを行う。
    # 同じ元投稿の別ユーザーによるRTや同文再掲を1件の代表投稿にまとめる。
    text_groups: dict[str, list[dict]] = {}
    for post in deduped_list:
        text_hash = compute_text_hash(normalize_post_text(post.get("text") or ""))
        text_groups.setdefault(text_hash, []).append(post)

    final_deduped_list: list[dict] = []
    text_duplicate_groups: list[dict] = []
    for text_hash, group in text_groups.items():
        representative_source = _select_representative(group)
        merged_query_source: list[str] = []
        for p in group:
            for src in p.get("query_source") or []:
                if src not in merged_query_source:
                    merged_query_source.append(src)
        duplicate_post_ids = [p["id"] for p in group if p["id"] != representative_source["id"]]

        representative = dict(representative_source)
        representative["query_source"] = merged_query_source
        representative["text_hash"] = text_hash
        representative["duplicate_count_by_text"] = len(group)
        representative["duplicate_post_ids"] = duplicate_post_ids
        final_deduped_list.append(representative)

        if len(group) > 1:
            text_duplicate_groups.append(
                {
                    "text_hash": text_hash,
                    "representative_post_id": representative_source["id"],
                    "duplicate_post_ids": duplicate_post_ids,
                    "group_size": len(group),
                    "query_source": merged_query_source,
                    "sample_text": representative_source.get("text"),
                }
            )

    dedup_by_text_count = len(deduped_list) - len(final_deduped_list)

    _MERGED_DEDUPED_JSON_PATH.write_text(
        json.dumps(final_deduped_list, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with _MERGED_DEDUPED_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for post in final_deduped_list:
            row = {col: post.get(col) for col in _CSV_COLUMNS}
            row["query_source"] = ";".join(row["query_source"] or [])
            row["duplicate_post_ids"] = ";".join(row["duplicate_post_ids"] or [])
            writer.writerow(row)

    if text_duplicate_groups:
        _TEXT_DUPLICATE_GROUPS_PATH.write_text(
            json.dumps(text_duplicate_groups, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    status = "partial_success" if failures else "success"
    run_summary = {
        "run_started_at": run_started_at,
        "queries": per_query_results,
        # 2026-08-16（Phase 1.1）: total_after_dedup / duplicate_count は
        # 「id dedup + 本文hash dedup」を経た最終件数を指すよう意味を変更した
        # （merged_deduped.json / .csv の実際の中身と一致させるため）。
        # id単独の内訳はdedup_by_id_count / dedup_by_text_countで別途確認できる。
        "total_before_dedup": len(before_dedup),
        "total_after_dedup": len(final_deduped_list),
        "duplicate_count": len(before_dedup) - len(final_deduped_list),
        "merged_before_dedup_count": len(before_dedup),
        "dedup_by_id_count": dedup_by_id_count,
        "dedup_by_text_count": dedup_by_text_count,
        "final_deduped_count": len(final_deduped_list),
        "text_duplicate_groups_count": len(text_duplicate_groups),
        "max_duplicate_group_size": max((g["group_size"] for g in text_duplicate_groups), default=1),
        "duplicate_examples": text_duplicate_groups[:5],
        "status": status,
        "failures": failures,
    }
    _RUN_SUMMARY_PATH.write_text(json.dumps(run_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"マージ前総件数: {len(before_dedup)}")
    print(f"idベースdedup後件数: {len(deduped_list)}（除外{dedup_by_id_count}件）")
    print(f"本文ハッシュdedup後件数: {len(final_deduped_list)}（除外{dedup_by_text_count}件）")
    print(f"本文重複グループ数: {len(text_duplicate_groups)}")
    print(f"失敗クエリ数: {len(failures)} / {len(QUERIES)}")
    print(f"保存先: {_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
