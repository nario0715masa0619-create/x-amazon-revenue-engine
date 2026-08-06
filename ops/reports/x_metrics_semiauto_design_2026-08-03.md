# x_metrics_semiauto_design_2026-08-03.md — X APIによる24hメトリクス半自動回収 設計

> 対象は[phase1_acquisition_launch_spec_2026-08-03.md](phase1_acquisition_launch_spec_2026-08-03.md)の最小オペレーション標準フロー（A〜D）のうち、**Dの後（24時間後メトリクス回収）を半自動化する設計**。本番用の認証情報・APIキーはこの設計ドキュメントにもコード側にも記載しない。CLAUDE.mdの「本番投稿の自動化はまだ行わない」「hooks実装は明示的な指示があるまで着手しない」方針は維持しており、24時間後の自動起動機構（cron/スケジューラ/hooks）自体は未実装。

> **実装状況（2026-08-04追記）**: 本設計のA案（最小実装）を[scripts/x_metrics_collector/](../../scripts/x_metrics_collector/)としてコード化済み。手動実行（`python -m scripts.x_metrics_collector --post-id <id>`または`--all-pending`）でGoogle Sheets（`posts`/`metrics_24h`）とX APIを実際に読み書きできる。セットアップ・実行手順は[scripts/x_metrics_collector/README.md](../../scripts/x_metrics_collector/README.md)参照。B/C案（自動トリガー、URL入力不要化）は引き続き未実装で、本ドキュメントのF/G節に整理したまま。

---

## A. 半自動Xメトリクス回収フロー概要

```
人間: X投稿 (C)
  ↓
人間: posted_url を1回入力 (D) ─ ここまでは既存の最小オペレーション
  ↓
AI (logger): posted_url から tweet_id を抽出し、post_idと対応付ける
  ↓
[24時間後] 起動（Phase 1では人間トリガー、将来的にはスケジューラ）
  ↓
AI (x-metrics-collector): X APIからメトリクス取得（認証条件を満たす場合）
  ↓
AI: 取得値を metrics_24h シートに正規化して記録（失敗時は data_quality に理由）
  ↓
AI (performance-analyst): 前日投稿の簡易振り返りを作成
  ↓
翌朝: morning-strategy-council（growth-strategist / council-chair）が
      「Yesterday status summary」としてMorning Strategy Briefに反映
```

人間の作業はDの投稿URL入力1回のみで変わらない。**変わるのはDの後**であり、従来「人間がXを開いて5項目を目視で拾う」作業を、「AIが取得を試み、取得できたものはそのまま使い、取得できなかったものだけ人間に軽く尋ねる」構造に置き換える。

---

## B. ユーザーがやること／AI側がやること

| | 内容 |
|---|---|
| **ユーザー** | 投稿URLを`posts`シートに1回入力する（既存Dのまま、追加作業なし） |
| **ユーザー（例外時のみ）** | AIが取得できなかった項目だけ、翌朝`daily_brief.md`または`metrics_24h`シートに補完する（従来の空欄ルールを維持） |
| **ユーザー（初回セットアップのみ、日次作業ではない）** | X APIのUser Context認証を一度だけ許可する（詳細はC節） |
| **AI（x-metrics-collector）** | tweet_id抽出、post_id対応付け、API呼び出し、正規化、失敗時のnotes記録 |
| **AI（performance-analyst）** | 取得結果をもとに簡易振り返りを作成 |
| **AI（growth-strategist / council-chair）** | 翌朝Briefに「Yesterday status summary」として反映 |

---

## C. 必要なX API権限・認証条件

### 取得できるメトリクス（フィールド名はX API v2準拠。最新版は要確認）

| 区分 | フィールド | 認証要件 |
|---|---|---|
| public（誰の投稿でも取得可） | `public_metrics.impression_count` / `like_count` / `reply_count` / `bookmark_count` / `quote_count` / `retweet_count` | App-only Bearer Tokenで取得可能 |
| non-public / organic（**自分の投稿のみ**） | `non_public_metrics.impression_count`（重複だが非公開版として存在） / `user_profile_clicks` / `url_link_clicks` / `organic_metrics.engagements` | **OAuth 2.0 User Context**（投稿アカウント本人が認可したトークン）が必須。App-only Bearer Tokenでは取得不可 |

### 認証条件（重要）

