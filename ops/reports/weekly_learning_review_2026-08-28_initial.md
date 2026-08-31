# 学習モード週次研究集計（source of truthから再計算: minimal_run_log/enrichment_record/post_analytics）

構造化データ: [weekly_learning_review_2026-08-28_initial.json](weekly_learning_review_2026-08-28_initial.json)
雛形: [weekly_learning_review_template_2026-08-28.md](weekly_learning_review_template_2026-08-28.md)

**この集計はops/reports/minimal_run_log_*.json / enrichment_record_*.json / post_analytics_*.json（実際に永続化されたsource of truthのみ）から再計算したものです。**shadow_mode_run_*.json由来のRun10〜12（研究資産としての再構成データ）は今回の集計対象に含めていません（本集計は`mainline_status=completed`のminimal_run_logのみを主対象とする、というsource of truth定義に従うため）。

対象期間: 2026-08-29 〜 2026-08-30（対象run: 7件）

## 1. 今週の本線運用状況

- 総run数: 7
- `mainline_status=completed`: 7件
- `closed_incomplete`: 0件
- `failed`: 0件

## 2. enrichment実行状況

- `completed`: 7件
- `partial`: 0件
- `failed_non_blocking`: 0件
- `not_started`: 0件

## 3. divergence発生状況

- `structure_hook_divergence=true`: 5件
- non-divergence: 2件

## 4. human vs structure/hook傾向

- split時にstructure側が的中: 1件
- split時にhook側が的中: 4件
- split時にどちらとも不一致: 0件

## 5. contamination / fallback / source variability

- Step A disclosure contamination: 0件
- fallback source使用率: 0%（0/7件）
- source別分布: {'2093229163213996215': 1, '2093563849580691551': 3, '2094056498305576981': 3}
- split発生5件のうち、structure側が的中1件、hook側が的中4件、どちらとも不一致0件
- fallback source使用率: 0%（0/7件）
- 実投稿済みrunのanalytics取得状況: 1件中 completed=0件・partial=1件（partialはX_USER_ACCESS_TOKEN未設定によるpublic_metricsのみ）

## 6. 次週の研究フォーカス

- Run14: divergence meta-gateのguarded live forward validation（新規source優先、研究専用の厳密プロトコルで）
- posted-theme exclusion guardを次回mainline runから実運用に組み込む
- 実投稿済みrunのanalytics追跡を継続（現時点でfetch_status=partial 1件、X_USER_ACCESS_TOKEN未設定のためnon-public指標は未取得）
- gadget teacher supplyの新規source開拓（同一source系列への依存緩和）

## 7. one_line_takeaway

実際に永続化されたminimal_run_log/enrichment_record（source of truth、7件）を再集計した。mainline_status=completedが7件、splitが5件（structure的中1件・hook的中4件）、non-divergenceが2件、contaminationが0件、fallback使用率0%。実投稿は1件のみでanalyticsはpartial（public_metricsのみ）取得済み。recommendation-only・人間レビュー前提の運用を継続する

## 対象run一覧（source of truthより）

| run_id | mainline_status | structure_hook_divergence | structure_vs_human_match | hook_vs_human_match | analytics |
|---|---|---|---|---|---|
| mainline-run-2026-08-29-001 | completed | True | False | True | fetch_status=partial |
| mainline-run-2026-08-29-002 | completed | True | True | False | — |
| mainline-run-2026-08-30-003 | completed | False | False | False | — |
| mainline-run-2026-08-30-004 | completed | True | False | True | — |
| mainline-run-2026-08-30-005 | completed | True | False | True | — |
| mainline-run-2026-08-30-006 | completed | False | False | False | — |
| mainline-run-2026-08-30-007 | completed | True | False | True | — |
