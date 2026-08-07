"""Google Sheets読み書き。posts/reviews/metrics_24hシートを列名（ヘッダー）ベースで扱う。

列の並び順が変わっても壊れないよう、ハードコードした列番号ではなく
1行目のヘッダー文字列をキーにして読み書きする。

2026-08-07追加: `ops-state` MCPサーバー（scripts/ops_state_mcp/）の実体としても使う。
posts/reviews/metrics_24hがPhase 1の正本であり、このクラスがその唯一の読み書き経路になる
（ops/logs/post_log.jsonl・ops/logs/metrics_snapshots.csvは凍結、新規追記はここを経由する）。
"""

from __future__ import annotations

import base64
import datetime as dt
import json
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from .config import Config

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    def __init__(self, config: Config):
        self._config = config
        self._gc = gspread.authorize(self._build_credentials(config))
        self._spreadsheet = self._gc.open_by_key(config.spreadsheet_id)

    @staticmethod
    def _build_credentials(config: Config) -> Credentials:
        if config.service_account_json_path:
            return Credentials.from_service_account_file(
                config.service_account_json_path, scopes=_SCOPES
            )
        if config.service_account_json_base64:
            decoded = base64.b64decode(config.service_account_json_base64).decode("utf-8")
            info = json.loads(decoded)
            return Credentials.from_service_account_info(info, scopes=_SCOPES)
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON_PATH または "
            "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64 のいずれかを設定してください。"
        )

    def get_posts(self) -> list[dict[str, Any]]:
        """postsシートを [{列名: 値}, ...] のリストで返す（1行目をヘッダーとして使用）。"""
        ws = self._spreadsheet.worksheet(self._config.posts_sheet_name)
        return ws.get_all_records()

    def get_metrics_24h_rows(self) -> list[dict[str, Any]]:
        """metrics_24hシートを [{列名: 値}, ...] のリストで返す。"""
        ws = self._spreadsheet.worksheet(self._config.metrics_sheet_name)
        return ws.get_all_records()

    def find_metrics_row_index(self, post_id: str, check_window: str) -> int | None:
        """既存の metrics_24h 行（同一 post_id + check_window）のシート上の行番号
        （1始まり、ヘッダー行込み）を返す。見つからなければ None。"""
        ws = self._spreadsheet.worksheet(self._config.metrics_sheet_name)
        records = ws.get_all_records()
        for i, record in enumerate(records, start=2):  # 1行目はヘッダーなのでデータは2行目から
            if str(record.get("post_id")) == post_id and str(record.get("check_window")) == check_window:
                return i
        return None

    def upsert_metrics_row(self, row: dict[str, Any], existing_row_index: int | None) -> None:
        """metrics_24hシートに1行を追記、または既存行を上書き更新する。

        既存行がある場合は新しい行を増やさず、その場で更新する
        （post_id + check_window が重複した行を積み上げない設計）。
        """
        ws = self._spreadsheet.worksheet(self._config.metrics_sheet_name)
        header = ws.row_values(1)
        values = [row.get(col, "") for col in header]

        if existing_row_index is not None:
            # gspread v6.2.1で確認済み: update(values, range_name=None, ...)。
            # キーワード引数range_name/valuesはこのバージョンの実シグネチャと一致する（2026-08-06 Context7で確認）。
            ws.update(range_name=f"A{existing_row_index}", values=[values])
        else:
            ws.append_row(values, value_input_option="USER_ENTERED")

    # ------------------------------------------------------------------
    # 2026-08-07追加: ops-state MCPサーバーが使うposts/reviews/metrics_24h
    # の汎用read/writeメソッド。既存のupsert_metrics_row等はそのまま維持し、
    # 下記メソッドから内部的に再利用する（ロジックの重複を避ける）。
    # ------------------------------------------------------------------

    def get_post(self, post_id: str) -> dict[str, Any] | None:
        """postsシートから1件をpost_idで検索して返す。見つからなければNone。"""
        for record in self.get_posts():
            if str(record.get("post_id")) == post_id:
                return record
        return None

    def list_posts(self, filter_: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """postsシートを、指定された列=値の条件（AND）で絞り込んで返す。filter_が空なら全件。"""
        records = self.get_posts()
        if not filter_:
            return records
        return [
            r for r in records
            if all(str(r.get(k, "")) == str(v) for k, v in filter_.items())
        ]

    def _find_post_row_index(self, post_id: str) -> int | None:
        ws = self._spreadsheet.worksheet(self._config.posts_sheet_name)
        records = ws.get_all_records()
        for i, record in enumerate(records, start=2):  # 1行目はヘッダー
            if str(record.get("post_id")) == post_id:
                return i
        return None

    def record_post_draft(self, post: dict[str, Any]) -> None:
        """postsシートに新規行を1件追記する。post_idは呼び出し側（logger相当）が発番済みのものを渡す。

        同一post_idの既存行がある場合はエラーにする(post_idの二重発行を防ぐ既存ルールを踏襲)。
        """
        if self._find_post_row_index(post["post_id"]) is not None:
            raise RuntimeError(
                f"post_id={post['post_id']} は既にpostsシートに存在します。"
                "新規post_idを発番するか、set_post_statusで更新してください。"
            )
        ws = self._spreadsheet.worksheet(self._config.posts_sheet_name)
        header = ws.row_values(1)
        values = [post.get(col, "") for col in header]
        ws.append_row(values, value_input_option="USER_ENTERED")

    def set_post_status(
        self,
        post_id: str,
        status: str,
        approved_by: str | None = None,
        notes: str | None = None,
    ) -> None:
        """postsシートの該当行のreview_status（+approved_by/notes）を更新する。

        review_status列がpost_log.schema.jsonの`status`enum相当を保持する
        （列名はgsheets_ledger_design.mdのposts列設計に合わせてreview_status）。
        """
        row_index = self._find_post_row_index(post_id)
        if row_index is None:
            raise RuntimeError(f"post_id={post_id} がpostsシートに見つかりません")
        ws = self._spreadsheet.worksheet(self._config.posts_sheet_name)
        header = ws.row_values(1)
        updates: dict[str, str] = {"review_status": status}
        if approved_by is not None:
            updates["approved_by"] = approved_by
        if notes is not None:
            updates["notes"] = notes
        for col_name, value in updates.items():
            if col_name not in header:
                continue
            col_index = header.index(col_name) + 1
            ws.update_cell(row_index, col_index, value)

    def get_reviews(self, post_id: str) -> list[dict[str, Any]]:
        """reviewsシートを、指定post_idで絞り込んで返す。"""
        ws = self._spreadsheet.worksheet(self._config.reviews_sheet_name)
        return [r for r in ws.get_all_records() if str(r.get("post_id")) == post_id]

    def record_review_result(self, review: dict[str, Any]) -> str:
        """reviewsシートに1件追記する。review_idを`rv-{post_id}-{連番}`で発番して返す。

        必須キー: post_id, reviewer。それ以外(axis_scores等)は任意で、
        該当列が無ければ無視される(列追加はシート側で吸収する設計)。
        `axis_scores`はdictで渡された場合、Sheetsのセルに収めるためJSON文字列化する。
        """
        post_id = review["post_id"]
        existing = self.get_reviews(post_id)
        review_id = f"rv-{post_id}-{len(existing) + 1:03d}"
        row = dict(review)
        row["review_id"] = review_id
        row.setdefault("reviewed_at", dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
        if isinstance(row.get("axis_scores"), dict):
            row["axis_scores"] = json.dumps(row["axis_scores"], ensure_ascii=False)

        ws = self._spreadsheet.worksheet(self._config.reviews_sheet_name)
        header = ws.row_values(1)
        values = [row.get(col, "") for col in header]
        ws.append_row(values, value_input_option="USER_ENTERED")
        return review_id

    def record_metrics_snapshot(
        self,
        post_id: str,
        window: str,
        values: dict[str, Any],
        data_quality: str,
        source: str,
        notes: str = "",
    ) -> str:
        """metrics_24hシートに1行をupsertする(同一post_id+windowがあれば更新)。

        `values`は impression_count/like_count/reply_count/bookmark_count/
        user_profile_clicks/url_link_clicks/engagements のうち埋まっているものだけ渡せばよい。
        `source`は"manual_screenshot"または"x_api"を想定(将来の取得経路を区別する新規列)。

        既存行が`data_quality: manual`(スクショ運用由来)の場合、`data_quality`が`manual`以外の
        呼び出しによる上書きを拒否する(x_metrics_collector.pyの既存の保護ルールを踏襲)。
        """
        from .collector import _compute_profile_visit_rate, _next_snapshot_id  # 既存ロジックを再利用

        existing_index = self.find_metrics_row_index(post_id, window)
        existing_rows = self.get_metrics_24h_rows()

        if existing_index is not None:
            existing_row = existing_rows[existing_index - 2]
            if existing_row.get("data_quality") == "manual" and data_quality != "manual":
                raise RuntimeError(
                    f"post_id={post_id} window={window} は既にdata_quality=manual"
                    "(スクショ運用由来)で記録済みのため、上書きを拒否しました。"
                )
            snapshot_id = existing_row.get("snapshot_id") or _next_snapshot_id(existing_rows, dt.date.today())
        else:
            snapshot_id = _next_snapshot_id(existing_rows, dt.date.today())

        impression_count = values.get("impression_count", "")
        row = {
            "snapshot_id": snapshot_id,
            "post_id": post_id,
            "check_window": window,
            "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "impression_count": impression_count,
            "like_count": values.get("like_count", ""),
            "reply_count": values.get("reply_count", ""),
            "bookmark_count": values.get("bookmark_count", ""),
            "user_profile_clicks": values.get("user_profile_clicks", ""),
            "url_link_clicks": values.get("url_link_clicks", ""),
            "engagements": values.get("engagements", ""),
            "profile_visit_rate": _compute_profile_visit_rate(
                values.get("user_profile_clicks"), impression_count
            ),
            "data_quality": data_quality,
            "source": source,
            "notes": notes,
        }
        self.upsert_metrics_row(row, existing_index)
        return snapshot_id

    def count_same_condition_samples(self, mode: str, format_: str, cta_type: str) -> int:
        """同条件群(mode/format/cta_type一致)のうち、実測profile_visit_rateを持つ件数を返す。

        CTA別強さ判定ルール(docs/strategy/kpi-definition.md)のCold-start mode/
        Relative benchmark modeの切り替え判定にそのまま使う想定(閾値5件は呼び出し側で判定する)。
        """
        matching_ids = {
            str(p.get("post_id"))
            for p in self.get_posts()
            if p.get("mode") == mode and p.get("format") == format_ and p.get("cta_type") == cta_type
        }
        if not matching_ids:
            return 0
        return sum(
            1
            for m in self.get_metrics_24h_rows()
            if str(m.get("post_id")) in matching_ids and str(m.get("profile_visit_rate", "")).strip()
        )
