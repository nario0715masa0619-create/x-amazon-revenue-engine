# mcp_architecture_2026-08-07.md — MCP前提アーキテクチャ（Phase 1実装済み）

> 投稿OS（morning-strategy-council / execution / market-grounded review / pre-post-self-check / affiliate-compliance-reviewer）の判断ロジックは不可侵。この設計は「何を出すか」ではなく「どこに書くか・どう読むか」のI/O一本化のみを対象とする。

## 目的

投稿1本の最適化ではなく、PDCA自動化の簡素化。手作業の転記・二重記録・ファイル間の不自然な橋渡し（`post_log.jsonl`のnotes不存在バグ、`metrics_snapshot`のdata_quality不存在バグ等、2026-08-06に発覚した一連の不整合）を、配線側の再設計で構造的に防ぐ。

## 複雑さの発生源（本質的 vs 配線由来）

- **本質的複雑さ**（MCP化しても消えない）: 性質の異なる4種のデータ（戦略判断・投稿ワークフロー状態・数値実績・競合比較の理由）、多段ゲート付きパイプライン、`data_quality`の出所追跡、Cold-start/Relative benchmark modeの二段階、人間ゲート（A/B/C/D）
- **配線由来の複雑さ**（今回のPhase 1で解消対象）: schema/docsの乖離バグ、記録先の後付け発明、スクショ⇄構造化データの手転記、`ops/logs/*`とGoogle Sheetsという2つの正本候補の並存、`daily_brief.md`の単一スナップショット問題、write前の手動schema検証

## アーキテクチャ概要

```
投稿OS（judgment layer、変更なし）
  │  読み書きはツール呼び出しのみ
  ▼
MCP: ops-state（新規・最小構築、scripts/ops_state_mcp/）
  │  実体は scripts/x_metrics_collector/sheets_client.py の SheetsClient を拡張再利用
  ▼
Google Sheets（既存スプレッドシート）— posts / reviews / metrics_24h

MCP: Context7（既存・変更なし）— 技術docs専用、投稿OSには非接続
```

必要なMCPサーバーは最小2本（Context7は既存）。orchestrator専用のMCPサーバーは作らない（オーケストレーションは判断ロジックの一部であり、I/Oではないため）。

## 正本データ設計

**正本 = Google Sheetsの`posts`/`reviews`/`metrics_24h`**（`ops-state` MCP経由でのみ読み書き）。`daily_brief.md`・`post_log.jsonl`・`metrics_snapshots.csv`のいずれも正本ではない。

- `posts`: 1投稿1レコード、`created_at`を持つ（列構成は[gsheets_ledger_design_2026-08-03.md](gsheets_ledger_design_2026-08-03.md)を踏襲。`status`は列名`review_status`）
- `reviews`（今回新規追加）: reviewerごとの判定を正規化。`axis_scores`はセル内JSON文字列として保持
- `metrics_24h`: 既存列＋`source`列（`manual_screenshot` / `x_api`）を新規追加。同一`record_metrics_snapshot`ツールを両経路が呼ぶことで、将来のX API再導入時もインターフェースを変えずに済む
- `data_quality: manual`行の不用意な上書き防止など、既存`sheets_client.py`のビジネスルールは`ops-state`サーバー側（`SheetsClient`の新規メソッド）に閉じ込める

## 段階移行

- **Phase 1（実装済み）**: `ops-state` MCPサーバー新規追加。`get_post`/`list_posts`/`record_post_draft`/`set_post_status`/`get_reviews`/`record_review_result`/`record_metrics_snapshot`/`count_same_condition_samples`/`render_daily_brief`を公開。`ops/logs/post_log.jsonl`・`ops/logs/metrics_snapshots.csv`は凍結（read-only archive化）。`daily_brief.md`は`render_daily_brief()`の生成ビューへ降格
- **Phase 2（未着手）**: スクショ由来の実測値記録を`record_metrics_snapshot(..., source="manual_screenshot")`経由に切り替え。growth-strategist/performance-analystの同条件群サンプル数の把握を`count_same_condition_samples`経由に
- **Phase 3（未着手・将来）**: X API再導入時、`scripts/x_metrics_collector`のX API部分（`x_api_client.py`/`tweet_id.py`）はそのまま温存し、取得後の書き込み先を独自の`upsert_metrics_row`直接呼び出しから`record_metrics_snapshot(..., source="x_api")`呼び出しへ差し替えるだけにする

## 残る非MCP領域

朝会5役・reviewerの独立性問題、market-grounded reviewerが実際にWebSearchを呼ぶかどうか、投稿文そのものの質、人間承認の負荷、Cold-start modeの母数不足、Google/service account初回認証設定——いずれもI/Oの配線とは無関係であり、今回の変更では一切改善しない。

## 詳細

実装の詳細（ツール一覧・Sheets列設計・セットアップ手順）は[scripts/ops_state_mcp/README.md](../../scripts/ops_state_mcp/README.md)を参照。
