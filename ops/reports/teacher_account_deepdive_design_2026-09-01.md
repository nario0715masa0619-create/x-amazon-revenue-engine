# teacher輩出アカウントの深掘り収集（設計文書、2026-09-01）

**本文書は調査・設計提案のみであり、実装は行っていない。commit対象は本ファイルのみ。**
**Gate A / thresholds / shipping decision、`_apply_engagement_gate()`本体、既存の日次ワークフロー
（`.github/workflows/phase1_daily_collection.yml`）本体には一切触れていない。**

---

## フェーズ1: API制約調査の結果

### 1-1. `search/recent`（現行）と`users/:id/tweets`（深掘り収集の候補）の比較

Web検索（docs.x.com、X Developer Community、2026年時点の解説記事）で確認できた範囲を、
本リポジトリの現行実装（[scripts/x_api_phase1_collect.py:37-39](../../scripts/x_api_phase1_collect.py)）
と対比する。

| 項目 | `GET /2/tweets/search/recent`（現行） | `GET /2/users/:id/tweets`（深掘り収集の候補） |
| --- | --- | --- |
| 遡及範囲 | **直近7日間のみ**（日数上限。7日より前の投稿はヒットしない） | **直近3,200件のツイート**（件数上限。投稿頻度次第で数ヶ月〜数年分に相当しうる） |
| レート制限（docs.x.com一般表記、階層非依存） | Per App 450/15min、Per User 300/15min | Per App 10,000/15min、Per User 900/15min |
| 従量課金（pay-per-use、2026-02以降のデフォルト） | 1件読み取り＝$0.005 | 同じく1件読み取り＝$0.005（エンドポイントによる単価差はない） |
| 1リクエスト最大件数 | `max_results`最大100（現行コードは10〜20を使用） | `max_results`最大100、pagination tokenで3,200件まで遡及可能 |
| クエリ構文 | キーワード・OR式・除外語等が使える（現行運用の主軸） | クエリ指定不可。指定した1アカウントの投稿を新しい順に返すのみ。絞り込みは`start_time`/`since_id`等の期間・ID指定に限る |
| 用途の性質 | 「未知のアカウント」からの広域発見 | 「既知のアカウント」の過去投稿の深掘り |

**最も重要な違い**: `search/recent`は日数で頭打ちになる（7日）のに対し、`users/:id/tweets`は
件数で頭打ちになる（3,200件）。今回の課題（広域キーワード収集を何度実行しても新規teacher候補が
0件）は、「7日という窓の狭さ」自体が原因ではなく「キーワードで初めて発見できるアカウントの
新規性」に依存する構造だと考えられるため、既知の反応良好アカウントについては
`users/:id/tweets`で過去に遡って深掘りする方が、繰り返しキーワード検索するより新規候補を
見つけやすい可能性が高い。

