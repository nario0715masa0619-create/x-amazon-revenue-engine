# ops-state MCPサーバー（Phase 1・最小構成）

投稿OS（morning-strategy-council / execution / market-grounded review / pre-post-self-check / affiliate-compliance-reviewer）の**判断ロジックには関与しない**。posts/reviews/metrics_24h（Google Sheets、正本）の読み書きを型付きツールとして公開する、I/O一本化レイヤーのみ。

設計の背景は [ops/reports/mcp_architecture_2026-08-07.md](../../ops/reports/mcp_architecture_2026-08-07.md)（設計案。未作成の場合はセッション内の合意事項を参照）、シート設計は [ops/reports/gsheets_ledger_design_2026-08-03.md](../../ops/reports/gsheets_ledger_design_2026-08-03.md) を参照。

## 前提

`scripts/x_metrics_collector/` が既に実装・検証済みであることが前提。このサーバーは同パッケージの `SheetsClient` をそのまま再利用する（新規実装は薄いMCPラッパーとreviews/posts書き込みメソッドの追加のみ）。

## セットアップ

1. 依存関係のインストール:
   ```bash
   python -m pip install -r scripts/requirements.txt
   ```
2. 認証情報は `scripts/x_metrics_collector/README.md` の手順と同じ `.env` を使う（`GOOGLE_SHEETS_SPREADSHEET_ID` / `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` または `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`）。このサーバー専用の追加設定は不要。
3. Google Sheetsの対象スプレッドシートに **`reviews`シート**を追加する（`posts`/`metrics_24h`は既存。`reviews`は今回新規追加。列名は下記「Sheets設計」参照）
4. `metrics_24h`シートに **`source`列**（`manual_screenshot` / `x_api`）を追加する（既存の `gsheets_ledger_design_2026-08-03.md` 設計に対する2026-08-07の小拡張）

## 起動

`.mcp.json`（リポジトリルート、project-scope）に登録済み:

```json
{
  "mcpServers": {
    "ops-state": {
      "command": "python",
      "args": ["-m", "scripts.ops_state_mcp.server"]
    }
  }
}
```

Claude Codeが新しいセッションを開始した時点で自動的に起動される（`.mcp.json`の変更はセッション開始時に読み込まれる）。手動起動する場合はリポジトリルートで:

```bash
python -m scripts.ops_state_mcp.server
```

認証情報が未設定でもサーバー自体は起動し、ツール一覧も確認できる（`SheetsClient`への接続は最初のツール呼び出し時まで遅延される）。実際にpost/review/metricsを読み書きするツール呼び出し時に、未設定なら`GOOGLE_SHEETS_SPREADSHEET_ID が未設定です`等のエラーが返る。

## 公開ツール

| ツール | 用途 |
|---|---|
| `get_post(post_id)` | postsシートから1件取得 |
| `list_posts(mode, format, cta_type, status)` | postsシートを条件絞り込みして取得 |
| `record_post_draft(post_id, mode, format, cta_type, angle, draft_text, ...)` | 新規投稿案をpostsシートに記録（post_id重複はエラー） |
| `set_post_status(post_id, status, approved_by, notes)` | postsシートのreview_status等を更新 |
| `get_reviews(post_id)` | reviewsシートを該当post_idで絞り込み取得 |
| `record_review_result(post_id, reviewer, action, hook_assessment, whole_post_assessment, axis_scores, cta_fit_assessment, rationale, confidence, notes)` | market-grounded review / self-check / complianceの判定結果を記録 |
| `record_metrics_snapshot(post_id, window, data_quality, source, impression_count, ...)` | metrics_24hへupsert。`data_quality: manual`行を`manual`以外で上書きすることはできない |
| `count_same_condition_samples(mode, format, cta_type)` | 同条件群の実測サンプル数を返す（Cold-start/Relative benchmark modeの判定材料） |
| `render_daily_brief()` | 現在の状態から`ops/reports/daily_brief.md`を再生成する |

## Sheets設計（正本）

### `posts`（既存＋`review_status`は`status`のSheets上の列名）
`gsheets_ledger_design_2026-08-03.md`の列構成をそのまま使用。

### `reviews`（今回新規追加）

| 列名 | 内容 |
|---|---|
| review_id | `rv-{post_id}-{連番}`（AI自動発番） |
| post_id | 対象投稿 |
| reviewer | 例: `trend-reality-reviewer` |
| reviewed_at | ISO8601 |
| hook_assessment / whole_post_assessment / cta_fit_assessment | `強い`/`同等`/`弱い` |
| axis_scores | 5軸のJSON文字列（例: `{"停止力":"強い",...}`） |
| action | `keep`/`revise`/`hold` |
| rationale | 判定理由 |
| confidence | `high`/`medium`/`low` |
| notes | 自由記述 |

`decision`/`reason_tags`/`reason_note`/`revision_instruction`（旧設計の列）が既にシートにあれば残してよい（このサーバーは使わないが壊さない）。

### `metrics_24h`（既存＋`source`列を新規追加）

既存列に加え、`source`（`manual_screenshot` / `x_api`）を追加。同じ`record_metrics_snapshot`ツールを両経路が呼ぶことで、将来X APIへ切り替える際もインターフェースを変えずに済む。

## 既知の制約（Phase 1時点）

- `reviews`シートの列を実際にスプレッドシート側へ追加する作業は、シートの実オーナー（このリポジトリの外側）が行う必要がある。このパッケージはコードのみで、シートのUI操作は行わない
- 実際のGoogle Sheets接続を伴う疎通確認は、実認証情報を持つ環境でのみ可能（このリポジトリのAI側では実施していない。検証済みなのはモック環境での業務ロジックとバリデーションのみ）
