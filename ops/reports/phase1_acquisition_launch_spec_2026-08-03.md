# phase1_acquisition_launch_spec_2026-08-03.md — Phase 1 集客モード本番運用仕様書

> このドキュメントは、集客（acquisition）モードのみを対象とした本番運用（Phase 1）の仕様書。教育・販売モードの本番投入は対象外。3本のdry run（[acquisition](dryrun_2026-08-02_fashion-gadget_acquisition.md)/[education](dryrun_2026-08-02_fashion-gadget_education.md)/[sales](dryrun_2026-08-02_fashion-gadget_sales.md)）と[横断レビュー](cross_mode_review_2026-08-02.md)、[次フェーズ整合レビュー](next_phase_alignment_review_2026-08-03.md)を前提とする。hooks実装・schema変更・外部API連携は今回対象外。

---

## 1. Phase 1 の範囲と自律境界

### 対象

- モード: **acquisition（集客）のみ**。教育・販売は対象外（`ops/state/current_mode.yaml`は引き続き`acquisition`）
- カテゴリ: **40代ファッション×ガジェット**（2026-08-03確定。以下「アカウント設計」参照）
- 目的: X運用の実開始。フォロワー基盤・エンゲージメント基盤の構築が目的であり、売上・コンバージョンはPhase 1のスコープ外

### アカウント設計（2026-08-03確定）

- 主対象: 40代男女
- 重視する価値: 清潔感／上質感／実用性／無理のなさ／生活感を減らすこと
- 避ける表現: 若作り訴求／テンション高めの煽り／安さ一辺倒／若年層向け流行語の多用

以降のresearcher/marketer/copywriter/compliance-reviewerの各判断は、このアカウント設計を前提とする。

### Claude Codeが自律で行う範囲

- 投稿候補生成（x-researcher → growth-marketer → x-copywriter、`templates/x_post_template.md`準拠で毎回2案）
- レビュー（affiliate-compliance-reviewer、`templates/review_template.md`準拠。needs_revision時は同一post_id維持で再提出→再レビューの閉ループ実施）
- ログ候補作成（logger、`ops/logs/post_log.jsonl`へのレビュー提出時点からの状態遷移記録）
- 簡易振り返り（performance-analyst、日次の軽い振り返りと週次のまとめ）

### 人間が行う範囲（Claude Codeは行わない） — 4手（A〜D）に集約

