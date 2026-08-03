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

### `posts`シート

| 列名 | 入力者 | 備考 |
|---|---|---|
| post_id / created_at / mode / campaign / theme_id / angle / format / cta_type / objective / disclosure_included / draft_text / final_text / image_style / asset_ids / link_id / review_status / approved_by | **AI** | x-copywriter〜affiliate-compliance-reviewerの過程で自動生成 |
| posted_url | **人間**（唯一の必須入力） | 投稿完了後に貼るだけ |
| posted_at | AI（自動） | URL入力時点のタイムスタンプ |
| posted_by | AI（既定値） | 単独運用中は固定名。複数人運用時のみ選択式にする |

### `reviews`シート

全列AI入力（review_id/post_id/review_type/reviewed_at/reviewer/decision/reason_tags/reason_note/revision_instruction）。人間の入力なし。

### `metrics_24h`シート

| 列名 | 入力者 | 備考 |
|---|---|---|
| metric_id / post_id / window / captured_at | AI（行を事前用意） | |
| impressions / likes / replies / profile_visits / new_follows | **人間**（取得できた分だけ） | **空欄＝未取得。注記不要** |
| reposts / bookmarks | 人間（任意） | 取得できれば |
| profile_visit_rate / like_rate / reply_rate / follow_rate_ref | AI（計算式） | `IFERROR`で空欄を自動的にスキップ |

将来API連携（X Analytics等）が可能になれば、この5項目もAI側の自動取得に置き換えられる設計にしてある（列構造自体は変えず、値の入力元だけが人間→APIに変わる）。

## この設計が体現する原則

- 人間が触れる列は`posts.posted_url`と`metrics_24h`の数値5項目のみ。他はすべてAIが埋める
- 同じ情報（post_id、投稿日時など）を人間に二度入力させない（承認時点で確定した情報をAIが使い回す）
- 「未取得」を人間に書かせない。空欄がそのまま未取得のシグナルになる設計
- 将来DB化する際も、この3テーブル構成（1対多の正規化）をほぼそのまま移植できる

## 現状との関係

- 今のPhase 1は`ops/logs/*.jsonl`/`*.csv`と`ops/reports/daily_brief.md`で運用しており、この設計はまだ適用していない
- Google Sheetsへの移行を実際に行う場合は、hooks実装や外部連携の議論と合わせて別途着手する（今回は見送り）

## 作成手順（実施する場合の参考）

1. 新規スプレッドシートを作成し、タブを`posts`/`reviews`/`metrics_24h`にする
2. 各シート1行目に見出し行を貼り付ける（列名は上記テーブル参照）
3. `review_status`/`format`/`objective`/`review_type`/`decision`にプルダウン（データの入力規則）を設定する
4. `metrics_24h`の計算列に`IFERROR`ベースの数式を入れる
5. `post_id`列に重複チェックの条件付き書式を設定する（任意）
