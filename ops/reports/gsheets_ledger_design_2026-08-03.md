# gsheets_ledger_design_2026-08-03.md — Google Sheets運用台帳 設計（将来の正本移行先）

> **これは設計ドキュメントであり、現時点で実装・接続はしていない。** hooks・外部API連携はまだ行わない方針（CLAUDE.md）に従い、Phase 1の実運用は引き続き`ops/logs/*.jsonl`/`*.csv`（schema準拠）と`ops/reports/daily_brief.md`（人間の最小入力窓口）で回す。このドキュメントは「次にどこへ正本を寄せるか」の設計であり、[phase1_acquisition_launch_spec_2026-08-03.md](phase1_acquisition_launch_spec_2026-08-03.md)の「ユーザーオペレーション最小化の原則」を将来さらに徹底するための移行先候補として位置づける。

## 目的

- X運用の実務記録を、将来的にGoogle Sheets（さらにDB）で管理できる状態に備える
- 正規化寄りのテーブル設計にしておくことで、DB移行時の手戻りを減らす
- **人間の入力を最小化する**という原則を、記録レイヤーの構造そのものに反映する

## シート構成（3シート・正規化）

```
posts (投稿マスタ、1 post_id = 1行)
  ↓ 1対多
reviews (レビュー履歴、追記のみ)
  ↓ 1対多
metrics_24h (数値スナップショット、追記のみ)
```

## 列設計（人間入力とAI入力を明示）

> **2026-08-03改訂**: `posts`/`metrics_24h`の列を、X API v2のフィールド名に揃える形で見直した（[x_metrics_semiauto_design_2026-08-03.md](x_metrics_semiauto_design_2026-08-03.md)参照）。旧列名（`impressions`等）は新設計の`impression_count`等に統合し、API取得を前提にした列（`tweet_id`/`selected_for_post`/`data_quality`）を追加した。

### `posts`シート

| 列名 | 入力者 | 備考 |
|---|---|---|
| post_id / platform / created_at / mode / campaign / theme_id / angle / objective / target / format / cta_type / disclosure_included / draft_text / final_text / image_style / asset_ids / link_id / review_status / approved_by | **AI** | x-copywriter〜affiliate-compliance-reviewerの過程で自動生成。`platform`は現状`X`固定、`target`はアカウント設計の対象層（例: `40s`） |
| selected_for_post | AI（既定）／人間が上書き可 | 2案のうち投稿する側をB（最終承認）で示す。承認時に自明なため通常は人間が別途入力しない |
| posted_url | **人間**（唯一の必須入力） | 投稿完了後に貼るだけ |
| tweet_id | AI（自動抽出） | `posted_url`からURLパターン抽出（`https://x.com/{user}/status/{tweet_id}`）。x-metrics-collectorがメトリクス取得時のキーに使う |
| posted_at | AI（自動） | URL入力時点のタイムスタンプ |
| posted_by | AI（既定値） | 単独運用中は固定名。複数人運用時のみ選択式にする |
| notes | AI／人間（任意） | |

### `reviews`シート

全列AI入力（review_id/post_id/review_type/reviewed_at/reviewer/decision/reason_tags/reason_note/revision_instruction）。人間の入力なし。

### `metrics_24h`シート

| 列名 | 入力者 | 備考 |
|---|---|---|
| snapshot_id / post_id / checked_at / check_window | AI（行を事前用意） | `check_window`は現状`24h`固定 |
| impression_count / like_count / reply_count / bookmark_count | **AI（X API自動取得）**、失敗時のみ人間が補完 | public_metrics相当。取得成功なら人間の作業は発生しない |
| user_profile_clicks / url_link_clicks / engagements | **AI（X API自動取得、要User Context認証）**、失敗時のみ人間が補完 | non_public_metrics/organic_metrics相当。認証条件を満たさない場合は取得不可（詳細は[x_metrics_semiauto_design_2026-08-03.md](x_metrics_semiauto_design_2026-08-03.md)） |
| profile_visit_rate | AI（計算式） | 分母`impression_count`、分子`user_profile_clicks`。**X管理画面の「プロフィール訪問数」と完全一致する保証はない近似値**（注意書き必須） |
| like_rate / reply_rate | AI（計算式） | `IFERROR`で空欄を自動的にスキップ |
| data_quality | AI | `ok` / `partial`（一部項目のみ取得） / `auth_missing`（認証未設定） / `api_error`（API呼び出し失敗） / `url_unresolved`（tweet_id抽出失敗） / `manual`（人間が手動補完） |
| notes | AI／人間 | 取得失敗理由やAPI取得不可時の代替手段（手動確認依頼など） |

**空欄ルールの整理（2種類を区別する）**:
- **人間が意図的に空欄にした場合** = 「取得できなかった」の意（従来ルールどおり、注記不要）
- **AIがAPI取得を試みて失敗した場合** = 空欄のままにせず、必ず`data_quality`と`notes`に理由を残す（原因不明の欠測にしない）

将来API連携が確立すれば、`impression_count`〜`engagements`の6項目は原則AI自動取得に置き換わり、人間が触れるのは`posts.posted_url`のみになる（Phase 1では取得失敗時のみ人間が補完する設計）。

## この設計が体現する原則

- 人間が触れる列は原則`posts.posted_url`のみ。`metrics_24h`の数値もAPI取得成功時は人間の作業がゼロになる
- 同じ情報（post_id、投稿日時など）を人間に二度入力させない（承認時点で確定した情報をAIが使い回す）
- 「未取得」を人間に書かせない。人間の空欄はそのまま未取得のシグナル。AI起因の欠測は理由付きで`data_quality`に残す
- 将来DB化する際も、この3テーブル構成（1対多の正規化）をほぼそのまま移植できる

## 現状との関係

> **実装状況（2026-08-04追記）**: 対象スプレッドシート（ID: `19QBFTd6j4_hlV38VhPaVtTLmhlzw5HNQNmyPhmkfmtM`）が実際に作成され、`posts`/`reviews`/`metrics_24h`の3シートが存在する。[scripts/x_metrics_collector/](../../scripts/x_metrics_collector/)（最小実装）がこの実シートを対象に`posts`の読み取りと`metrics_24h`への書き込みを行う。`reviews`シートへの書き込みはまだ実装していない（現状は空でよい運用のまま）。

- 投稿候補生成〜承認〜投稿（`posts`/`reviews`）は引き続き`ops/logs/*.jsonl`/`*.csv`と`ops/reports/daily_brief.md`が正本であり、この設計・実装はまだ適用していない
- 24時間後メトリクス回収（`metrics_24h`）のみ、Google Sheets実シートへの読み書きを先行実装した（本ドキュメントおよび[x_metrics_semiauto_design_2026-08-03.md](x_metrics_semiauto_design_2026-08-03.md)参照）
- `posts`/`reviews`シート側の本格運用移行（hooks実装や外部連携含む）は引き続き見送り

## 作成手順（実施する場合の参考）

1. 新規スプレッドシートを作成し、タブを`posts`/`reviews`/`metrics_24h`にする
2. 各シート1行目に見出し行を貼り付ける（列名は上記テーブル参照）
3. `review_status`/`format`/`objective`/`review_type`/`decision`/`data_quality`にプルダウン（データの入力規則）を設定する
4. `metrics_24h`の計算列に`IFERROR`ベースの数式を入れる
5. `post_id`列に重複チェックの条件付き書式を設定する（任意）
6. `tweet_id`は`posted_url`からの正規表現抽出（`ARRAYFORMULA(REGEXEXTRACT(...))`等）で自動化できる（実施する場合の参考。現時点では未実装）
