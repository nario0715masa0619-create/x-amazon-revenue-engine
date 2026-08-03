# daily_brief.md — 日次ブリーフ（テンプレート）

> mode-orchestrator が1日の始まりに使う簡易サマリ。埋めて使う。
> Phase 1（集客モード本番運用）では、当日朝の計画欄に加えて、投稿後・翌日の記録欄も同じファイルに追記していく運用とする（[phase1_acquisition_launch_spec_2026-08-03.md](phase1_acquisition_launch_spec_2026-08-03.md)参照）。`post_log.schema.json`/`metrics_snapshot.schema.json`を変更しない前提の暫定記録先。

## 対象日

YYYY-MM-DD

## 現在モード

- `ops/state/current_mode.yaml` の値: (記入)
- 直近のモード別投稿比率（実績）: 集客 __% / 教育 __% / 販売 __%

## 前日の実績サマリ

- 投稿件数: __件（集客__ / 教育__ / 販売__）
- 特筆すべき数値変化: (記入)
- ログの欠損・要確認事項: (記入、なければ「なし」)

## 本日の予定

- 予定している投稿・施策: (記入)
- 想定モード: (記入)
- 必要な担当: (記入)

## 実投稿記録（投稿完了後に記入。Phase 1暫定運用）

`status: posted` = 人間がXへの投稿完了を確認した状態。投稿URL・投稿時刻・投稿者は`post_log.schema.json`に格納する場所がないため、当面ここに記録する（将来のschema拡張候補、[phase1spec](phase1_acquisition_launch_spec_2026-08-03.md)参照）。

| post_id | 投稿URL | 投稿時刻 | 投稿者 | 備考 |
|---|---|---|---|---|
| | | | | |

## 24時間後実績記録（投稿翌日に記入。Phase 1暫定運用）

最小取得項目: `impressions` / `likes` / `replies` / `profile_visits` / フォロワー純増数（参考値、取れれば）。取得できない項目は空欄にせず、`metrics_snapshots.csv`には暫定値として`0`を記録した上で、下表の備考に「未取得」と明記する（0＝実測ゼロと0＝未取得を区別するため）。`reposts`/`bookmarks`/`engagements`も取得できれば記録し、できなければ同様に扱う。`link_clicks`/`conversions`/`revenue`/`epc`は集客モードではリンクを使わないため常に`0`（未取得ではなく実測ゼロ）。

| post_id | impressions | likes | replies | profile_visits | フォロワー純増数(参考) | 備考(未取得項目など) |
|---|---|---|---|---|---|---|
| | | | | | | |

## スキップ/持ち越し記録（needs_revisionが当日中に解消しなかった場合）

当日中に`approved`が1本も出なかった場合、その日の投稿はスキップしてよい（Phase 1では投稿本数より運用安定を優先する）。

| 対象post_id | 状況 | スキップ理由 | 翌日の扱い（再レビュー優先 / 新規テーマ優先） | 備考 |
|---|---|---|---|---|
| | | | | |

## 懸念・要確認

- (記入、なければ「なし」)
