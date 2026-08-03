# phase1_acquisition_launch_spec_2026-08-03.md — Phase 1 集客モード本番運用仕様書

> このドキュメントは、集客（acquisition）モードのみを対象とした本番運用（Phase 1）の仕様書。教育・販売モードの本番投入は対象外。3本のdry run（[acquisition](dryrun_2026-08-02_fashion-gadget_acquisition.md)/[education](dryrun_2026-08-02_fashion-gadget_education.md)/[sales](dryrun_2026-08-02_fashion-gadget_sales.md)）と[横断レビュー](cross_mode_review_2026-08-02.md)、[次フェーズ整合レビュー](next_phase_alignment_review_2026-08-03.md)を前提とする。hooks実装・schema変更・外部API連携は今回対象外。

---

## 1. Phase 1 の範囲と自律境界

### 対象

- モード: **acquisition（集客）のみ**。教育・販売は対象外（`ops/state/current_mode.yaml`は引き続き`acquisition`）
- カテゴリ: ファッション×ガジェット
- 目的: X運用の実開始。フォロワー基盤・エンゲージメント基盤の構築が目的であり、売上・コンバージョンはPhase 1のスコープ外

### Claude Codeが自律で行う範囲

- 投稿候補生成（x-researcher → growth-marketer → x-copywriter、`templates/x_post_template.md`準拠で毎回2案）
- レビュー（affiliate-compliance-reviewer、`templates/review_template.md`準拠。needs_revision時は同一post_id維持で再提出→再レビューの閉ループ実施）
- ログ候補作成（logger、`ops/logs/post_log.jsonl`へのレビュー提出時点からの状態遷移記録）
- 簡易振り返り（performance-analyst、日次の軽い振り返りと週次のまとめ）

### 人間が行う範囲（Claude Codeは行わない）