- `user_profile_clicks`（＝`profile_visit_rate`算出の分子）は non-public metrics に属し、**投稿したアカウント自身のUser Context認証がなければ取得できない**
- User Context認証は、X Developer Portalでアプリを登録し、対象アカウントが一度だけOAuth認可フローを完了する必要がある（`tweet.read` / `users.read` スコープ、可能ならリフレッシュトークンで長期運用）。**これは日次作業ではなく、初回1回だけの人間の作業**（Phase 1の「4手＋例外」とは別枠のセットアップコスト）
- 認証トークンは本リポジトリのファイルに含めない。環境変数または外部のシークレット管理（今回は具体的な保管先の実装まで踏み込まない）を前提とする
- X API のレートリミットはアクセス層（Free/Basic/Pro）によって異なる。Phase 1（1日1投稿）の頻度では問題にならない想定だが、将来投稿数が増える場合は要確認

### `profile visits` と `user_profile_clicks` の関係（重要な注意点）

X管理画面のUI上に表示される「プロフィール訪問数（profile visits）」は、`user_profile_clicks`（API上のorganicメトリクス）を**近似値として使う**。ただし以下の理由で完全一致は保証されない:

- APIのメトリクス集計ロジックとUI表示の集計ロジックが同一である保証がない（ドキュメント上明記されていない）
- 集計対象期間・タイムゾーンの扱いが異なる可能性がある
- 将来X側の仕様変更で定義が変わる可能性がある

このため、`profile_visit_rate`はあくまで**近似指標**として扱い、`docs/strategy/kpi-definition.md`および`gsheets_ledger_design_2026-08-03.md`にこの注意書きを明記する（後述F参照）。

---

## D. Google Sheets側の必要列・更新ルール

`ops/reports/gsheets_ledger_design_2026-08-03.md`を本設計に合わせて改訂済み（`posts`に`tweet_id`/`selected_for_post`列を追加、`metrics_24h`をX APIフィールド名に統一し`data_quality`列を追加）。詳細は同ファイル参照。要点のみ:

- `posts.tweet_id`: `posted_url`からAIが自動抽出（URL形式 `https://x.com/{username}/status/{tweet_id}`）
- `metrics_24h`: `impression_count`/`like_count`/`reply_count`/`bookmark_count`（public、認証要件が軽い）と`user_profile_clicks`/`url_link_clicks`/`engagements`（non-public、User Context必須）を分けて扱う
- `data_quality`: `ok` / `partial` / `auth_missing` / `api_error` / `url_unresolved` / `manual`
- **空欄の2つの意味を区別する**: 人間が意図的に空欄にした場合は注記不要（既存ルール）。AIが取得を試みて失敗した場合は`data_quality`と`notes`に理由を残す（原因不明の欠測にしない）

---

## E. 失敗ケースとフォールバック

| 失敗ケース | `data_quality` | フォールバック |
|---|---|---|
| `posted_url`の形式が想定と異なり`tweet_id`を抽出できない | `url_unresolved` | notesに元URLを残し、人間に手動確認を依頼。人間がtweet_idを直接入力できる列を用意してもよい |
| User Context認証が未設定・失効している | `auth_missing` | non-public系（`user_profile_clicks`等）のみ取得断念。public系は取得を試みる（`partial`扱い） |
| API呼び出し自体が失敗（レート制限・一時的障害等） | `api_error` | notesにエラー概要を記録し、次回リトライを促す。Phase 1では自動リトライは実装せず、人間が翌朝`daily_brief.md`で確認するだけの運用に留める |
| 一部フィールドのみ取得成功 | `partial` | 取得できた項目は記録し、取得できなかった項目は空欄＋notesに理由 |
| 投稿がAPI経由で見つからない（削除・非公開化等） | `api_error`（notesに「投稿が見つからない」と明記） | 人間に投稿状況の確認を促す |

いずれのケースも、**「取得を試みたが失敗した」ことが分かる状態を残す**のが原則。人間が空欄を見たときに「まだ取りに行っていない」のか「取りに行ったが失敗した」のかを区別できるようにする。

---

## acquisition modeのKPIとの接続（技術論点8）

