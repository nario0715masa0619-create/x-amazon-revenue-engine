# kpi-definition.md — KPI定義

## モード別KPI

| モード | 主KPI | 補助KPI | 意味 |
|---|---|---|---|
| 集客 (acquisition) | `impressions`, `profile_visit_rate` | `follow_rate` | どれだけ新規に見つけてもらい、興味を持たれたか |
| 教育 (education) | `save_rate`, `reply_rate` | `link_preclick_interest` | どれだけ理解・信頼を積み上げられたか |
| 販売 (sales) | `ctr`, `conversion` | `revenue`, `epc` | どれだけ具体的な成果につながったか |

- `profile_visit_rate` = プロフィール訪問数 / インプレッション数
- `follow_rate` = フォロー数 / プロフィール訪問数
- `save_rate` = ブックマーク数 / インプレッション数
- `link_preclick_interest` = リンククリック前の反応（返信・引用等でリンクへの言及があるか）の簡易指標。将来的に定量化を検討
- `ctr` = リンククリック数 / インプレッション数
- `conversion` = 購入数 / リンククリック数
- `epc` (Earnings Per Click) = 報酬額 / リンククリック数

## 投稿単位KPI

`ops/logs/metrics_snapshots.csv` に記録する、post_id単位の実測値:

- `impressions`（表示回数）
- `engagements`（いいね・返信・repost・bookmarkの合計、または各SNSの定義に準拠）
- `likes` / `replies` / `reposts` / `bookmarks`
- `profile_visits`
- `link_clicks`
- `conversions`
- `revenue`
- `epc`

投稿単位KPIは、複数時点でスナップショットを取ることを想定する（投稿直後・24時間後・7日後 等）。`window` フィールド（[metrics_snapshot.schema.json](../../schemas/metrics_snapshot.schema.json)）でどの期間の値かを明示する。

## CTA別「強い投稿」判定ルール（2026-08-06追加）

**「強い投稿」を`impressions`の絶対値では定義しない。** 投稿が狙った行動（CTA）をどれだけ起こせたかで判定する。CTA typeごとに主指標を切り替え、同条件群内での相対評価を基本とするが、実績データが少ない期間は下記「Cold-start mode」で運用する。

### 判定順序

主指標 → 補助指標 → 失格条件 → 人間ゲート

### CTA type別 主指標・補助指標・失格条件

`post_log.schema.json`の`cta_type`は自由文字列（enum制約なし）のため、以下の語彙追加にschema変更は不要。**「コメント誘導」を意味するCTA typeは`comment`ではなく、既存の`reply_prompt`に統一する**（新語彙を増やさない）。

| cta_type | 主指標 | 使用フィールド（`metrics_snapshot.schema.json`） | 補助指標 | 失格条件 |
|---|---|---|---|---|
| `profile_visit` | `profile_visit_rate` = `profile_visits / impressions` | `profile_visits`, `impressions` | `impressions`, `likes`, `replies`, `bookmarks` | rateが低い／`impressions`が極端に少ない／一読で意味が通らない／プロフィールへ飛ぶ理由が弱い／特殊要因で伸びているだけ |
| `reply_prompt` | `reply_rate` = `replies / impressions` | `replies`, `impressions` | `replies`実数, `impressions` | rateは高く見えるが母数が小さすぎる／返信が薄い・スタンプ中心・ターゲット外ばかり／一読で意味が通らない／返信を促す理由が弱い |
| `link_click` | `ctr` = `link_clicks / impressions` | `link_clicks`, `impressions` | `link_clicks`実数, `profile_visits` | CTRが低い／リンクを押す理由が弱い／フックは強いが本文が遷移につながらない／特殊要因でクリックされているだけ |
| `save`（bookmark誘導） | `save_rate` = `bookmarks / impressions` | `bookmarks`, `impressions` | `bookmarks`実数, `likes`, `replies` | 保存価値が薄い／rateが低い／保存したくなる具体性がない／一読で意味が通らない |
| `reach`（awareness、CTA明示なしの場合） | `impressions` | `impressions` | `likes`, `replies`, `bookmarks`, `profile_visits` | `impressions`が低い／フックが弱い／抽象的すぎる／止まる理由がない |

