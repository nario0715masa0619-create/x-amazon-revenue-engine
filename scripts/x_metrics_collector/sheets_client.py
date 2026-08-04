"""Google Sheets読み書き。posts/metrics_24hシートを列名（ヘッダー）ベースで扱う。

列の並び順が変わっても壊れないよう、ハードコードした列番号ではなく
1行目のヘッダー文字列をキーにして読み書きする。
"""

from __future__ import annotations

import base64
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
            # gspread >= 5.x を想定。バージョンによりupdate()の引数仕様が異なる場合は要調整。
            ws.update(range_name=f"A{existing_row_index}", values=[values])
        else:
            ws.append_row(values, value_input_option="USER_ENTERED")