Sources:
- [X API Rate Limits](https://docs.x.com/x-api/fundamentals/rate-limits)
- [Is Search Recent Posts available on Free Tier? - X Developers](https://devcommunity.x.com/t/is-search-recent-posts-available-on-free-tier/247462)
- [Users/:id/tweets endpoint not reaching 3,200 cap on some accounts - X Developers](https://devcommunity.x.com/t/users-id-tweets-endpoint-not-reaching-3-200-cap-on-some-accounts/267433)
- [X API pay-per-usage pricing and credits](https://docs.x.com/x-api/getting-started/pricing)

### 1-2. 現在の`X_BEARER_TOKEN`でこのエンドポイントにアクセス可能か

**結論: 要確認（契約プラン名がリポジトリ内のどこにも記載されていないため断定できない）。**

判断材料として確認した事実:

- 認証方式の観点では、`users/:id/tweets`もApp-only Bearer Token（現行`search/recent`と同じ
  認証方式）で呼び出し可能なエンドポイントであり、[.env.example](../../.env.example)の
  `X_BEARER_TOKEN`をそのまま使い回せると推測される（追加のOAuth 2.0 User Contextトークンは
  不要と見込まれる）。
- 契約プラン名（Free/Basic/Pro/pay-per-use等）は、`.env.example`にも本リポジトリのどの設計文書
  にも記載がない。同種の先行調査（[ops/reports/broad_teacher_collection_design_2026-09-01.md:11-16](../../ops/reports/broad_teacher_collection_design_2026-09-01.md)）
  でも同じ結論（「不明」）に達している。
- **本調査で新たに判明した事実**: X社は2026年2月6日付けで、新規契約者向けデフォルトを
  従量課金（pay-per-use）モデルへ全面移行した（Free tierは新規には提供されなくなり、
  既存Free tierユーザーは自動移行された）。本プロジェクトの`.env.example`・X API最小設計文書
  （[ops/reports/x_api_minimal_design_2026-08-14.md](../../ops/reports/x_api_minimal_design_2026-08-14.md)）
  の日付は2026-08-14であり、これは2026年2月の制度変更**後**にあたる。したがって、本プロジェクトが
  2026-08-14前後に新規にX API契約したのであれば、pay-per-use（Free tierなし）である可能性が
  高いと推測される。ただし、それ以前から継続している契約（レガシーBasic/Pro等）である可能性を
  排除する材料はリポジトリ内に存在しない。
- pay-per-use契約であれば、「エンドポイントごとのアクセス可否」という旧来の階層区分（Free tier
  では他者のタイムライン取得不可、等）の概念自体が該当しなくなり、`users/:id/tweets`が使えない
  可能性は低いと推測される。一方、レガシーFree tier相当のまま据え置かれている場合はこの限りで
  はなく、その場合は本設計全体が実行不能になる。

**実装着手前に、人間が developer portal もしくは請求ダッシュボードで契約プラン名を実際に
確認することを必須の前提条件とする。**

Sources:
- [Specifics about the new free tier rate limits - X Developers](https://devcommunity.x.com/t/specifics-about-the-new-free-tier-rate-limits/229761)
- [X API pay-per-usage pricing and credits](https://docs.x.com/x-api/getting-started/pricing)

### 1-3. 「一度teacherを出したアカウントを無期限に監視し続ける」場合の収集コスト増加見積もり

現行の日次運用（[.github/workflows/phase1_daily_collection.yml](../../.github/workflows/phase1_daily_collection.yml)、
6クエリ×`max_results`20＝最大120reads/日）を基準に、監視対象アカウントが5/10/20件の場合の
追加コストを、**契約プランが不明なため2つのシナリオ**で試算する。

#### シナリオA: pay-per-use（$0.005/read）の場合

| 監視対象数 | 初回深掘り（1アカウントにつき直近100件取得、one-time） | 以後の呼び出し回数/日 | 想定新規投稿数/日（仮定: 1アカウントあたり1〜5件/日） | 従量課金/日（以後） | 従量課金/月（以後） |
| --- | --- | --- | --- | --- | --- |
| 5 | $2.50（one-time） | 5 calls | 5〜25 reads | $0.025〜$0.125 | 約$0.75〜$3.75 |
| 10 | $5.00 | 10 calls | 10〜50 reads | $0.05〜$0.25 | 約$1.5〜$7.5 |
| 20 | $10.00 | 20 calls | 20〜100 reads | $0.10〜$0.50 | 約$3〜$15 |

現行6クエリ運用の従量課金は最大$0.60/日（≒$18/月）であり、20アカウント監視を足しても
合計は月$50を大きく下回る。pay-per-use契約の上限（2,000,000 reads/月）に対しても、
現行＋深掘り20アカウントの合計は月あたり数千reads程度（120×30＋100×20＋60×30≒6,600reads）
に過ぎず、0.5%未満で無視できる規模である。

**未確認事項**: 新規投稿が0件だった日の呼び出し（`since_id`で差分が無い場合）にも
最低課金が発生するか、投稿0件なら課金も0件かは、公式ドキュメントの記述からは断定できない。
上記試算は「返却件数分のみ課金される」前提であり、実際と異なる可能性がある。

#### シナリオB: レガシー階層プラン（Basic/Pro等、15分窓のリクエスト数上限）の場合

`users/:id/tweets`の一般公開レート制限（Per User 900/15min、Per App 10,000/15min）を基準にすると、
1日1回×20アカウント＝20 calls/日は、900回/15分という上限に対して極めて小さく、現行の
search/recent運用（6 calls/日 vs 300回/15分）と同様、レート制限が実運用上のボトルネックに
なる可能性は低いと見込まれる。ただし、この一般表記が実際の契約プランにそのまま適用される
保証はない（1-2節参照）。

#### コスト増加の性質についての結論

金額・呼び出し回数いずれの試算でも、**監視対象アカウント数に対して線形にしか増えない**
（1アカウント追加＝1日1回の差分チェック呼び出しが1回増えるだけ）ため、20件程度までの規模では
コストそのものは大きな問題にならないと見込まれる。真のコスト増加リスクは、日々の増分チェック
コストではなく、**監視対象アカウントの登録数が「増える一方で減らない」場合の長期的な累積**
（ワークフロー実行時間の増加、`ops/data/watched_accounts.jsonl`の肥大化）にある。これが
フェーズ2-3（卒業/継続条件）を設計する必要性の裏付けになる。

---

## フェーズ2: 設計提案の要約

実装は行っていない。以下はすべて設計提案であり、着手には別途人間の承認が必要。

### 2-1. アカウント登録の仕組み

**起点**: `x_api_phase2_classify.py`の`_apply_engagement_gate()`を通過し最終的に
`pre_teacher_candidate`となったレコード（`author_id`を含む）。既存の`_classify()`/
`_classify_core()`/`_apply_engagement_gate()`本体には一切手を入れず、classify.pyの出力
ファイル（`outputs/x_api_phase2/pre_teacher_candidate.json`）を**読み取り専用で参照するだけの
独立した後段ステップ**として追加する（[scripts/accumulate_phase1_collection.py](../../scripts/accumulate_phase1_collection.py)
が既存パイプラインの出力を読み取り専用で参照し別ファイルへ追記するのと同じ設計パターン）。

**永続化を2層に分離する**（[scripts/topic_group_state.py](../../scripts/topic_group_state.py)の
永続化パターンを参考にしつつ、「テーマ」と「アカウント」の性質差を踏まえて設計し直したもの。
理由は2-3節で詳述）:

1. `ops/data/watched_accounts.jsonl`（新設・追記専用の**登録イベントログ**）
   - ユーザー指定どおり、[scripts/cumulative_post_store.py](../../scripts/cumulative_post_store.py)の
     `post_id`ベース重複排除と同じ設計思想を`author_id`版として複製実装する（既存関数を
     書き換えるのではなく、同じ設計パターンの別モジュール`scripts/watched_account_store.py`
     （新設案）として持つ）。
   - 新規の`author_id`が`pre_teacher_candidate`として初めて観測された時のみ1行追記する
     （2回目以降は同じ`author_id`でも追記しない＝post_id dedupと同じ挙動）。
   - フィールド案: `author_id`、`first_seen_as_teacher_post_id`、`first_seen_as_teacher_query_source`、
     `registered_at`。
   - **本文（text）は保存しない**——[cumulative_post_store.py:14-24](../../scripts/cumulative_post_store.py)
     と同じ理由（本リポジトリはpublicであり、`.gitignore`が`outputs/x_api_phase1/`を実データ・
     投稿本文を含みうるためコミット対象外としている既存方針を踏襲する）。
2. `ops/data/watched_account_state.json`（新設・**可変の監視状態ストア**）
   - `topic_group_state_store.json`と同じ永続化パターン（`author_id`をキーにした辞書、
     `json.dump()`で毎回全体を書き換える）。
   - フィールド案: `watch_status`（`active`/`graduated`、2-3節参照）、`teacher_count`
     （累計`pre_teacher_candidate`数）、`first_registered_at`、`last_teacher_at`、
     `last_deepdive_checked_at`、`consecutive_unproductive_deepdive_runs`、
     `last_deepdive_since_id`（次回増分チェック用のカーソル）。

**2層に分ける理由**: (1)はユーザー指定の「post_idと同様の重複排除を持つ追記型ストア」という
要件をそのまま満たす不変な監査ログである。一方、卒業/継続判定にはカウンタの増減・状態遷移が
必要であり、これを追記専用JSONLで表現しようとすると「カウンタを増やす」操作が実質的に
全件読み直して差分計算するのと同義になってしまう。`topic_group_state.py`が採用している
「キー付き辞書を都度書き換える」方式（2)のほうが素直であるため、役割を分離した。

### 2-2. 深掘り収集の仕組み

**新設スクリプト案**: `scripts/x_api_deepdive_collect.py`（`x_api_phase1_collect.py`と同じ
requestsベースの実装パターンを踏襲）。`QUERIES`配列の代わりに`watched_account_state.json`から
`watch_status=="active"`のアカウントの`author_id`一覧を読み込み、各アカウントについて
`GET /2/users/:id/tweets`を1回ずつ呼び出す。`since_id`パラメータに`last_deepdive_since_id`
（無ければ未指定＝直近100件）を渡すことで、2回目以降は新規投稿のみを取得する増分収集とする。

**出力先の分離**: 既存の`outputs/x_api_phase1/`ではなく、新規ディレクトリ`outputs/x_api_deepdive/`
（`.gitignore`に追加）に同フォーマットで書き出す。日次キーワード収集と深掘り収集を別
ワークフローとして走らせた場合の書き込み競合を避けるため。

**累積ストアへの合流**: 深掘り収集で取得した投稿を、既存の`cumulative_post_store.append_new_posts()`
（**変更不要**、汎用のpure function）経由でそのまま`ops/data/x_api_phase1_cumulative.jsonl`へ
追記する。post_id基準の重複排除は関数側で自動的に効くため、日次キーワード収集と深掘り収集の
両方から同じ投稿が来ても二重登録されない。ユーザー指定の「既存の累積ストアに合流させる」を
そのまま満たす。

**Phase 2分類パイプラインへの合流（要検討事項として発見した課題）**:

`x_api_phase2_classify.py`は入力パス（`outputs/x_api_phase1/merged_deduped.json`、
[scripts/x_api_phase2_classify.py:31](../../scripts/x_api_phase2_classify.py)）・出力ディレクトリ
（`outputs/x_api_phase2/`、同32行目）が**モジュールレベルの定数としてハードコード**されており、
CLI引数や環境変数での上書き機構が現状存在しない。同様に`post_generation_pipeline.py`も
`outputs/x_api_phase2/pre_teacher_candidate.json`を固定パスで読む
（[scripts/post_generation_pipeline.py:118,2274](../../scripts/post_generation_pipeline.py)）。

日次ワークフローと深掘りワークフローを別々のGitHub Actionsとして走らせた場合、両方が
同じ固定パスへ書き込むと、後から走った方が前者の出力を上書きし、`post_generation_pipeline.py`
が読む`pre_teacher_candidate.json`の内容が意図せず失われるリスクがある。

**提案する最小限の追加（実装は行わず提案のみ）**: `x_api_phase1_collect.py`と
`x_api_phase2_classify.py`の両方に、入出力パスを上書きできる環境変数
（例: `PHASE1_OUTPUT_DIR`、`PHASE2_INPUT_PATH`、`PHASE2_OUTPUT_DIR`）を追加する。
**未設定時のデフォルト値は既存のハードコードパスと完全に同じ**にすることで、既存の日次
ワークフローの挙動は一切変わらない（後方互換・`phase1_daily_collection.yml`本体は無変更でよい）。
これは分類ロジック（`_classify()`/`_classify_core()`/`_apply_engagement_gate()`）を一切変更しない
純粋なI/O経路のパラメータ化であり、「判定ロジックは完全に同一のものを使う、新しい判定ロジックを
作らない」というユーザー指定の制約とは矛盾しないと判断したが、**この判断の妥当性自体は
人間の確認が必要**（未解決事項参照）。

深掘りワークフローはこの環境変数を使って`x_api_phase2_classify.py`を
`PHASE2_INPUT_PATH=outputs/x_api_deepdive/merged_deduped.json PHASE2_OUTPUT_DIR=outputs/x_api_deepdive_phase2/`
のように呼び出す。分類ロジック本体は完全に同じ関数がそのまま実行される。

深掘り側のPhase 2出力（`outputs/x_api_deepdive_phase2/pre_teacher_candidate.json`）を、
既存の`outputs/x_api_phase2/pre_teacher_candidate.json`（`post_generation_pipeline.py`が読む
正本）へ**追記・重複排除（post_id基準）でマージする**、小さな新設マージステップ
（`scripts/merge_deepdive_teacher_candidates.py`、新設案）を設ける。これも新しい「判定」
ロジックではなく、既に分類済みの結果を集約するだけの機械的な処理である。

**別ワークフロー**: `.github/workflows/phase1_deepdive_collection.yml`（新設）。既存の
`phase1_daily_collection.yml`本体は変更しない。スケジュールは日次キーワード収集
（`cron: "0 21 * * *"`）と時間帯をずらす（例: `"0 22 * * *"`、1時間後）ことで、
`ops/data/`配下ファイルへのgit commit競合を避ける。

### 2-3. 監視対象からの卒業/継続条件

**`topic_group`のcooldown/retire思想がそのまま流用できるかの検討（ユーザー指定どおり検討）**:

`topic_group`のcooldown/retireは「**同じテーマの使い回しを防ぐ**」ための仕組みであり、
「投稿（publish）」というイベントを起点に、一定期間そのテーマを候補プールから外す（cooldown）、
または致命的な結果（`loss`）なら二度と使わない（`retired`）という設計である
（[scripts/topic_group_state.py:298-333](../../scripts/topic_group_state.py)）。対象は
「1回使ったら休ませる／使い切ったら捨てる消費型リソース」であり、`topic_retry_budget`は
「そのテーマで何回投稿を試みたか」を消費する概念である。

監視対象アカウントは性質が異なる。「アカウントを1回使ったら休ませる」という消費行為ではなく、
「継続的に定期チェックする対象を維持するかどうか」という**購読（subscription）型**の管理である。
`retry_budget`のように「チェックした回数」を消費に見立てても、チェック自体はコスト的に軽微
（フェーズ1-3参照）であり、「予算が尽きたから見るのをやめる」という理由付けには馴染まない。

**結論: `topic_group`の仕組みをそのまま流用するのは適切ではない**。「状態を持たせ、状態遷移を
明示的に管理する」という設計思想は踏襲しつつ、遷移条件はアカウント監視の実態
（「最近teacherを出しているか」）に合わせて作り直す。

**提案する状態遷移（新設、`topic_group`同様に暫定値・要人間確認）**:

- `active`: 新規登録直後の初期状態。深掘り収集の対象。
- `graduated`（仮称。実質は「卒業」というより「休止」に近い）: `consecutive_unproductive_deepdive_runs`
  （深掘りチェックで新規`pre_teacher_candidate`が0件だった連続回数）が閾値（暫定案: N=10回、
  または30日相当）に達したら`graduated`へ遷移し、深掘り収集の対象から外す（＝API呼び出し
  コストを止める）。
- `active`への復帰条件: `graduated`のアカウントが、既存の**日次キーワード収集**側で再び
  `pre_teacher_candidate`として観測された場合、自動的に`active`へ復帰させる。この処理は
  2-1節のアカウント登録処理と同一の入口関数（`register_or_reactivate_watched_account()`、
  新設案）で「新規登録」と「復帰」の両方を扱う設計とする。
- **完全な`retired`（二度と復帰しない状態）は設けないことを提案する**。理由:
  `topic_group`の`retired`は「投稿してlossだった」という明確な失敗シグナルに基づくが、
  アカウント監視の場合「しばらくteacherを出していない」ことは投稿頻度の波・アルゴリズムの
  タイミング等による一時的な沈黙である可能性が高く、テーマの`loss`ほど確定的な失敗とは言えない。
  完全排除より、いつでも再エントリーできる休止のほうが安全側（見逃しを増やさない側）の設計だと
  考える。

閾値の具体値（N回・何日）は本設計では暫定案に留め、**人間の確認が必要**と明記する
（`topic_group_lifecycle_design`の既存の書き方（暫定値＋要人間確認）を踏襲した）。

### 2-4. API制約内に収まる実行頻度・監視対象数の上限案

フェーズ1-3の試算（pay-per-use前提なら20アカウントでも追加は月$15程度、レガシー階層プラン
前提でも20回/日は900回/15分の上限に対して十分小さい）を踏まえ、**当面の上限案として
20アカウント・1日1回チェック**を提案する。ただし根拠はコスト・呼び出し回数の試算のみであり、
実際の契約プラン（フェーズ1-2、要確認）次第では上限を引き上げられる可能性がある。逆に
レガシーFree tier相当で`users/:id/tweets`自体にアクセスできない場合はこの設計全体が実行不能に
なるため、**実装着手前の契約プラン確認を必須の前提条件とする**。

実行頻度は日次キーワード収集（`cron: "0 21 * * *"`）と別workflowとして1時間ずらした時間帯
（`cron: "0 22 * * *"`）を提案する。

---

## 未解決事項・要判断事項

1. **X APIの契約プラン（Free/Basic/Pro/pay-per-use等）がリポジトリ内のどこにも記載がなく、
   本調査では確定できなかった。** `users/:id/tweets`へアクセス可能かどうか、フェーズ1-3の
   コスト試算のどちらのシナリオが該当するかは、この確認が済むまで確定しない。**実装着手前に
   人間がdeveloper portalまたは請求ダッシュボードで確認することを必須の前提条件とする。**
2. **`x_api_phase1_collect.py`・`x_api_phase2_classify.py`への入出力パス上書き環境変数の追加は、
   「判定ロジックは完全に同一のものを使う、新しい判定ロジックを作らない」という制約の範囲内
   （純粋なI/O経路のパラメータ化であり判定ロジック自体には触れない）と判断したが、この判断の
   妥当性自体は人間の確認が必要。** 許容されない場合、深掘り収集用にPhase 2分類ロジックを
   別途複製する必要が生じ、「完全に同一のロジックを使う」という要件と矛盾するため、別の
   マージ方式を再検討する必要がある。
3. **`graduated`への遷移閾値（連続何回・何日で休止するか）、および`active`復帰の具体的な
   トリガー条件は暫定案に留めた。** 具体値の確定は人間の判断が必要。
4. **初回深掘り時に取得する投稿件数（直近100件で十分か、3,200件まで遡るべきか）は暫定
   （100件）とした。** 確定は人間判断が必要。
5. **新規投稿が0件だった日の増分チェック呼び出しにも課金が発生するか（pay-per-use契約の場合）は、
   公式ドキュメントの記述だけでは断定できなかった。** フェーズ1-3のコスト試算に影響しうるため、
   実装前に確認が望ましい。
6. **設計の射程外の論点として一点記録する**: 「一度でもteacherを出したアカウント」を継続的に
   深掘り監視する設計は、当該アカウントの投稿者が意図していない形での継続的な注目・追跡に
   あたりうる。公開投稿をAPI経由で読むこと自体はX社の利用規約上想定された利用形態であり
   技術的な障壁ではないが、この設計方針自体（不特定多数の広域収集から、特定アカウントの
   継続監視へと性質が変わる点）の妥当性については、本調査の範囲外として人間の判断に委ねる。

---

## 参照した既存コード・文書

- [scripts/x_api_phase1_collect.py](../../scripts/x_api_phase1_collect.py) — 現行Phase 1収集
- [scripts/x_api_phase2_classify.py](../../scripts/x_api_phase2_classify.py) — `_apply_engagement_gate()`、`_classify()`
- [scripts/cumulative_post_store.py](../../scripts/cumulative_post_store.py) — post_idベース追記型ストアの既存パターン
- [scripts/accumulate_phase1_collection.py](../../scripts/accumulate_phase1_collection.py) — 既存パイプライン出力を読み取り専用参照する後段ステップの既存パターン
- [scripts/topic_group_state.py](../../scripts/topic_group_state.py) — 可変状態ストアの既存パターン、cooldown/retire実装
- [.github/workflows/phase1_daily_collection.yml](../../.github/workflows/phase1_daily_collection.yml) — 既存の日次ワークフロー（本設計では変更しない）
- [ops/reports/broad_teacher_collection_design_2026-09-01.md](../../ops/reports/broad_teacher_collection_design_2026-09-01.md) — 先行するX API制約調査（契約プラン不明という同一の結論）
- [ops/reports/topic_group_lifecycle_design_2026-08-31.md](../../ops/reports/topic_group_lifecycle_design_2026-08-31.md) — cooldown/retire思想の元設計
