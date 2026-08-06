# morning_strategy_brief.md — 毎朝の戦略会議ブリーフ テンプレート

> council-chairが`morning-strategy-council` skillの結論をまとめる際の型。5役（trend-analyst/competitor-analyst/audience-representative/growth-strategist/risk-compliance-observer）の所見を要約したものであり、新しい意見は追加しない。
> **これは投稿文そのもののレビューではない。** 投稿案の査読は`templates/market_grounded_review_template.md`、コンプラ最終判定は`templates/review_template.md`を使う。
> **現在はPhase 1の暫定評価フェーズ中。** 前日実績はスクショ由来の`data_quality: manual`行が中心であり、不完全データの扱いは下記「不完全データの扱い」節に従う（詳細: `ops/reports/provisional_evaluation_phase_2026-08-04.md`）。

---

# Morning Strategy Brief

- **TL;DR（1行）**: 人間はこの1行と「Recommended direction」だけ読めば当日方針を選べる状態にする。詳細欄は根拠を確認したいときのみ参照する
- Date:
- Mode:
- Account:
- Yesterday status summary:（`ops/reports/daily_brief.md`の「24時間後実績記録」表から生成。現在は`data_quality: manual`（スクショ由来の暫定評価レーン）が中心。**`data_quality`は`ops/logs/metrics_snapshots.csv`には存在しない（2026-08-06修正。schema準拠の数値のみを持つ別ファイル）**。将来Google Sheets `metrics_24h`シート移行後はそちらが正本になり、`ok`/`partial`行も対象になる。`profile_visit_rate`は`user_profile_clicks`ベースの近似値である旨を踏まえて記述する。データが不完全な場合は下記「不完全データの扱い」に従う）
- Today objective:
- **競合比で今日勝ちに行く軸**:（停止力／自分事化／差別化／緊張感／遷移力のいずれか。詳細は`ops/reports/phase1_acquisition_launch_spec_2026-08-03.md`の「集客モードの評価思想」参照）
- **競合比で避けるべき弱さ**:（例: 抽象論、ありふれた整理論、説明から入る導入）
- **今日のフック仮説**:（例: 私的空間より対人空間のほうが40代男性には刺さる）
- **競合比で最低限同等以上を狙う条件**:（何が満たせなければ、その日の案は弱いとみなすか）
- Recommended theme:
- Recommended angle:
- Recommended hook direction:
- CTA direction:
- Fixed variables:
- One variable to test:
- Avoid list:
- Risk notes:
- 2-3 candidate directions for human approval:
- Recommended direction:
- Confidence:
- If evidence is weak, say why:

---

## 不完全データの扱い（暫定評価フェーズ中のルール）

- `impression_count`しかない場合、その投稿・テーマ全体を「失敗」と断定しない（データが薄いことと成果が悪いことを混同しない）
- 指標欠損時は、KPIの断定より**フック仮説の検証**（hook_strengthの観点）を優先する
- データが弱い日は`Confidence`を`low`にし、「If evidence is weak, say why」にデータ欠損由来か仮説自体が弱いのかを明記する
- 参照した`metrics_24h`行の`data_quality`が`manual`（暫定評価レーン）であることを「Yesterday status summary」に明記し、将来のAPI由来データ（`ok`/`partial`）と混同しない
