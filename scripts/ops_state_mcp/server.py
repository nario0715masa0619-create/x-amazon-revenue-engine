"""ops-state MCPサーバー(Phase 1、最小構成)。

投稿OS(morning-strategy-council / execution / market-grounded review /
pre-post-self-check / affiliate-compliance-reviewer)の判断ロジックには一切関与しない。
posts/reviews/metrics_24h(Google Sheets、正本)への読み書きを型付きツールとして
公開するだけの、I/O一本化レイヤー。「何を出すか」は投稿OSが決め、
「どこに書くか・どう読むか」だけをここに寄せる。

起動: python -m scripts.ops_state_mcp.server (stdio transport)
`.mcp.json`に project-scope で登録して、Claude Codeから起動する想定。

認証: scripts/x_metrics_collector/config.py の load_config() をそのまま再利用する
(.envからGOOGLE_SHEETS_SPREADSHEET_ID/GOOGLE_SERVICE_ACCOUNT_JSON_PATH等を読む)。
このファイル自体・このパッケージのどのファイルにも認証情報を書かない。
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ..x_metrics_collector.config import load_config
from ..x_metrics_collector.sheets_client import SheetsClient
from . import validation
from .render import render_daily_brief_markdown

_REPO_ROOT = Path(__file__).resolve().parents[2]

mcp = MCPServer(
    name="ops-state",
    version="0.1.0",
    instructions=(
        "投稿OSのposts/reviews/metrics_24h(Google Sheets)への読み書き専用ツール群。"
        "投稿文の強弱判定・戦略判断・競合比較の判定基準はこのサーバーの責務ではない"
        "(呼び出し側の投稿OSが判断し、判断結果だけをここに記録する)。"
    ),
)

_client: SheetsClient | None = None


def _get_client() -> SheetsClient:
    """SheetsClientの遅延生成。サーバー起動時ではなく最初のツール呼び出し時に接続するため、
    認証情報が未設定でもサーバー自体は起動でき、ツール一覧も確認できる。"""
    global _client
    if _client is None:
        _client = SheetsClient(load_config())
    return _client


@mcp.tool()
def get_post(post_id: str) -> dict[str, Any] | None:
    """postsシートから1件をpost_idで取得する。"""
    return _get_client().get_post(post_id)


@mcp.tool()
def list_posts(
    mode: str | None = None,
    format: str | None = None,
    cta_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """postsシートを、指定した列の値でAND絞り込みして返す(未指定の引数は無視する)。"""
    filter_: dict[str, Any] = {}
    if mode:
        filter_["mode"] = mode
    if format:
        filter_["format"] = format
    if cta_type:
        filter_["cta_type"] = cta_type
    if status:
        filter_["review_status"] = status
    return _get_client().list_posts(filter_)


@mcp.tool()
def record_post_draft(
    post_id: str,
    mode: str,
    format: str,
    cta_type: str,
    angle: str,
    draft_text: str,
    campaign: str | None = None,
    product: str | None = None,
    target: str | None = None,
    disclosure_included: bool = False,
    final_text: str | None = None,
    asset_ids: list[str] | None = None,
    link_id: str | None = None,
    status: str = "draft",
    approved_by: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """新規投稿案をpostsシートに1件記録する(post_idはlogger相当が発番済みのものを渡す)。

    post_log.schema.jsonの必須項目・enum・patternをwrite前に検証する
    (2026-08-06に発覚した「存在しないフィールドへの書き込み」バグの再発防止)。
    """
    post = {
        "post_id": post_id,
        "platform": "X",
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": mode,
        "campaign": campaign or "",
        "product": product or "",
        "angle": angle,
        "target": target or "",
        "format": format,
        "cta_type": cta_type,
        "disclosure_included": disclosure_included,
        "draft_text": draft_text,
        "final_text": final_text or "",
        "asset_ids": ",".join(asset_ids or []),
        "link_id": link_id or "",
        "review_status": status,
        "approved_by": approved_by or "",
        "notes": notes or "",
    }
    validation.validate_post_draft({**post, "status": status})
    _get_client().record_post_draft(post)
    return {"post_id": post_id, "recorded": True}


@mcp.tool()
def set_post_status(
    post_id: str,
    status: str,
    approved_by: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """postsシートの該当行のreview_status(+approved_by/notes)を更新する。"""
    validation.validate_post_status(status)
    _get_client().set_post_status(post_id, status, approved_by, notes)
    return {"post_id": post_id, "status": status, "updated": True}


@mcp.tool()
def get_reviews(post_id: str) -> list[dict[str, Any]]:
    """reviewsシートを、指定post_idで絞り込んで返す。"""
    return _get_client().get_reviews(post_id)


@mcp.tool()
def record_review_result(
    post_id: str,
    reviewer: str,
    action: str,
    hook_assessment: str | None = None,
    whole_post_assessment: str | None = None,
    axis_scores: dict[str, str] | None = None,
    cta_fit_assessment: str | None = None,
    rationale: str | None = None,
    confidence: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """market-grounded review layer / self-check / complianceの判定結果をreviewsシートに1件追記する。

    判定基準そのもの(強い/同等/弱い、keep/revise/hold等)は投稿OS側が決める。
    ここではenumがtemplates/market_grounded_review_template.mdの定義から外れていないかのみ検証する。
    """
    review = {
        "post_id": post_id,
        "reviewer": reviewer,
        "action": action,
        "hook_assessment": hook_assessment,
        "whole_post_assessment": whole_post_assessment,
        "axis_scores": axis_scores,
        "cta_fit_assessment": cta_fit_assessment,
        "rationale": rationale or "",
        "confidence": confidence,
        "notes": notes or "",
    }
    validation.validate_review_result(review)
    review_id = _get_client().record_review_result(review)
    return {"review_id": review_id, "recorded": True}


@mcp.tool()
def record_metrics_snapshot(
    post_id: str,
    window: str,
    data_quality: str,
    source: str,
    impression_count: int | None = None,
    like_count: int | None = None,
    reply_count: int | None = None,
    bookmark_count: int | None = None,
    user_profile_clicks: int | None = None,
    url_link_clicks: int | None = None,
    engagements: int | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """metrics_24hシートに1行をupsertする(同一post_id+windowがあれば更新)。

    `source`は"manual_screenshot"(現行の暫定評価フェーズ)または"x_api"
    (将来のx-metrics-collector再有効化時)を想定。同じツールを両経路が呼ぶことで、
    intakeインターフェースを分けずに将来差し替え可能にする。
    `data_quality: manual`の既存行を manual以外で上書きしようとするとエラーになる
    (スクショ運用の値を保護する既存ルールをサーバー側に閉じ込めている)。
    """
    validation.validate_metrics_snapshot(data_quality, source)
    values = {
        k: v
        for k, v in {
            "impression_count": impression_count,
            "like_count": like_count,
            "reply_count": reply_count,
            "bookmark_count": bookmark_count,
            "user_profile_clicks": user_profile_clicks,
            "url_link_clicks": url_link_clicks,
            "engagements": engagements,
        }.items()
        if v is not None
    }
    snapshot_id = _get_client().record_metrics_snapshot(
        post_id, window, values, data_quality, source, notes
    )
    return {"snapshot_id": snapshot_id, "recorded": True}


@mcp.tool()
def count_same_condition_samples(mode: str, format: str, cta_type: str) -> dict[str, Any]:
    """同条件群(mode/format/cta_type一致)のうち、実測profile_visit_rateを持つ件数を返す。

    docs/strategy/kpi-definition.mdのCold-start mode(5件未満)/Relative benchmark mode
    (5件以上)の切り替え判定にそのまま使う。閾値の意味づけ自体は投稿OS側の判断のまま。
    """
    count = _get_client().count_same_condition_samples(mode, format, cta_type)
    return {"count": count, "mode_suggestion": "cold_start" if count < 5 else "relative_benchmark"}


@mcp.tool()
def render_daily_brief() -> str:
    """現在のSheets状態からMarkdownを生成し、ops/reports/daily_brief.mdへ書き出して返す。

    daily_brief.mdはこの関数の出力先(生成ビュー)。手編集の対象ではない。
    """
    markdown = render_daily_brief_markdown(_get_client())
    (_REPO_ROOT / "ops" / "reports" / "daily_brief.md").write_text(markdown, encoding="utf-8")
    return markdown


if __name__ == "__main__":
    mcp.run(transport="stdio")