- **A. 当日方針の採択**: Morning Strategy BriefのTL;DRと候補から1つ選ぶ
- **B. 最終承認**: `approved`となった案の中から実際に投稿する1案を選ぶ
- **C. 実投稿**: X上への実際の投稿操作
- **D. 投稿URLの記録**: `daily_brief.md`の「実投稿記録」欄にURLを貼るだけ（`status: posted`への更新はloggerが自動で行う。post_id・投稿時刻・投稿者の入力は不要）
- （例外）24時間後の実績数値の取得（**半自動化を設計済み**。x-metrics-collectorがX APIから取得を試み、取得できなかった項目のみ人間が補う。詳細は[x_metrics_semiauto_design_2026-08-03.md](x_metrics_semiauto_design_2026-08-03.md)。手順は[5.](#5-最小オペレーション標準フロー)を参照）

### 明示的にやらないこと

- 実際のX投稿API連携（自動投稿）
- hooks実装、schema変更
- 教育・販売モードの本番投入
- mode_weights.yamlの変更（Phase 1では`acquisition`固定運用のため対象外。変更は`weekly-pdca-review`経由のみという既存ルールを維持）

---

## 2. 投稿テーマの初期レンジ（3テーマ）

1本目の集客dry runでresearcherが整理した5サブテーマのうち、集客モードに最も適した（比較・断定を避けやすく、あるある共感・興味喚起を作りやすい）3つに絞る。

| テーマID | テーマ名 | 内容 |
|---|---|---|
| T1 | 見た目を損ねない実用品 | ケーブル・モバイルバッテリー等、デザイン性のあるガジェット周りの小物 |
| T2 | 暑さ対策・快適性向上 | 涼しさとおしゃれの両立（携帯扇風機・ネッククーラー等） |
| T3 | 通勤/通学で映える便利系 | ガジェット収納・バッグ内の持ち歩き方 |

ミニマル系・身につけるガジェット（スマートリング等）の2サブテーマは、Phase 1では扱わない（比較要素が強く教育モード向きのため、次フェーズで検討）。

---

## 3. KPI定義（主・副）

| 区分 | 指標 | 定義 | 備考 |
|---|---|---|---|
| 主KPI | `impressions` | 表示回数 | `ops/logs/metrics_snapshots.csv` |
| 主KPI | `profile_visit_rate` | `profile_visits / impressions` | [kpi-definition.md](../../docs/strategy/kpi-definition.md)の定義に準拠 |
| 副KPI | `follow_rate` | `フォロー数 / profile_visits` | Phase 1ではアカウント全体のフォロワー純増数を参考値として`daily_brief.md`に記録する（投稿起因かどうかの厳密な切り分けは行わない）。`metrics_snapshot.schema.json`にフォロー数を格納するフィールドがないため、`follow_rate`の厳密な算出は次フェーズのschema拡張後に持ち越す |

**初週の目標は数値目標の達成ではなく、ベースライン（基準値）の確立とする。** 過去の実運用実績が存在しないため、5投稿分のKPI実績を「初期基準値」として記録し、Phase 2以降の比較対象とする。

---

## 4. 1週間スプリント計画

初週は1日1本・合計5本（平日5日想定、Day1〜Day5）。同一テーマの連投を避けるため、以下のローテーションとする（[x-posting-policy.md](../../docs/policies/x-posting-policy.md)の「同一トピックの連投を避け、話題の幅を広げる」に準拠）。

| Day | 日付（例） | テーマ | フォーマット |
|---|---|---|---|
| Day1 | 2026-08-03（月） | T1: 見た目を損ねない実用品 | `single_post` |
| Day2 | 2026-08-04（火） | T2: 暑さ対策・快適性向上 | `single_post` |
| Day3 | 2026-08-05（水） | T3: 通勤/通学で映える便利系 | `single_post` |
| Day4 | 2026-08-06（木） | T1: 見た目を損ねない実用品（別角度） | `single_post` |
| Day5 | 2026-08-07（金） | T2: 暑さ対策・快適性向上（別角度） | `single_post` |

- フォーマットは初週`single_post`に統一する（`thread`はオペレーションが安定してから導入）
- 日付は例。実際の開始日に合わせてスライドしてよい
- 週次振り返りは全5投稿の24時間後スナップショットが揃うDay8（例: 2026-08-10 月）を目安に実施する

---

## 5. 最小オペレーション標準フロー

**ユーザーオペレーション最小化の原則**: 人間は運用担当者ではなく最終承認者として扱う。Phase 1の人間の作業は、原則として以下の**4手**に収める。

| # | 人間がすること | かかる手間 |
|---|---|---|
| A | Morning Strategy Brief（`.claude/skills/morning-strategy-council/SKILL.md`）を見て、当日方針を1つ選ぶ | TL;DR＋候補2〜3個から1つ選ぶだけ |
| B | 最終投稿案（`approved`）を1つ承認する | 最終文面を見て1つ選ぶだけ |
| C | Xへ実投稿する | 通常の投稿操作 |
| D | 投稿URLを1回記録する（`ops/reports/daily_brief.md`の「実投稿記録」欄） | URLを貼るだけ。post_id・投稿時刻・投稿者はAIが補う |

翌日の24時間後実績のみ例外で、人間は取得できた数値（最大5項目）を空欄のまま埋めるだけでよく、取得できない項目は空欄で放置してよい（「未取得」と書き添える必要はない）。**半自動化の設計は完了しており**（[x_metrics_semiauto_design_2026-08-03.md](x_metrics_semiauto_design_2026-08-03.md)）、x-metrics-collectorがX APIから取得を試みたうえで、取得できなかった項目だけ人間に確認を求める形に置き換えられる。ただし24時間後の自動起動機構（スケジューラ/hooks）は未実装のため、実運用は当面「人間または将来のジョブが取得処理を起動する」前提で回す。

### 5-1. AI側の内部フロー（参考。人間はこの詳細を読む必要はない）

1. **morning-strategy-council**（trend-analyst/competitor-analyst/audience-representative/growth-strategist/risk-compliance-observer → council-chair）: 前日実績・スプリント計画・アカウント設計をもとにMorning Strategy Briefを作成 → **人間がAで採択**
2. **mode-orchestrator**: 採択方針をその日限りの前提条件として引き継ぐ
3. **x-researcher → growth-marketer → x-copywriter**: 採択方針に沿って投稿案を**2案**作成（`templates/x_post_template.md`準拠）
4. **market-grounded review layer → x-copywriter（必要なら1回だけ修正）→ pre-post-self-check**: reviewer提出前の品質改善
5. **affiliate-compliance-reviewer**: 2案をレビュー
   - `needs_revision`の場合: x-copywriterが同一post_id維持で修正版を再提出 → 再レビュー
   - **当日中に`approved`が1本も出ない場合**: mode-orchestratorがスキップ案を`daily_brief.md`の「スキップ/持ち越し記録」欄に下書きする。人間は確認するだけでよい（Phase 1では投稿本数より運用安定を優先する）
6. **logger**: レビュー提出時点で`post_id`を発行し、状態遷移を`ops/logs/post_log.jsonl`に記録。`approved`が確定したら、`daily_brief.md`の「実投稿記録」欄にpost_idの行をあらかじめ用意しておく → **人間がBで承認、Cで投稿、Dで投稿URLのみ記入**
7. **logger**: 投稿URLの記入を受け、post_id・投稿時刻・投稿者を補って`status: posted`を記録する。投稿されなかった側の案は`archived`への変更をloggerが提案し、人間は追認するだけでよい
8. **x-metrics-collector**（最小実装あり。[scripts/x_metrics_collector/](../../scripts/x_metrics_collector/)、手動実行）: 投稿URLからtweet_idを解決し、X APIから取得を試みる。取得できた項目は`metrics_24h`（Google Sheets）に記録し、取得できなかった項目・認証未設定等は理由付きで残す
9. **人間（例外時のみ）**: x-metrics-collectorが取得できなかった数値のみ`daily_brief.md`に記入（空欄＝未取得）
10. **logger → performance-analyst**: 記録されたスナップショットをもとに、前日投稿1件分の簡易振り返りを`daily_brief.md`に追記

将来のGoogle Sheets／DB移行設計は[gsheets_ledger_design_2026-08-03.md](gsheets_ledger_design_2026-08-03.md)を参照（未実装、設計のみ）。

---

## 6. 週次振り返りの標準フロー

対象: 初週5投稿すべての24時間後スナップショットが揃った時点（Day8目安）。

1. **performance-analyst**: 5投稿分の`post_log`と`metrics_snapshots`を突き合わせ、テーマ別（T1/T2/T3）・フックタイプ別に`impressions`/`profile_visit_rate`を比較する。勝ち筋・負け筋仮説を抽出する（サンプル数5件は少数のため、「参考値」である旨を明記する）
2. **weekly-pdca-review skill**: `templates/weekly_report_template.md`に沿って`ops/reports/weekly_review.md`を更新する
   - `mode_weights.yaml`の変更: Phase 1は`acquisition`固定運用のため、通常は「不要」判断となる想定
   - `docs/playbooks/acquisition.md` / `.claude/skills/acquisition-playbook/SKILL.md`の更新要否を検討する（初期基準値と大きく異なる傾向が出た場合のみ）
3. **人間**: 週次レビュー結果を確認し、Phase 2（投稿頻度の拡大、教育モードの追加検討等）に進むかどうかを判断する

---

## 7. 本番開始前に埋めるべき不足前提条件

### 今回のラウンドで解決した項目

以下3点は、最小運用ルールを定義することで解決済み（詳細は5節の日次フローと`ops/reports/daily_brief.md`を参照）。

- **`posted`状態の暫定運用**: `posted` = 人間がXへの投稿完了を確認した状態と定義し、投稿URL・投稿時刻・投稿者は`daily_brief.md`の「実投稿記録」欄に記録する運用とした（[.claude/agents/logger.md](../../.claude/agents/logger.md)参照）
- **24時間後実績の手動取得手順**: 最小取得項目（`impressions`/`likes`/`replies`/`profile_visits`/フォロワー純増数）を定義し、記録先（`metrics_snapshots.csv`が正、`daily_brief.md`が入力窓口）を分離した
- **needs_revisionが当日中に解消しない場合のフォールバック**: 当日スキップ可、スキップ理由と翌日の扱いを`daily_brief.md`に記録する運用とした
- **（2026-08-03追加ラウンド）ユーザーオペレーション最小化**: 上記3点をさらに簡略化した。投稿記録は投稿URLの1入力のみ（post_id・投稿時刻・投稿者はloggerが補完）、24時間後実績は空欄＝未取得としこれまで求めていた「未取得」の注記自体を不要にし、スキップ記録はmode-orchestratorが下書きして人間は確認のみにした。詳細は[5.](#5-最小オペレーション標準フロー)参照

### まだ残っている不足前提条件（最大2件）

1. **投稿の実行者・アカウント権限が未確認**
   どのXアカウントに、誰が実際にログインして投稿するか（本人か、権限委任された運用者か）が仕様書レベルで明示されていない

2. **2案とも`approved`だった場合の選定基準がない**
   「人間が1案選ぶ」とあるが、選定時に何を基準にするか（フックの強さ、テーマの新鮮さ、直近投稿との重複回避など）のガイドが未整備。判断が属人化するリスクがある

---

## 推奨ファイル名

`ops/reports/phase1_acquisition_launch_spec_2026-08-03.md`（本ファイルの実際の保存名と一致）