- 主KPI `impressions`: `metrics_24h.impression_count`（public、取得しやすい）
- 主KPI `profile_visit_rate`: `user_profile_clicks / impression_count`（non-public、User Context必須。近似値である旨を明記）
- 副KPI `follow_rate`: 引き続きAPI経由での取得対象外（X APIの投稿単位メトリクスに「フォロー数」はないため）。Phase 1同様、アカウント全体のフォロワー純増数を参考値として人間が記録する運用を維持する
- `docs/strategy/kpi-definition.md`の`profile_visit_rate`定義に、`user_profile_clicks`近似値である旨の注記を追加することを推奨する（本ラウンドでは提案に留め、必要なら次回反映）

---

## Morning Strategy Councilでの参照方法（技術論点9）

- `growth-strategist`が「前日実績」を見る際、`data_quality`は`ops/logs/metrics_snapshots.csv`には存在しない（`schemas/metrics_snapshot.schema.json`にフィールドがなく、2026-08-06に判明・修正した記録先バグ）。参照先は`ops/reports/daily_brief.md`の「24時間後実績記録」表（暫定評価フェーズ中の実質的な記録先）、またはGoogle Sheets移行後は`metrics_24h`シートとし、`data_quality`が`ok`/`partial`/`manual`の行のみを実績として扱う（`auth_missing`/`api_error`の行は「未取得」として扱い、確定した傾向として使わない）
- `council-chair`はMorning Strategy Briefの「Yesterday status summary」に、取得できたメトリクスと`profile_visit_rate`近似値を反映する。取得が`partial`だった場合はTL;DRに「一部データ未取得」と明記する

---

## 処理ステップ（設計、実装は別途）

1. 投稿URLの受け取り（`posts.posted_url`、人間が入力— 既存D）
2. URLから`tweet_id`を抽出（正規表現。Google Sheets上なら`REGEXEXTRACT`、将来スクリプト化するなら軽量な文字列処理）
3. `tweet_id`と`post_id`の対応付け（`posted_url`が入力された行がそのまま対応行のため、追加の突合処理は不要）
4. 24時間後実行ジョブの登録（下記「実装オプション」参照。Phase 1では人間トリガーが現実的）
5. X API認証（User Context前提）の必要条件確認（未設定なら`auth_missing`で処理を打ち切る）
6. メトリクスAPI呼び出し（`public_metrics`は常に試行、`non_public_metrics`/`organic_metrics`は認証がある場合のみ）
7. 正規化して`metrics_24h`（Google Sheets移行後）または`ops/reports/daily_brief.md`の「24時間後実績記録」表（現在の暫定評価フェーズ）に保存する。**`ops/logs/metrics_snapshots.csv`は`data_quality`/`notes`を保持できない（2026-08-06修正）ため、この用途では使わない**
8. 失敗時は`data_quality`/`notes`に反映（E節参照）
9. 翌朝Brief用の要約データとして`performance-analyst`→`growth-strategist`/`council-chair`に引き継ぐ

### 将来スクリプト化する場合の構造イメージ（雛形・未実装）

```
scripts/collect_24h_metrics.py（イメージ。実際には作成していない）

def extract_tweet_id(posted_url: str) -> str | None:
    # 正規表現で https://x.com/{user}/status/{tweet_id} から tweet_id を抽出
    ...

def fetch_metrics(tweet_id: str, user_context_token: str | None) -> dict:
    # public_metrics は常に取得を試みる
    # non_public_metrics / organic_metrics は user_context_token がある場合のみ
    ...

def normalize_and_write(post_id: str, metrics: dict, quality: str, notes: str) -> None:
    # metrics_24h シート（または daily_brief.md の「24時間後実績記録」表）に1行追記
    # metrics_snapshots.csv は data_quality/notes を持たないため対象外（2026-08-06修正）
    ...
```

このスクリプト自体は今回作成していない（設計イメージの提示のみ）。実装に進む場合は、認証情報の管理方法・実行トリガー（下記B案）の決定が先に必要。

---

## 実装オプションの比較（A/B/C）

| | A. 最小実装 | B. 1段進んだ実装 | C. 将来構想 |
|---|---|---|---|
| URL入力 | 人間が手入力 | 人間が手入力 | **不要**（投稿APIから自動連携） |
| 24h後トリガー | 人間が翌朝手動起動、またはGoogle Apps Scriptの time-driven trigger | 真の自動トリガー（cron/スケジューラ、失敗時リトライあり） | 完全自動 |
| Sheets書き込み | 自動 | 自動 | 自動 |
| 朝会向け要約 | performance-analystが手動生成 | 自動生成 | 完全自動生成・提案まで |
| 実装コスト | 低（hooks不要、Sheets関数＋簡易スクリプトのみ） | 中（スケジューラ・リトライ機構が必要） | 高（投稿API連携・hooks本実装が必須） |
| 今回のCLAUDE.md制約との整合 | ○（hooks本実装不要） | △（スケジューラ部分がhooks寄り） | ×（投稿自動化・hooks本実装が前提、現行方針と抵触） |

