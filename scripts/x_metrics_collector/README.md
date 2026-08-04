# x_metrics_collector — X 24時間後メトリクス半自動回収（最小実装／A案）

設計の背景・全体像は[ops/reports/x_metrics_semiauto_design_2026-08-03.md](../../ops/reports/x_metrics_semiauto_design_2026-08-03.md)を参照。このディレクトリはその設計のA案（最小実装）にあたる実コード。

## できること

- `posts`シートの`posted_url`（未設定なら`tweet_id`が既にあればそれを優先）から対象投稿を特定する
- X API v2からメトリクスを取得する
  - `X_BEARER_TOKEN`のみ設定: `public_metrics`（impression/like/reply/bookmark）のみ取得（`data_quality: partial`）
  - `X_USER_ACCESS_TOKEN`も設定: `non_public_metrics`/`organic_metrics`（user_profile_clicks/url_link_clicks/engagements）も取得（`data_quality: ok`）
- `metrics_24h`シートに正規化して書き込む。既存行（同一`post_id`＋`check_window=24h`）があれば更新し、行を積み上げない。`data_quality: manual`の行（人間が後から手入力したもの）は上書きしない
- `profile_visit_rate = user_profile_clicks / impression_count`を計算する（0除算・欠損時は空欄）

**まだ自動実行の仕組み（cron/スケジューラ/hooks）はない。** 手動、または人間が用意した簡易ジョブから実行する前提（設計ドキュメントの実装オプションA）。

## セットアップ（初回のみ）

1. 依存関係をインストールする

   ```bash
   pip install -r scripts/requirements.txt
   ```

2. `.env.example`を`.env`にコピーし、値を埋める

   ```bash
   cp .env.example .env
   ```

3. Google Sheetsサービスアカウントを作成し、対象スプレッドシート（ID: `19QBFTd6j4_hlV38VhPaVtTLmhlzw5HNQNmyPhmkfmtM`）を編集者として共有する
   - Google Cloud ConsoleでサービスアカウントJSONキーを発行する
   - `.env`の`GOOGLE_SERVICE_ACCOUNT_JSON_PATH`にJSONファイルのパスを設定する（またはBase64化して`GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`に設定する）
   - サービスアカウントのメールアドレスを、対象スプレッドシートの共有設定に「編集者」として追加する

4. X API認証を用意する
   - `public_metrics`のみでよければ、X Developer PortalでApp-only Bearer Tokenを発行し`X_BEARER_TOKEN`に設定する
   - `user_profile_clicks`等も取得する場合、投稿アカウント自身でOAuth 2.0 User Context認証を一度だけ完了し、得られたUser Access Tokenを`X_USER_ACCESS_TOKEN`に設定する（本実装はOAuth認可フロー自体は実装していない。X公式のOAuth 2.0 Authorization Code with PKCEフローに従って取得する。**これは日次作業ではなく初回1回だけの人間の作業**）

## 実行方法

```bash
# Day1の投稿(p-20260803-001)を対象に、書き込みなしで動作確認する
python -m scripts.x_metrics_collector --post-id p-20260803-001 --dry-run

# 確認できたら実際にSheetsへ書き込む
python -m scripts.x_metrics_collector --post-id p-20260803-001

# 投稿から24時間以上経過し、まだ取得できていない投稿をまとめて処理する
python -m scripts.x_metrics_collector --all-pending
```

`--dry-run`をつけると、Sheetsへの書き込みを行わず、取得結果と書き込み予定の行をコンソールに表示するだけになる。初回動作確認には`--dry-run`を推奨する。

## `data_quality`の意味

| 値 | 意味 |
|---|---|
| `ok` | public + non-public 両方取得成功 |
| `partial` | public のみ取得成功（User Context未設定） |
| `auth_missing` | X API認証情報が一切設定されていない |
| `api_error` | API呼び出しがエラーになった（レート制限・投稿not found等） |
| `url_unresolved` | `posted_url`からtweet_idを抽出できず、`posts.tweet_id`も空 |
| `manual` | 人間が後で手動入力した行（このスクリプトは上書きしない） |

「値が取れない」ことと「0だった」ことを混同しないため、取得できなかった数値項目は0で埋めず空欄のままにし、理由を`data_quality`/`notes`に残す。

## 注意: `profile_visit_rate`について

`user_profile_clicks`（X API非公開メトリクス）を分子とする近似値であり、X管理画面UIに表示される「プロフィール訪問数」と完全に一致する保証はない。

## モジュール構成

```
scripts/x_metrics_collector/
  __main__.py       CLIエントリポイント
  config.py         環境変数からの設定読み込み
  tweet_id.py        posted_url からの tweet_id 抽出
  x_api_client.py    X API v2 呼び出し
  sheets_client.py    Google Sheets 読み書き（列名ベース）
  collector.py         回収ロジックの中核（取得結果の正規化、data_quality判定、profile_visit_rate計算）
```

`collector.py`と`tweet_id.py`はSheets/X APIへの実アクセスを行わず、ロジックのみを持つ。ネットワークなしでも単体で検証できる（本実装時に確認済み）。

## 今後の拡張（B/C案、未実装）

- **B**: 24時間後の自動起動（cron等）、失敗時リトライ、朝会向け要約の自動生成
- **C**: 投稿API連携によりURL入力自体を不要にする完全自動化

詳細は[x_metrics_semiauto_design_2026-08-03.md](../../ops/reports/x_metrics_semiauto_design_2026-08-03.md)参照。
