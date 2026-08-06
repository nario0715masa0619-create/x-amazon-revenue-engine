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
7. **ユーザーは運用担当者ではなく最終承認者として扱うこと。** 日々の記録・整理・下書き作成はAI側に寄せ、人間に同じ情報を二度入力させない、ゼロから考えさせない設計を優先する。詳細: [ops/reports/phase1_acquisition_launch_spec_2026-08-03.md](ops/reports/phase1_acquisition_launch_spec_2026-08-03.md)の「最小オペレーション標準フロー」
8. **Context7（`.mcp.json`で導入。2026-08-06追加）は「技術docs専用インフラ」であり、投稿文生成の品質改善ツールではない。** 使ってよいのは、ライブラリ／API／SDK／MCP／設定・実装・移行など**技術実装の検証**が必要なときのみ（例: Google Sheets/Google API/service accountの仕様確認、MCP・subagent連携の設定確認、X API等の外部APIの公式仕様確認）。**朝会（morning-strategy-council）・投稿文生成（x-copywriter）・market-grounded review layer・pre-post-self-check・CTA別強さ判定など、コピー品質・戦略判断・競合比較には一切使わない。** 不要なときは呼ばない。これらのskill/agentファイル自体への機能追加は行っていない（責務は変更なし）。

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
| 毎朝の戦略決定（朝会＝戦略、execution layer＝実務） | `.claude/skills/morning-strategy-council/SKILL.md` |
| ログの構造 | `schemas/*.schema.json` |
| 現在の運用状態 | `ops/state/*.yaml` |
| 技術docs検索（Context7）の設定・使用範囲 | `.mcp.json`（設定）／このファイルの実行ルール8 |

## 迷ったときの優先順位

1. 安全（コンプラ・開示・アカウント健全性）
2. 記録の正確性（ログ・ID・追跡可能性）
3. 施策の効果（KPI改善）

速さのために 1 と 2 を犠牲にしない。