「コメント内容の質」「保存したくなる具体性」等の定性判断は数値化フィールドを持たないため、下記の人間ゲートおよび`daily_brief.md`の定性メモ（notes相当欄）で扱う。

### 同条件群の定義

強さ判定は、以下が揃った投稿同士だけで比較する: 同一platform（X固定）・同一account・同一objective（mode）・同一format・同一cta_type・同一target phase（Phase 1は単一ターゲットのため定数）・quote repost/外部ブーストなし・比較可能な期間。`mode`/`format`/`cta_type`は`post_log.schema.json`の既存フィールドで絞り込み可能。「quote repost/外部ブーストなし」を機械的に判定する材料は現状ないため、外れ値が疑われる場合は`daily_brief.md`側の定性メモに記録する（新規schemaフィールドは追加しない）。

### 二段階運用モード

**現時点で`ops/logs/post_log.jsonl`・`ops/logs/metrics_snapshots.csv`には実績データがほとんど蓄積されていない。** これはCTA別ルール導入自体のブロッカーではなく、**厳密な相対評価（百分位）を行うためのブロッカー**として扱う。ルールは今すぐ導入し、サンプルが少ない間は簡易判定で運用する。

#### Cold-start mode（デフォルト。同条件群の有効サンプルが5件未満の間）

- 厳密な上位25〜30%判定は行わない
- 主指標・補助指標・失格条件をもとに、**「明確に強い」／「明確に弱い」／「保留」**の3値で暫定判定する
  - 明確に強い: 主指標が同条件群内の既存最大値を明確に上回り、失格条件に該当せず、人間ゲートを通過する
  - 明確に弱い: 失格条件に該当する、または主指標が同条件群内で明確に見劣りする
  - 保留: 判断材料不足（observation only相当）
- 5件という閾値は、[phase1_acquisition_launch_spec_2026-08-03.md](../../ops/reports/phase1_acquisition_launch_spec_2026-08-03.md)の「初週5投稿を初期基準値とする」設計と揃えている

#### Relative benchmark mode（同条件群の有効サンプルが5件以上に達した後）

- 同条件群内で相対評価する
  - 上位25〜30% → strong candidate
  - 中位帯 → observation only
  - 下位帯 → baseline不採用
- 投稿数がまだ少ない期間は、厳密な百分位にこだわらず「同条件群の中で明確に上位か」を優先してよい

### 人間ゲート（どちらのモードでも必須）

以下を満たさない投稿は、主指標がどれだけ良くても「強い投稿」と認定しない:

- 一読で意味が通る
- 一文目で止まる理由がある
- 抽象的すぎない
- 過去の自分の見せられる投稿より弱く見えない
- CTAへの導線が自然

### 出力分類（3分類、モード共通）

1. **benchmark candidate** — CTA別主指標が強い（Cold-startなら「明確に強い」、Relative benchmarkなら上位25〜30%）、人間ゲート通過。次回生成のベースライン候補
2. **observation only** — 条件が揃わない、または主指標は弱いが観察価値がある。参考にするが生成ベースラインには使わない
3. **reject / failure** — 主指標が弱い、人間ゲートで落ちる、意味不明／抽象的／CTA弱い。生成ベースラインに使わない

## 週次で見るKPI

`weekly-pdca-review` skill 実行時に確認する集計値:

- モード別の投稿数と、各モードの主KPI平均・合計
- モード比率（実績）と `ops/state/mode_weights.yaml`（目標比率）の乖離
- 訴求角度別・商品カテゴリ別の成果比較
- 実施した experiment（A/B等）の結果サマリ
- 前週比の増減

## 将来的な North Star Metric の候補

現時点では単一のNorth Star Metricを確定しない。運用データが蓄積した段階で、以下のような候補から選定・検証する:

- **週次の紹介料収益（revenue）** — 最終的な事業目的に最も近いが、初期は母数が小さく振れ幅が大きい
- **週次の実質リーチ × epc** — リーチの質を織り込んだ複合指標。母数の小ささを緩和できる可能性がある
- **フォロワーあたりの週次revenue** — アカウント規模に依存しない効率指標

候補の選定自体も `weekly-pdca-review` の議題とし、一定期間（例: 8週間分）のデータが溜まった時点で見直す。
