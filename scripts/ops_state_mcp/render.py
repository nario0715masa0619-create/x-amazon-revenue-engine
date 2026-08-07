"""daily_brief.md相当のMarkdownを、Google Sheets(正本)の現在状態から生成する。

daily_brief.mdは2026-08-07以降、手編集の対象ではなく本モジュールの出力先(生成ビュー)。
テンプレートの見出し構成はops/reports/daily_brief.md(旧版)を踏襲しているが、
内容は都度Sheetsから再構成する(手で足していく方式はやめる)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from x_metrics_collector.sheets_client import SheetsClient


def _latest_posts(posts: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    return sorted(posts, key=lambda p: str(p.get("created_at", "")), reverse=True)[:limit]


def render_daily_brief_markdown(client: "SheetsClient") -> str:
    posts = client.get_posts()
    metrics = client.get_metrics_24h_rows()
    metrics_by_post: dict[str, list[dict[str, Any]]] = {}
    for m in metrics:
        metrics_by_post.setdefault(str(m.get("post_id")), []).append(m)

    lines: list[str] = []
    lines.append("# daily_brief.md — 生成ビュー(ops-state MCP `render_daily_brief`が出力。手編集しない)")
    lines.append("")
    lines.append(
        "> **2026-08-07以降、このファイルは正本ではありません。** "
        "正本はGoogle Sheetsの`posts`/`reviews`/`metrics_24h`です"
        "（`ops-state` MCPサーバー経由でのみ読み書きする）。"
        "このファイルは`render_daily_brief`ツール呼び出し時点のスナップショットとして"
        "都度上書き生成されます。手で編集しても次回の生成で失われます。"
    )
    lines.append("")

    lines.append("## 直近の投稿案（最大10件、created_at降順）")
    lines.append("")
    lines.append("| post_id | mode | format | cta_type | review_status | approved_by |")
    lines.append("|---|---|---|---|---|---|")
    for p in _latest_posts(posts):
        lines.append(
            f"| {p.get('post_id','')} | {p.get('mode','')} | {p.get('format','')} | "
            f"{p.get('cta_type','')} | {p.get('review_status','')} | {p.get('approved_by','')} |"
        )
    if not posts:
        lines.append("| （該当なし） | | | | | |")
    lines.append("")

    lines.append("## 投稿ごとの最新review結果")
    lines.append("")
    lines.append("| post_id | reviewer | action | hook_assessment | cta_fit_assessment | confidence |")
    lines.append("|---|---|---|---|---|---|")
    for p in _latest_posts(posts):
        post_id = str(p.get("post_id"))
        for r in client.get_reviews(post_id):
            lines.append(
                f"| {post_id} | {r.get('reviewer','')} | {r.get('action','')} | "
                f"{r.get('hook_assessment','')} | {r.get('cta_fit_assessment','')} | {r.get('confidence','')} |"
            )
    lines.append("")

    lines.append("## 24時間後実績（metrics_24h、直近分）")
    lines.append("")
    lines.append("| post_id | window | impression_count | profile_visit_rate | data_quality | source | notes |")
    lines.append("|---|---|---|---|---|---|---|")
    for post_id, rows in metrics_by_post.items():
        for m in rows:
            lines.append(
                f"| {post_id} | {m.get('check_window','')} | {m.get('impression_count','')} | "
                f"{m.get('profile_visit_rate','')} | {m.get('data_quality','')} | "
                f"{m.get('source','')} | {m.get('notes','')} |"
            )
    if not metrics:
        lines.append("| （該当なし） | | | | | | |")
    lines.append("")

    return "\n".join(lines) + "\n"
