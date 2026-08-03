# x-amazon-revenue-engine

X（旧Twitter）× Amazonアフィリエイト運用を、Claude Code上で複数担当（subagents）に分業させながら回すための「運用OS」リポジトリです。

このリポジトリ自体が運用マニュアルであり、実行環境でもあります（repository-as-operating-system）。GitHubを正本とし、ルール・役割・ログのすべてをここに集約します。

## 1. 目的

- X上での発信を通じて Amazon アフィリエイトの成果（クリック・コンバージョン・報酬）を継続的に伸ばす
- 「集客 → 教育 → 販売」という運用モデルに沿って投稿を設計する
- 施策・投稿・数値をすべてログとして残し、PDCA（Plan-Do-Check-Act）が機械的に回る状態を作る
- 誇大表現・誤認表現・開示漏れのない、健全なアカウント運用を維持する

このリポジトリはまず「設計・雛形・記録基盤」を整えるための初版です。本番投稿の自動化や外部API接続はまだ行いません。

## 2. 全体アーキテクチャ

```
              ┌─────────────────────┐
              │  mode-orchestrator   │  ← 司令塔（現在モードを判定し、担当へタスクを振る）
              └──────────┬───────────┘
                         │
      ┌──────────┬────────┴────────┬──────────────┬─────────────┐
      ▼          ▼                 ▼              ▼             ▼
 x-researcher  growth-marketer  x-copywriter  compliance-reviewer  performance-analyst
  (調査)         (戦略設計)        (文案作成)      (レビュー)          (成果分析)
                                                                       │
                                                                       ▼
                                                                    logger
                                                              (ログ整合性の維持)
```

担当（agents）はモードをまたいで横断的に動き、モード（skills / state）は「今どの目的で動くか」を切り替えるレイヤーです。両者は独立した軸として設計されています。

x-copywriterとcompliance-reviewerの間には、`pre-post-self-check` skillとmarket-grounded review layer（`trend-reality-reviewer`/`competitor-reality-reviewer`/`audience-market-fit-reviewer`）という2つの前段品質改善レイヤーがあります。いずれもcompliance-reviewerの最終判断を代替しません（詳細は`.claude/agents/`参照）。

さらにその手前、mode-orchestratorが動き出す前には、毎朝「今日何を狙うか」を決める`morning-strategy-council` skillがあります。**朝会＝戦略決定、execution layer（researcher以降）＝実務**という二層構造で、朝会は投稿文そのものを議論せず、人間が方針を1つ採択してからexecution layerに引き継ぎます（詳細は`.claude/skills/morning-strategy-council/SKILL.md`参照）。

**ユーザーは運用担当者ではなく最終承認者として扱います。** Phase 1では、人間の作業は「当日方針を1つ選ぶ→最終投稿案を1つ承認する→実投稿する→投稿URLを1回記録する」の4手に収める設計です（詳細は`ops/reports/phase1_acquisition_launch_spec_2026-08-03.md`、将来のGoogle Sheets移行設計は`ops/reports/gsheets_ledger_design_2026-08-03.md`参照）。

## 3. 「担当」と「モード」の違い

| | 担当（Roles） | モード（Modes） |
|---|---|---|
| 実体 | `.claude/agents/*.md`（subagents） | `.claude/skills/*/SKILL.md` + `ops/state/*.yaml` |
| 意味 | 誰が作業するか（機能・役割） | 今何を目的に動いているか（集客/教育/販売） |
| 変化頻度 | ほぼ固定 | 日次〜週次で変わる |
| 例え | 部署・職能 | 今期の重点方針 |

たとえば `x-copywriter`（担当）は、集客モードでも教育モードでも販売モードでも文案を書きますが、**どう書くか**は現在のモード（`ops/state/current_mode.yaml`）と対応する playbook skill によって変わります。担当とモードを混同しないことが、このリポジトリ運用の大前提です。

## 4. ログとPDCAの考え方

- すべての投稿・施策には一意な ID（`post_id` / `experiment_id`）を付与する
- ログは人間向けMarkdownではなく、**機械可読なJSONL/CSV**（`ops/logs/`）に記録する
- ログに記録されていない施策は、正式な施策として扱わない（＝「やったことにしない」）
- `performance-analyst` が数値ログを分析し、`weekly-pdca-review` skill が週次で勝ち筋・負け筋を抽出する
- 抽出された学びは `ops/reports/weekly_review.md`、`ops/state/mode_weights.yaml`、必要に応じて `docs/playbooks/*.md` に反映される

PDCAのループ：

```
Plan  : docs/playbooks + growth-marketer が仮説を立てる
Do    : x-copywriter が文案化 → compliance-reviewer がレビュー → 投稿 → logger がログ化
Check : performance-analyst が metrics_snapshot を分析
Act   : weekly-pdca-review skill が mode_weights / playbook / state を更新
```

## 5. ディレクトリ構成

```
.
├─ README.md                 このファイル
├─ CLAUDE.md                 全担当共通の実行ルール（憲法）
├─ .claude/
│  ├─ agents/                担当（subagents）定義
│  └─ skills/                モード別プレイブック・週次レビューskill
├─ docs/
│  ├─ strategy/              事業モデル・ファネル定義・KPI定義（正本ドキュメント）
│  ├─ roles/                 各担当の責務・入出力・成功条件
│  ├─ policies/               X運用ポリシー・Amazonアフィリポリシー・開示ポリシー
│  └─ playbooks/              モード別の人間向け解説
├─ schemas/                   ログの構造定義（JSON Schema）
├─ ops/
│  ├─ state/                  現在モード・モード比率などの実行時状態
│  ├─ logs/                    投稿ログ・施策ログ・数値ログ（機械可読）
│  └─ reports/                 日次ブリーフ・週次レビューの出力先
└─ templates/                  投稿・レビュー・週報のテンプレート
```

## 6. セットアップの最初の手順

1. このリポジトリをクローンし、Claude Code で開く
2. `CLAUDE.md` と `docs/strategy/*.md` を読み、事業モデルとモード定義を理解する
3. `ops/state/current_mode.yaml` で現在モードを確認する（初期値: `acquisition`）
4. `.claude/agents/mode-orchestrator.md` を起点に、担当への指示出しフローを確認する
5. 最初の投稿案を作る場合は `templates/x_post_template.md` を使い、`x-copywriter` → `affiliate-compliance-reviewer` の順でレビューを通す
6. 投稿・施策が発生したら、必ず `logger` を経由して `ops/logs/` にIDを記録する

## 7. 今後の拡張ポイント

- 投稿・数値取得の自動化（X API / Amazon PA-API 連携）
- `ops/logs/*.jsonl` を集計するダッシュボード（BIツールまたは簡易スクリプト）
- モード切替の自動判定ロジック（現在は `mode-orchestrator` が手動判定）
- 商品データベース（`products/` の追加）とレコメンドロジック
- 複数アカウント運用時のスコープ分離（アカウント単位のstate管理）

まずは自動化前提を作らず、人間の意思決定を支援する記録基盤として育てていきます。