**Phase 1時点で最も現実的な実装案は A（最小実装）。** 理由: hooksの本実装を要求せず、CLAUDE.mdの現行方針と矛盾しない。「人間が翌朝、記録済みのURLに対して取得処理を1回実行する（またはGoogle Apps Scriptの時間主導トリガーで自動化する）」だけで、Sheetsへの正規化・失敗時のフォールバックまでは設計どおり動かせる。Bはスケジューラ実装が伴うため次段階、Cは投稿自動化そのものが前提になるため現行方針とは別枠の議論。

---

## F. 今すぐやる設計修正

1. `.claude/agents/x-metrics-collector.md`の新設（メトリクス取得ロジックの担当を明確化）
2. `ops/reports/gsheets_ledger_design_2026-08-03.md`の列設計改訂（本ドキュメントD節参照）
3. `.claude/agents/logger.md` / `docs/roles/logger.md`: `posted`確定後にx-metrics-collectorへ引き継ぐ流れを明記
4. `.claude/agents/performance-analyst.md`: `data_quality`列を踏まえた分析ルールに更新
5. `.claude/agents/growth-strategist.md`: 前日実績の参照先と`user_profile_clicks`近似値の注意を追記
6. `.claude/agents/mode-orchestrator.md`: 引き継ぎ先にx-metrics-collectorを追加
7. `templates/morning_strategy_brief.md`: 「Yesterday status summary」の生成元を明記
8. `ops/reports/phase1_acquisition_launch_spec_2026-08-03.md`: 24時間後実績の「例外」欄を半自動フロー前提に更新

## G. 将来の完全自動化に必要な追加条件

1. 24時間後トリガーの自動実行機構（cron/スケジューラ、またはClaude Codeのスケジュール実行機能） — 今回は設計のみで実装せず
2. X APIのUser Context認証トークンの安全な管理・自動更新（リフレッシュトークン運用） — 認証情報そのものは本リポジトリに含めない
3. 投稿自体のAPI化（Xへの自動投稿） — 現行のCLAUDE.md方針（本番投稿自動化はまだ行わない）と抵触するため、これが解禁されない限りCの完全自動化構想には進めない

---

## 最後に整理

### 1. この半自動化が実現すると、ユーザーの手数が何から何に減るか

**現状**: 投稿URL入力（1回）＋翌日Xを開いて5項目を目視回収（毎日）
**半自動化後（A案）**: 投稿URL入力（1回）のみ。翌日の数値確認は、AIが取得できた場合は人間の作業ゼロ、取得できなかった項目だけ人間に確認を求める（従来の「毎回5項目全部見る」から「取得漏れがあれば一部だけ見る」に縮小）

### 2. `profile visits` と `user_profile_clicks` の関係の注意点

`user_profile_clicks`はAPI上の非公開メトリクスであり、X管理画面UIの「プロフィール訪問数」の近似値として扱う。集計ロジックの完全一致は保証されないため、`profile_visit_rate`は「参考指標」として扱い、Phase 1の意思決定（Week 2以降のA/Bテスト判定等）でも「近似値である」ことを前提にした解釈をする。

### 3. Phase 1時点で最も現実的な実装案

**A（最小実装）。** hooks本実装を要求せず、現行のCLAUDE.md方針と矛盾しない範囲で「URL入力→（人間トリガーまたは簡易スケジューラ）→API取得→Sheets正規化→失敗時フォールバック」まで設計・準備できる。

### 4. API制約が厳しい場合の暫定代替案

- non-public metrics（`user_profile_clicks`等）がAPIプランの制約で取得できない場合、public metrics（`impression_count`/`like_count`/`reply_count`/`bookmark_count`）のみ自動取得に切り替え、`profile_visit_rate`の算出は引き続き人間の手動入力（X Analytics画面からのコピー）に頼る「部分自動化」とする
- API自体に一切アクセスできない場合は、現行Phase 1の完全手動運用（空欄＝未取得ルール）にフォールバックする。設計自体は無駄にならず、API利用が可能になった時点でそのまま適用できる
