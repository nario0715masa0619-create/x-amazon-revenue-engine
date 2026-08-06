# logger（記録担当）

対応する subagent: [.claude/agents/logger.md](../../.claude/agents/logger.md)

## 責務

- 投稿ログ・施策ログ・数値ログの整合性を保つ
- `post_id` / `experiment_id` / `snapshot_id` を命名規則に従って発行する
- 投稿案がレビューに提出された時点で`post_id`を発行し、`draft`/`needs_revision`/`approved`等の状態遷移を同一IDのもとで一貫して記録する（承認済みのものだけを記録対象とするわけではない）
- ログの欠損・不整合を検知し警告する

## ID命名規則

- `post_id`: `p-YYYYMMDD-連番`（例: `p-20260802-001`）
- `experiment_id`: `e-YYYYMMDD-連番`（例: `e-20260802-001`）
- `snapshot_id`: `s-{post_id}-YYYYMMDDHHmm`（例: `s-p-20260802-001-202608091200`）

## 再提出ルール（needs_revision後）

`needs_revision` となった投稿案が修正・再提出される場合、新しい `post_id` は発行しない。同一 `post_id` のまま、修正後の内容を新しい行として追記する（既存行は上書きしない）。同一 `post_id` に複数行がある場合、最新の `created_at` を持つ行が現在のステータスを表し、過去の行は修正履歴として残る。詳細は [.claude/agents/logger.md](../../.claude/agents/logger.md) を参照。

## 競合比判定の記録（2026-08-06修正: 記録先バグを修正。schema変更なし）

集客モードの評価が「競合比で強いか」を中核とするようになったことに伴い、複数案を比較した際の採否理由を記録する。**`post_log.schema.json`に`notes`フィールドは存在しない（2026-08-06の機能監査で判明。`additionalProperties: false`のため実行不可能だった）ため、`post_log`には書かない。** 代わりに`ops/reports/daily_brief.md`の「投稿案の競合比較記録」欄に、フック/投稿全体の競合比評価、最強・最弱軸、採用/不採用理由、他候補との相互参照を記録する（`posted_url`等と同じく、schemaに格納場所がない情報を`daily_brief.md`で扱う既存パターンを踏襲）。詳細は [.claude/agents/logger.md](../../.claude/agents/logger.md) を参照。

## `posted`状態の暫定運用（Phase 1） — 人間の入力はURLのみ

`posted` = 人間がXへの投稿完了を確認した状態。**人間が入力するのは投稿URL1つだけ**（ユーザーオペレーション最小化の原則）。post_id・投稿時刻・投稿者はloggerが承認時点の情報とURL記入時刻から補う。投稿URLは`post_log.schema.json`に格納する場所がないため`ops/reports/daily_brief.md`の「実投稿記録」欄に記録する（schema変更なしの暫定運用。将来的な正本移行先の設計は[gsheets_ledger_design_2026-08-03.md](../../ops/reports/gsheets_ledger_design_2026-08-03.md)参照）。詳細は [.claude/agents/logger.md](../../.claude/agents/logger.md) を参照。

## 入力

- x-copywriterがレビューに提出した投稿案、およびaffiliate-compliance-reviewerの判定結果（承認結果によらない）
- growth-marketerからの施策情報
- 数値取得結果

## 出力

- `ops/logs/post_log.jsonl`、`ops/logs/experiment_log.jsonl`、`ops/logs/metrics_snapshots.csv` への追記
- ログ欠損・不整合のレポート

## 成功条件

- すべてのログエントリが `schemas/*.schema.json` に準拠している
- `approved_by` が空、または未承認のまま `status: approved` になっているエントリがない
- 同一投稿案に対する `post_id` の重複発行がない（再提出時は同一IDを維持している）

## 禁止事項

- スキーマ非準拠のログ記録
- 既存ログ行の無断上書き・削除
- 未承認投稿の `approved` 扱い

## 連携先

- x-copywriter / affiliate-compliance-reviewer / performance-analyst（ログ欠損時の差し戻し先）
- weekly-pdca-review skill（週次のログ棚卸し）
- x-metrics-collector（`posted`確定後、投稿URLを引き継ぎ24時間後メトリクス回収を依頼する。[x_metrics_semiauto_design_2026-08-03.md](../../ops/reports/x_metrics_semiauto_design_2026-08-03.md)参照）
