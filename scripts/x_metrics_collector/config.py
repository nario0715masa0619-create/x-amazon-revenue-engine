"""環境変数からの設定読み込み。

認証情報の実値はこのリポジトリのどのファイルにも書かない。
.env はコミット対象外（.gitignore で除外すること）。値は .env.example を参考に各自で設定する。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    spreadsheet_id: str
    service_account_json_path: str | None
    service_account_json_base64: str | None
    x_bearer_token: str | None
    x_user_access_token: str | None
    posts_sheet_name: str
    metrics_sheet_name: str


def load_config() -> Config:
    """環境変数から設定を読み込む。python-dotenv があれば .env も読む（無くても動く）。"""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    spreadsheet_id = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
    if not spreadsheet_id:
        raise RuntimeError(
            "GOOGLE_SHEETS_SPREADSHEET_ID が未設定です。"
            ".env.example を参考に .env を作成してください。"
        )

    return Config(
        spreadsheet_id=spreadsheet_id,
        service_account_json_path=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_PATH") or None,
        service_account_json_base64=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64") or None,
        x_bearer_token=os.environ.get("X_BEARER_TOKEN") or None,
        x_user_access_token=os.environ.get("X_USER_ACCESS_TOKEN") or None,
        posts_sheet_name=os.environ.get("POSTS_SHEET_NAME", "posts"),
        metrics_sheet_name=os.environ.get("METRICS_SHEET_NAME", "metrics_24h"),
    )
