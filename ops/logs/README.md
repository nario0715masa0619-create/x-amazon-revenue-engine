# ops/logs/ — 2026-08-07以降、read-only archive

**`post_log.jsonl`・`metrics_snapshots.csv`は2026-08-07付けで凍結しました。新規の追記は行いません。**

正本は Google Sheets の `posts` / `reviews` / `metrics_24h` に移行しました（`ops-state` MCPサーバー経由でのみ読み書き）。詳細は [ops/reports/mcp_architecture_2026-08-07.md](../reports/mcp_architecture_2026-08-07.md) を参照。

- `post_log.jsonl`: 2026-08-02〜2026-08-06に記録した実データ（サンプル行・Day3候補棄却・案A/B/C/D）をそのまま過去アーカイブとして保持します。削除しません
- `metrics_snapshots.csv`: サンプル行のみ（実データは元々記録されていません）。同様に凍結・保持します
- `experiment_log.jsonl`: 今回のPhase 1では未使用のまま凍結対象に含めます（`reviews`シートへの統合は将来検討）
- `schemas/post_log.schema.json` 等は廃棄しません。ローカルファイル検証用の役割から、`ops-state` MCPツール（`record_post_draft`等）の入力契約としての役割に転用されています（[scripts/ops_state_mcp/validation.py](../../scripts/ops_state_mcp/validation.py)参照）

新しい投稿・レビュー・実測記録は、すべて`ops-state` MCPサーバーのツール（`record_post_draft`/`record_review_result`/`record_metrics_snapshot`等）経由でGoogle Sheetsへ記録してください。このディレクトリのファイルへ直接追記しないでください。
