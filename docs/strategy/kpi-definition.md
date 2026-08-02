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