- **最終承認**: `approved`となった案の中から実際に投稿する1案を選ぶ
- **実投稿**: X上への実際の投稿操作
- 24時間後の実績数値の取得（X Analytics等からの手動取得。詳細は[6. 不足している前提条件](#6-不足している前提条件本番開始前に埋めるべきもの)を参照）
- 投稿完了後の`status: posted`への更新の最終確認

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
| 副KPI | `follow_rate` | `フォロー数 / profile_visits` | X Analytics等から手動取得したフォロー数を用いる（取得方法は未確定。[6.](#6-不足している前提条件本番開始前に埋めるべきもの)参照） |

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

## 5. 日次運用の標準フロー

### 5-1. 投稿候補生成〜承認（当日朝、実投稿前）

1. **mode-orchestrator**: 当日のテーマ（スプリント表参照）を確認し、担当へのタスク分解を行う
2. **growth-marketer**: 当日テーマに対する施策設計（狙うKPI: `impressions`/`profile_visit_rate`、CTA type: `profile_visit`）
3. **x-copywriter**: `templates/x_post_template.md`準拠で投稿案を**2案**作成
4. **affiliate-compliance-reviewer**: 2案を`templates/review_template.md`でレビュー
   - `needs_revision`の場合: x-copywriterが同一post_id維持で修正版を再提出 → affiliate-compliance-reviewerが再レビュー（[logger.mdの再提出ルール](../../.claude/agents/logger.md)に準拠）。当日中に`approved`まで到達しない場合は[6.](#6-不足している前提条件本番開始前に埋めるべきもの)のフォールバック方針を参照
5. **logger**: レビュー提出時点で`post_id`を発行し、`draft`/`needs_revision`/`approved`の状態遷移を`ops/logs/post_log.jsonl`に記録
6. **人間（最終承認）**: `approved`となった案（1〜2件）の中から実際に投稿する1案を選ぶ
7. **人間（実投稿）**: 選んだ案をXに実際に投稿する

### 5-2. 投稿後の記録（当日中）

8. 実際に投稿したpost_idと投稿URL・投稿時刻を、`ops/reports/daily_brief.md`に暫定記録する（schemaに投稿URL/実投稿時刻を格納するフィールドが現状ないための暫定運用。[6.](#6-不足している前提条件本番開始前に埋めるべきもの)参照）
9. 投稿しなかった側の案（2案のうち選ばれなかった`approved`案）は、`status: approved`のまま`archived`として扱ってよいかを人間が判断する

### 5-3. 24時間後の簡易記録（投稿翌日）

10. **人間**: 前日投稿の24時間後実績（`impressions`/`engagements`/`profile_visits`等）をX Analytics等から取得する
11. **logger**: 取得値を`window: 24h`のスナップショットとして`ops/logs/metrics_snapshots.csv`に記録
12. **performance-analyst**: 前日投稿1件分の簡易振り返り（`profile_visit_rate`の実績値と一言コメントのみ。詳細分析は週次でまとめて行う）を`ops/reports/daily_brief.md`に追記

---

## 6. 週次振り返りの標準フロー

対象: 初週5投稿すべての24時間後スナップショットが揃った時点（Day8目安）。

1. **performance-analyst**: 5投稿分の`post_log`と`metrics_snapshots`を突き合わせ、テーマ別（T1/T2/T3）・フックタイプ別に`impressions`/`profile_visit_rate`を比較する。勝ち筋・負け筋仮説を抽出する（サンプル数5件は少数のため、「参考値」である旨を明記する）
2. **weekly-pdca-review skill**: `templates/weekly_report_template.md`に沿って`ops/reports/weekly_review.md`を更新する
   - `mode_weights.yaml`の変更: Phase 1は`acquisition`固定運用のため、通常は「不要」判断となる想定
   - `docs/playbooks/acquisition.md` / `.claude/skills/acquisition-playbook/SKILL.md`の更新要否を検討する（初期基準値と大きく異なる傾向が出た場合のみ）
3. **人間**: 週次レビュー結果を確認し、Phase 2（投稿頻度の拡大、教育モードの追加検討等）に進むかどうかを判断する

---

## 7. 本番開始前に埋めるべき不足前提条件（最大5件）

Phase 1の設計時点で、以下5点は仕様として未確定、または既存schemaの制約により暫定運用に留まっている。本番開始前、または開始後早い段階で埋める必要がある。

1. **`posted`状態への遷移条件・実際の投稿URL/投稿時刻を記録する場所が未定義**
   `schemas/post_log.schema.json`は`additionalProperties: false`であり、現行フィールドに投稿URL・実投稿時刻を格納する場所がない。今回は暫定的に`ops/reports/daily_brief.md`への手記録で回避しているが、投稿数が増えると破綻する。次フェーズでのschema拡張候補（[next_phase_alignment_review_2026-08-03.md](next_phase_alignment_review_2026-08-03.md)のC-1と合わせて検討するのが望ましい）

2. **24時間後実績・フォロー数の取得方法（手動取得の具体的な手順）が未確定**
   「人間が手動取得する」という前提のみで、X Analyticsのどの画面から何を見るか、`follow_rate`算出に必要なフォロー数をどう計測するか（アカウント全体のフォロワー純増数か、投稿起因と推定できる数かなど）の具体的な手順が定義されていない

3. **投稿の実行者・アカウント権限が未確認**
   どのXアカウントに、誰が実際にログインして投稿するか（本人か、権限委任された運用者か）が仕様書レベルで明示されていない

4. **2案とも`approved`だった場合の選定基準がない**
   「人間が1案選ぶ」とあるが、選定時に何を基準にするか（フックの強さ、テーマの新鮮さ、直近投稿との重複回避など）のガイドが未整備。判断が属人化するリスクがある

5. **needs_revisionが当日中に解消しない場合のフォールバック方針がない**
   1日1本ペースで再レビューに時間がかかった場合、その日の投稿を見送るか、翌日に2本投稿するか、テーマ順を入れ替えるかの運用ルールが未定義。スプリント計画（[4.](#4-1週間スプリント計画)）が崩れた場合の扱いを事前に決めておく必要がある

---

## 推奨ファイル名

`ops/reports/phase1_acquisition_launch_spec_2026-08-03.md`（本ファイルの実際の保存名と一致）
