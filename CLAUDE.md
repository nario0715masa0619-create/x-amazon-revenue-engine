# CLAUDE.md — 全担当共通ルール

このファイルは、このリポジトリで作業するすべての担当（subagents）が従うべき最小限の実行ルールです。詳細な役割定義は `docs/roles/`、モード別の運用方針は `.claude/skills/` と `docs/playbooks/` を参照してください。ここには「必ず守るべきこと」だけを書きます。

## このプロジェクトについて

- X（旧Twitter）× Amazonアフィリエイト運用のための「運用OS」リポジトリである
- 運用モードは **集客（acquisition）／教育（education）／販売（sales）** の3つのみ
- 詳細: [docs/strategy/funnel-definition.md](docs/strategy/funnel-definition.md)

## 担当とモードを混同しない

- **担当（roles）** = 誰が作業するか。`.claude/agents/*.md` で定義される固定的な機能
- **モード（modes）** = 今何を目的に動いているか。`ops/state/current_mode.yaml` で管理される可変的な状態
- 担当はモードをまたいで動く。「今は販売モードだから x-copywriter は使わない」は誤り。「今は販売モードだから x-copywriter は sales-playbook に従う」が正しい

## 実行ルール（必須）

1. **販売モードの投稿案は、公開前に必ず `affiliate-compliance-reviewer` のレビューを通すこと。** 承認なしに販売モードの投稿を確定させてはならない。
2. **すべての施策・投稿には一意なID（`post_id` / `experiment_id`）を付与すること。** 命名規則は [docs/roles/logger.md](docs/roles/logger.md) に従う。
3. **ログ未記録の施策は、正式施策として扱わない。** `ops/logs/` に記録されるまで「実施済み」とみなさない。
4. **数値の改善・悪化は、週次レビュー（`weekly-pdca-review` skill）で `ops/reports/weekly_review.md` に反映すること。** 個別の気づきをその場限りにしない。
5. **誇大表現・誤認表現・開示漏れを禁止する。** 詳細: [docs/policies/disclosure-policy.md](docs/policies/disclosure-policy.md)、[docs/policies/amazon-affiliate-policy.md](docs/policies/amazon-affiliate-policy.md)
6. **本番投稿の自動化はまだ行わない。** 現段階は設計・雛形・記録基盤の整備を優先する。外部API接続やスケジュール投稿の実装は、明示的な指示があるまで着手しない。

## 参照先マップ

| 知りたいこと | 参照先 |
|---|---|
| 事業モデル・収益構造 | `docs/strategy/business-model.md` |
| モードの定義・切替の考え方 | `docs/strategy/funnel-definition.md` |
| KPI定義 | `docs/strategy/kpi-definition.md` |
| 各担当の責務 | `docs/roles/*.md` |
| X運用ルール | `docs/policies/x-posting-policy.md` |
| Amazonアフィリ注意点 | `docs/policies/amazon-affiliate-policy.md` |
| 開示ルール | `docs/policies/disclosure-policy.md` |
| モード別の実務手順 | `.claude/skills/*/SKILL.md`、`docs/playbooks/*.md` |
| ログの構造 | `schemas/*.schema.json` |
| 現在の運用状態 | `ops/state/*.yaml` |

## 迷ったときの優先順位

1. 安全（コンプラ・開示・アカウント健全性）
2. 記録の正確性（ログ・ID・追跡可能性）
3. 施策の効果（KPI改善）

速さのために 1 と 2 を犠牲にしない。
