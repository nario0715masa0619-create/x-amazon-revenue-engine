# x_metrics_collector — X 24時間後メトリクス半自動回収（最小実装／A案）

設計の背景・全体像は[ops/reports/x_metrics_semiauto_design_2026-08-03.md](../../ops/reports/x_metrics_semiauto_design_2026-08-03.md)を参照。このディレクトリはその設計のA案（最小実装）にあたる実コード。

**このページの読み方**: 初めてセットアップする方は、まず一番下の「[運用者向け最短セットアップ手順](#運用者向け最短セットアップ手順)」だけ見れば十分です。詳細や困ったときは本文の該当セクションに戻ってください。

---

## できること

- `posts`シートの`posted_url`（`tweet_id`列が既に埋まっていればそちらを優先）から対象投稿を特定する
- X API v2からメトリクスを取得する
  - `X_BEARER_TOKEN`のみ設定: `public_metrics`（impression/like/reply/bookmark）のみ取得（`data_quality: partial`）
  - `X_USER_ACCESS_TOKEN`も設定: `non_public_metrics`/`organic_metrics`（user_profile_clicks/url_link_clicks/engagements）も取得（`data_quality: ok`）
- `metrics_24h`シートに正規化して書き込む。既存行（同一`post_id`＋`check_window=24h`）があれば更新し、行を積み上げない。`data_quality: manual`の行（人間が後から手入力したもの）は上書きしない
- `profile_visit_rate = user_profile_clicks / impression_count`を計算する（分母が空・0、分子が空の場合は0除算せず空欄にする）

**まだ自動実行の仕組み（cron/スケジューラ/hooks）はない。** 手動、または人間が用意した簡易ジョブから実行する前提（設計ドキュメントの実装オプションA）。日次でユーザーがやることは「投稿後に`posted_url`を1回入れる」→「翌日このコマンドを実行する（または誰かに定期実行してもらう）」の2手だけ。

---

## セットアップ（初回のみ・人間が一度だけ行う作業）

### 1. 依存関係のインストール

```bash
pip install -r scripts/requirements.txt
```

Python 3.10以上を想定（`str | None`のような新しい型ヒント構文を使用）。

### 2. `.env`の作成

```bash
cp .env.example .env
```

`.env`は**リポジトリのルート直下**に置く（`scripts/`配下ではない）。この後の手順で値を埋めていく。`.env`は`.gitignore`で除外済みなのでコミットされない。

### 3. Google Sheetsサービスアカウントの設定

対象スプレッドシート: `19QBFTd6j4_hlV38VhPaVtTLmhlzw5HNQNmyPhmkfmtM`（`posts`/`reviews`/`metrics_24h`の3シートを含む）

1. [Google Cloud Console](https://console.cloud.google.com/)で新規プロジェクトを作成する（既存プロジェクトの流用でもよい）
2. 「APIとサービス」→「ライブラリ」で **Google Sheets API** を検索し有効化する
   - **Google Drive APIの有効化は不要。** 本実装はスプレッドシートIDを直接指定して開く方式（`open_by_key`）のため、Drive経由の検索は行わない
3. 「APIとサービス」→「認証情報」→「認証情報を作成」→「サービスアカウント」でサービスアカウントを作成する
4. 作成したサービスアカウントの「キー」タブ→「鍵を追加」→「新しい鍵を作成」→JSON形式を選んでダウンロードする
5. ダウンロードしたJSONファイルを、リポジトリの外の安全な場所に保管する（リポジトリ内に置く場合は、`.gitignore`の`service-account*.json`パターンに一致するファイル名にすること。例: `service-account-key.json`）
6. 対象スプレッドシート（`https://docs.google.com/spreadsheets/d/19QBFTd6j4_hlV38VhPaVtTLmhlzw5HNQNmyPhmkfmtM/edit`）を開き、右上の「共有」から、サービスアカウントのメールアドレス（JSONファイル内の`client_email`の値。`xxxx@yyyy.iam.gserviceaccount.com`という形式）を**編集者**として追加する
7. `.env`の`GOOGLE_SERVICE_ACCOUNT_JSON_PATH`にJSONファイルの絶対パスを設定する
   - Windows例: `GOOGLE_SERVICE_ACCOUNT_JSON_PATH=C:\Users\you\secrets\service-account-key.json`
   - Mac/Linux例: `GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/home/you/secrets/service-account-key.json`
   - ファイルを置きたくない環境では、JSON内容をbase64エンコードして`GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`に設定してもよい（`_PATH`が設定されていればそちらが優先される）

### 4. X API認証の設定

1. [X Developer Portal](https://developer.x.com/)でプロジェクト・アプリを作成する
2. **public metricsのみでよい場合（最小構成）**: アプリの「Keys and tokens」からApp-only認証用のBearer Tokenを発行し、`.env`の`X_BEARER_TOKEN`に設定する。**これだけで動作する**（`impression_count`/`like_count`/`reply_count`/`bookmark_count`が取得でき、`data_quality: partial`になる。`user_profile_clicks`が空のため`profile_visit_rate`も空欄になる — これは仕様どおりで、算出不可扱いでよい）
3. **non-public metrics（`user_profile_clicks`/`url_link_clicks`/`engagements`）も取得したい場合**: 上記に加えて、投稿アカウント自身でOAuth 2.0 User Context認証を一度だけ完了させる
   - アプリの「User authentication settings」でOAuth 2.0を有効化する（スコープは最低`tweet.read`・`users.read`）
   - X公式のOAuth 2.0 Authorization Code with PKCEフローに従い、投稿アカウント自身でログインして認可し、User Access Tokenを取得する（本実装はこのOAuth認可フロー自体を自動化していない。ブラウザでの認可が必要なため、日次作業ではなく初回1回だけの人間の作業として切り離している）
   - 取得したUser Access Tokenを`.env`の`X_USER_ACCESS_TOKEN`に設定する

**重要**: `X_USER_ACCESS_TOKEN`を用意できない、または用意しない運用でも構わない。その場合は`X_BEARER_TOKEN`だけで`public_metrics`が取得でき、`data_quality: partial`・`profile_visit_rate`空欄という状態で最小運用できる。

---

## セットアップ後の確認コマンド

| コマンド | 何が起きるか | 成功条件 | 失敗時に見る場所 |
|---|---|---|---|
| `pip install -r scripts/requirements.txt` | gspread/google-auth/requests/python-dotenvをインストール | エラーなく終了する | Pythonバージョン（3.10+）、pipの更新、ネットワーク接続 |
| `python -m scripts.x_metrics_collector --post-id p-20260803-001 --dry-run` | Sheetsに接続し対象投稿を読み取り、X APIを呼び出し、結果をコンソールに表示（**書き込みはしない**） | `data_quality=ok`または`data_quality=partial`が表示され、`row = {...}`にメトリクスが入っている | [トラブルシューティング](#トラブルシューティング)参照 |
| `python -m scripts.x_metrics_collector --post-id p-20260803-001` | dry-runと同じ処理を行い、実際に`metrics_24h`シートへ書き込む | 「metrics_24h へ追記しました」または「へ更新しました」と表示され、実際にスプレッドシートを開くと該当行が確認できる | [トラブルシューティング](#トラブルシューティング)参照 |
| `python -m scripts.x_metrics_collector --all-pending` | `posted_url`があり24時間以上経過し未取得（`data_quality`が`ok`/`manual`でない）投稿をまとめて処理 | 対象ごとに上記と同様のログが出る。対象がなければ「処理対象なし」と表示される | 同上 |

---

## Day1データでの動作確認

対象: `post_id: p-20260803-001`、`tweet_id: 2084125939462480008`、`posted_url: https://x.com/ritsu_opt/status/2084125939462480008?s=20`

### 「セットアップ完了手前」と言える基準（X API認証がまだでもここまでは進められる）

- [ ] `pip install -r scripts/requirements.txt`が通る
- [ ] `.env`が作成され、`GOOGLE_SHEETS_SPREADSHEET_ID`が設定されている
- [ ] サービスアカウントJSONが用意され、パスが`.env`に設定されている
- [ ] 対象スプレッドシートがサービスアカウントのメールアドレスに編集者共有されている

### 「実運用開始可」と言える基準

- [ ] 上記に加えて、`--dry-run`実行時に`data_quality`が`url_unresolved`/`auth_missing`以外（`ok`または`partial`）になる
- [ ] `--dry-run`なしで実行し、`metrics_24h`シートに実際に行が追記／更新されることを確認済み

### Day1実行で`metrics_24h`のどの列が埋まるか

| 列 | Bearer Tokenのみ | User Access Tokenも設定 |
|---|---|---|
| `snapshot_id` / `post_id` / `check_window` / `checked_at` | 埋まる | 埋まる |
| `impression_count` / `like_count` / `reply_count` / `bookmark_count` | 埋まる | 埋まる |
| `user_profile_clicks` / `url_link_clicks` / `engagements` | 空欄 | 埋まる |
| `profile_visit_rate` | 空欄 | 埋まる（`user_profile_clicks / impression_count`） |
| `data_quality` | `partial` | `ok` |
| `notes` | non-public未取得の理由 | 空欄 |

---

## `data_quality`の意味

| 値 | 意味 |
|---|---|
| `ok` | public + non-public 両方取得成功 |
| `partial` | public のみ取得成功（User Context未設定。エラーではなく正常な部分取得） |
| `auth_missing` | X API認証情報（Bearer TokenもUser Access Tokenも）が一切設定されていない |
| `api_error` | API呼び出しがエラーになった（レート制限・投稿not found等） |
| `url_unresolved` | `posted_url`からtweet_idを抽出できず、`posts.tweet_id`も空 |
| `manual` | 人間が後で手動入力した行（このスクリプトは上書きしない） |

「値が取れない」ことと「0だった」ことを混同しないため、取得できなかった数値項目は0で埋めず空欄のままにし、理由を`data_quality`/`notes`に残す。

---

## トラブルシューティング

**Google Sheetsに書けない**
- サービスアカウントのメールアドレスが対象スプレッドシートに「編集者」として共有されているか確認する
- `.env`の`GOOGLE_SHEETS_SPREADSHEET_ID`が、スプレッドシートURLの`/d/`と`/edit`の間の文字列と一致しているか確認する
- Google Cloud ConsoleでGoogle Sheets APIが有効化されているか確認する

**サービスアカウント権限不足**
- 共有設定が「閲覧者」ではなく「編集者」になっているか確認する
- サービスアカウントのJSONキーがGoogle Cloud Console上で失効・削除されていないか確認する

**X API認証不足**
- `X_BEARER_TOKEN`または`X_USER_ACCESS_TOKEN`のいずれかが`.env`に設定されているか確認する
- トークンをコピーした際に余分な空白・改行が混入していないか確認する

**`tweet_id`解決失敗（`data_quality: url_unresolved`）**
- `posts.posted_url`が`https://x.com/{user}/status/{tweet_id}`（または`twitter.com`）の形式になっているか確認する
- `posts.tweet_id`列に直接値を入れておけば、`posted_url`の形式に関わらずそちらが優先して使われる

**public metricsは取れるがnon-publicが取れない（`data_quality: partial`）**
- 想定どおりの挙動。`X_USER_ACCESS_TOKEN`が未設定、または投稿アカウント自身のトークンでない可能性がある
- non-publicが必要なら上記「X API認証の設定」手順3を完了させる

**`.env`読み込み失敗**
- `.env`がリポジトリの**ルート直下**（`scripts/`ではない）に置かれているか確認する
- `python-dotenv`がインストールされているか確認する（`pip install -r scripts/requirements.txt`に含まれる）
- コマンドをリポジトリのルートディレクトリから実行しているか確認する

**`data_quality=partial`の意味がわからない**
- 上記「`data_quality`の意味」表を参照。エラーではなく「一部だけ取得できた」という正常な状態

**`data_quality=auth_missing`の意味がわからない**
- `X_BEARER_TOKEN`も`X_USER_ACCESS_TOKEN`も設定されていないため、X APIへのリクエスト自体を送っていない状態

---

## 注意: `profile_visit_rate`について

`user_profile_clicks`（X API非公開メトリクス）を分子とする近似値であり、X管理画面UIに表示される「プロフィール訪問数」と完全に一致する保証はない。

---

## モジュール構成

```
scripts/x_metrics_collector/
  __main__.py       CLIエントリポイント
  config.py         環境変数（.env）からの設定読み込み
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

---

## 運用者向け最短セットアップ手順

管理者向けの詳細手順ではなく、実際に日々運用する人向けの短縮版。

1. Google Cloudでサービスアカウントを作成し、JSONキーをダウンロードする
2. 対象スプレッドシートをサービスアカウントのメールアドレスに「編集者」で共有する
3. `.env.example`を`.env`にコピーし、スプレッドシートID・JSONキーのパスを記入する
4. X Developer PortalでBearer Token（最低限これだけ）を発行し`.env`に記入する。non-public metricsも欲しければUser Access Tokenも取得して記入する
5. `pip install -r scripts/requirements.txt`を実行する
6. `python -m scripts.x_metrics_collector --post-id p-20260803-001 --dry-run`で動作確認する
7. 問題なければ`python -m scripts.x_metrics_collector --post-id p-20260803-001`で本実行する
8. 以降は、投稿後に`posted_url`をSheetsに入れる → 翌日`--all-pending`を実行する、の2手だけで回る
