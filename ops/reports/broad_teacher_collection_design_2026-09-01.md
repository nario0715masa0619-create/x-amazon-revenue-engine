# teacher収集をジャンルレベルの広い網に再設計する（設計文書、2026-09-01）

**本文書は設計提案のみであり、実装は行っていない。commit対象は本ファイルのみ。**

---

## フェーズ1: 制約調査の結果

### 1. X APIのプラン・レート制限・月間クエリ上限

**不明（リポジトリ内に具体的なプラン名・数値上限の記載なし）。**

- `.env.example`（23-28行目）は`X_BEARER_TOKEN`（App-only認証）の設定方法のみを記載し、プラン名（Free/Basic/Pro等）や月間クエリ上限の記載はない。
- [ops/reports/x_metrics_semiauto_design_2026-08-03.md:61](../../ops/reports/x_metrics_semiauto_design_2026-08-03.md) に「X API のレートリミットはアクセス層（Free/Basic/Pro）によって異なる。Phase 1（1日1投稿）の頻度では問題にならない想定だが、将来投稿数が増える場合は要確認」という記載があるが、**実際にどの層を契約しているかは明記されていない**。
- コード側（[scripts/x_metrics_collector/x_api_client.py:65](../../scripts/x_metrics_collector/x_api_client.py)、[ops/reports/x_api_smoke_test_notes.md:43](../../ops/reports/x_api_smoke_test_notes.md)）は`429`エラーへの事後対応（エラーメッセージ記録・人間へのリトライ促し）のみを実装しており、事前の呼び出し数トラッキング・予算管理の仕組みはコード上どこにも存在しない。
- 参考情報（リポジトリ外の一般知識、未確認・要人間確認）: X API v2の`search/recent`エンドポイントは無料（Free）プランでは利用できず、最低でもBasic以上の有料プランが必要というのが2026年時点の一般的な仕様である。本リポジトリで実際に`search/recent`呼び出しが成功している（`ops/reports/x_api_smoke_test_notes.md`等に成功記録あり）ことから、少なくともBasic相当以上の契約がある可能性が高いが、**契約プラン名・月間上限は本調査では確認できなかった**。

### 2. 現行18クエリの実行頻度

**コード上に定義された自動スケジュール（cron等）は存在しない。人間/AIオペレーターによる手動起動であり、固定の日次・週次頻度は規定されていない。**

- `scripts/x_api_phase1_collect.py`自体に、スケジューリング・頻度に関する記述は一切ない（`daily`/`weekly`/`cron`等のキーワードで検索しても該当箇所なし）。使い方は`python scripts/x_api_phase1_collect.py`という手動実行コマンドのみ（同ファイル19-20行目）。
- 実行履歴（`outputs/x_api_phase1/run_summary.json`の`run_started_at`、および`ops/reports/`配下の各設計文書の日付）から確認できる実際の実行日: 2026-08-15、08-16、08-27（Round1/Round2として同日に複数回）、08-31。**約2週間の間に不定期に5〜6回程度、各mainline/research runサイクルのタイミングで手動起動されている**——固定の「1日1回」「週次」ではない。
- なお`ops/reports/x_metrics_semiauto_design_2026-08-03.md:61`にある「Phase 1（1日1投稿）」は投稿（publish）の頻度についての記述であり、本Phase 1収集スクリプトの実行頻度とは別物である。

### 3. X API検索クエリのOR演算子・複数語句の1クエリ集約

**確認済み（Web検索）。OR演算子は大文字`OR`で使用し、`( )`によるグループ化が可能。1クエリあたりの文字数上限は従量課金（pay-per-use）契約で512文字、Enterprise契約で4,096文字。**

- 例: `("national hockey league" OR "NHL" OR "league") AND ("stick" OR "puck" OR ...)`のように、複数の同義語・カテゴリ語を`OR`でまとめ、`( )`でグループ化した上で他の条件とスペース区切り（暗黙のAND）で組み合わせられる。
- これにより、現行のように「対象語×文脈語」の組み合わせごとに個別クエリを用意する必要はなく、**同義語・カテゴリ語群を1クエリのOR式にまとめることで、呼び出し回数を増やさずにカバー範囲を広げられる**。
- Sources: [Recent Search Quickstart](https://docs.x.com/x-api/posts/search/quickstart/recent-search), [Search operators | Docs | X Developer Platform](https://developer.x.com/en/docs/x-api/v1/rules-and-filtering/search-operators), [Search Operators - X Developer Platform](https://docs.x.com/x-api/posts/search/integrate/operators), [Full Archive Search API endpoint (Academic Research) - Query Character Limit](https://devcommunity.x.com/t/full-archive-search-api-endpoint-academic-research-query-character-limit/165206)

### 4. Phase 2 teacher判定のノイズ耐性

**現状確認: `pre_teacher_candidate`の判定ロジック（[scripts/x_api_phase2_classify.py:695-834](../../scripts/x_api_phase2_classify.py)の`_classify()`）は、キーワード共起ベースのtopic_fit/structure_fit/approach_value判定であり、`like_count`/`retweet_count`/`impression_count`等の数値エンゲージメント指標を分類の判定条件として直接は使用していない（該当フィールドは出力列としては保持されるが、`_classify()`内の分岐条件には登場しない）。**

- これは背景説明にある「エンゲージメント基準で判定」という前提と、コード上確認できる実装が完全には一致しない可能性を示す事実であり、本調査ではこの食い違いを解消せず、事実としてのみ報告する。teacher判定ロジック自体は「触ってはいけない領域」に指定されているため、本タスクでは一切変更を提案しない。
- 重要な発見: Phase 2のジャンル語辞書`GADGET_KEYWORDS`（[scripts/x_api_phase2_classify.py:69-72](../../scripts/x_api_phase2_classify.py)）は、**現行Phase 1クエリ（イヤホン/骨伝導のみ）よりも既に広いカテゴリを含んでいる**——`"ガジェット", "イヤホン", "スマホ", "スマホケース", "Apple Watch", "腕時計", "モバイルバッテリー", "充電器", "ケーブル", "EDC", "デバイス", "携帯性"`。つまり、**Phase 2分類器はイヤホン以外のガジェットカテゴリを正しく`topic_fit`判定できる語彙を既に持っており、ボトルネックはPhase 1収集側にしかない。** これは「Phase 2を変更せず収集入口のみ広げる」という本タスクの制約と整合しており、フェーズ2設計の前提として採用する。
- ノイズ増加リスクについて: `_classify()`には`negative_dominant`（スポーツ/恋愛/政治等の別テーマ支配を検出）・`weak_generic_only`（「40代」等の広い語のみの偶然一致をrejectへ落とす）・`aggregator_dominant`（集約bot/雑多カテゴリ列挙を検出）という、まさに「広い語で検索した際に増えるノイズ」に対応するために2026-08-15〜08-19に追加された既存のreject分岐が備わっている（同ファイル729-798行目）。ジャンルレベルの広いクエリへ切り替えた場合、これらの既存ノイズ対策分岐がこれまで以上に働く前提になるが、**実際のノイズ増加率は本調査（read-only）では実測していない**（設計提案の検証項目として後述）。
  - **2026-09-01追記（単一ゲート実装後の更新）**: 本文書作成後、teacher判定ロジックへ`_apply_engagement_gate()`という単一の出口ゲート（commit `ac5012c`）が実装され、上記のリスク評価は次のように区別すべきものとなった。
    - **解消されたリスク**: `pre_teacher_candidate`への到達経路（`_classify_core()`内のメイン交点パス・`fashion_only_but_reusable`・`gadget_only_but_reusable`等、経路数によらない）がどれであっても、`obs["observed_engagement_tier"]=="qualifying"`（実測エンゲージメントが閾値を満たす）でなければ`observe`へ格下げされる。したがって、**エンゲージメントゼロの投稿がkeyword一致のみで`pre_teacher_candidate`へ昇格すること（zero-engagement-keyword-squatting）は構造的に防止されている**。実データでのATH-PRO5MK2×骨伝導投稿（impression_count=0）の除外がこれを裏付けている。
    - **未解消のまま残るリスク**: 単一ゲートは`engagement_tier`のみを見ており、投稿内容がジャンルと実際に関連しているかは判定しない。そのため、**エンゲージメントは満たしつつジャンルと無関係な投稿（topic drift）が、`topic_fit`側の判定を偶然満たしてしまい昇格するリスクは未解消のまま残っている。** 実例として、ジェンダー格差についての社会風刺投稿（`post_id=2094194114099352021`、「40代」「小物」という語を偶然含んでいただけの投稿）が、実測インプレッション197・エンゲージメント合計16という実測値により`qualifying`となり、`fashion_gadget_intersection_detected`経由で`pre_teacher_candidate`へ昇格した事例が確認されている（GOV-20260901-ENGAGEMENT-BASED-TEACHER-01のテスト検証時に発見）。
    - **広域収集実装後の見込み**: 上記の未解消リスク（topic drift）は、収集クエリをジャンルレベルへ広げるほど発生頻度が上がると見込まれる——広いクエリは母数を増やすため、バズった無関係投稿が偶然`topic_fit`の軸共起条件を満たす確率も上がるためである。したがって、広域収集を実装する際は、単一ゲートが「エンゲージメントゼロでの誤昇格」は防いでいても「エンゲージメントを伴う話題ズレ」までは防いでいない、という前提で実データの再検証を行う必要がある。

---

## フェーズ2: 設計提案

設計文書全文（本ファイル）を`ops/reports/broad_teacher_collection_design_2026-09-01.md`として作成した。要約は以下のとおり。

### 1. ジャンルレベルの収集クエリ設計案

現行の「対象語（イヤホン）＋文脈語」型18クエリを、「年代/性別語 × ジャンル・所有/愛用語」型のOR集約クエリへ置き換える案。特定商品名・型番（イヤホン、骨伝導、ATH-PRO5MK2等）は一切使用しない。

| # | 想定layer | クエリ案 | 意図 |
|---|---|---|---|
| Q1 | gadget | `(40代 OR アラフォー) (ガジェット OR デバイス OR EDC OR 携帯性)` | ジャンル語そのもの＋Phase2 GADGET_KEYWORDSと同じ語彙で広く網をかける |
| Q2 | gadget | `(40代 OR アラフォー) (愛用 OR 手放せない OR 買ってよかった OR 使い分け)` | 商品名に依存しない「所有・愛用」を表す一般語 |
| Q3 | gadget | `(40代 OR アラフォー) (充電 OR バッテリー OR ケーブル OR 持ち歩き)` | 特定製品名を出さない機能・シーン語（複数カテゴリに横断する） |
| Q4 | fashion | `(40代 OR アラフォー) (小物 OR コーデ OR 身につける OR 着映え)` | 既存fashionクエリの延長、商品名は出さない |
| Q5 | fashion | `(40代 OR アラフォー) (バッグ OR 財布 OR 時計 OR ベルト OR メガネ)` | 装身具カテゴリの網（個別ブランド名・型番は含まない） |
| Q6 | intersection | `(ガジェット OR デバイス) (服 OR コーデ OR ファッション)` | git初期コミット時点の`服 ガジェット`クエリの精神を踏襲し、交点を直接狙う |

- 「比較」「実体験」等をAND必須語に含めない方針を維持する（[ops/reports/gadget_query_redesign_2026-08-27.md](../../ops/reports/gadget_query_redesign_2026-08-27.md)で「比較」をAND条件に含めると0件に収束すると既に実証済みのため、この教訓を引き継ぐ）。比較構造の有無の判定は既存どおりPhase 2以降に委ねる。
- 各クエリは日本語で30〜40文字程度であり、512文字制限に対して十分な余裕がある。
- `max_results`は既存の10〜20の運用パターンを踏襲する（例: 各15〜20）。

### 2. API制約内での実行可能性（呼び出し回数見積もり）

- 提案クエリは**6本**。現行の18本から**呼び出し回数を12本（67%）削減**しつつ、カバー範囲は特定商品カテゴリ限定から年代×ジャンル全体へ拡張される。
- フェーズ1で確認したとおり契約プランの数値上限は不明のため、削減方向（6クエリ）自体が安全側の設計選択となる。実行頻度も現行同様、固定スケジュールを設けず手動起動（1 mainline/research cycleあたり1回程度）を維持する前提とする。
- 具体的な月間呼び出し数の見積もりは、契約プラン確定後に人間が試算することを推奨する（本調査ではプラン自体が不明のため見積もり不可）。

### 3. teacher投稿からのtopic_group自動抽出設計

前タスク（GOV-20260901-INVESTIGATION-01/02系）で「未実装」と判明した、teacher投稿から商品名・テーマ・訴求切り口を機械的に抽出しtopic_groupとして登録する処理の設計案。

**新設関数案（実装はしない）: `topic_dedupe.py`に`propose_topic_group_from_teacher_post(source_post_id, post_text) -> dict`**

- 既存の`topic_dedupe.build_theme_profile([post_text])`（`extract_theme_components()`/`build_theme_signature()`/`build_topic_group()`をラップした既存関数、[scripts/topic_dedupe.py](../../scripts/topic_dedupe.py)）をそのまま再利用し、`theme_signature`/`topic_group`/`theme_components`を機械的に抽出する（新規ロジックを増やさず、既存のtheme_signature正規化基盤を再利用する）。
- 追加で、`theme_components`のうち最も多くヒットしたカテゴリ（product/use_case/comparison_axis等の各辞書エントリ）を`category_label`として提示する（例: 「モバイルバッテリー系」「腕時計系」）。これは人間が確認する際の一次サマリとして使う。
- 抽出結果は、既存の`topic_group_state.get_or_create_topic_group()`（[scripts/topic_group_state.py:77-97](../../scripts/topic_group_state.py)、変更なしでそのまま呼び出す）を使ってtopic_group_stateへ登録する。ただし新規作成時の初期`topic_status`は、既存の`"active"`ではなく**新設する`"proposed"`**とする（`TOPIC_STATUSES`タプルへの追加のみ、既存の`"active"`/`"cooling_down"`/`"exhausted"`/`"published"`/`"retired"`は変更しない）。
- `"proposed"`状態のtopic_groupは、既存の`passes_mainline_candidate_filter()`の第1条件（`topic_status == "active"`）を自動的に満たさないため、**既存の候補フィルタ本体を一切変更せずに**「人間確認前はmainlineへ出さない」という制約を実現できる。
- 新設する昇格関数案: `promote_proposed_topic_group(state) -> TopicGroupState`（人間が内容を確認したうえで呼ぶ想定、`topic_status`を`"proposed"`→`"active"`へ変更するのみ）。この関数もretry_budget/cooldown/候補フィルタ本体には触れない。

**抽出精度の限界と対処案:**

- キーワード辞書ベースの抽出であるため、辞書に無い新規商品名・カテゴリ（例: 未収録の新ガジェット用語）は`category_label`が付かない、または誤ったカテゴリに寄せられる可能性がある。
- 皮肉・否定文脈（「〜は使わなくなった」等）の扱いは、Phase 2 classifyに既にある`_detect_negation_context()`/`_mask_negated_genre_context()`（[scripts/x_api_phase2_classify.py](../../scripts/x_api_phase2_classify.py)）と同等の考え方を将来的に`topic_dedupe.py`側にも適用検討する余地があるが、本設計では未対応として明記する。
- **対処案（本タスクの指示どおり）**: 抽出結果は`"proposed"`状態でのみ登録し、`"active"`への昇格（＝実際にmainline候補になる）には人間の最終確認を1ステップ挟む。これは既存のCLAUDE.md実行ルール6・[ops/reports/operating_policy_human_confirmation_2026-08-14.md](../../ops/reports/operating_policy_human_confirmation_2026-08-14.md)（人間確認前提の運用方針）とも整合する。

### 4. 収集入口の差し替えのみで完結する設計

- 変更対象は`scripts/x_api_phase1_collect.py`の`QUERIES`定数の中身のみ（差し替え）。
- `scripts/x_api_phase2_classify.py`（Phase 2 classify、teacher判定ロジック本体）は無変更。前述のとおり`GADGET_KEYWORDS`が既に広いカテゴリをカバーしているため、変更の必要性自体がない。
- `scripts/topic_group_state.py`のretry_budget/cooldown/候補フィルタ本体（`record_mainline_attempt()`/`record_publication()`/`passes_mainline_candidate_filter()`）は無変更。`"proposed"`ステータスの追加と`promote_proposed_topic_group()`の新設のみを提案しており、いずれも既存ロジックの分岐を書き換えるものではない。
- Gate A / thresholds / shipping decisionには一切触れない。

### 検証項目（レビュー観点、実装検証は本タスクの範囲外）

- 提案クエリ6本が512文字制限内に収まっているか（本文書内で文字数を目視確認済み、全て制限に対し十分な余裕がある）
- 商品カテゴリの先読みが排除されているか——**自己チェック結果は下記「未解決事項」参照。完全な排除はできていない。**
- 実際にX APIへ発行した際のヒット件数・ノイズ比率（reject率）の実測（未実施、実装フェーズでの検証項目として残す）
- `"proposed"`→`"active"`昇格フローの人間確認UI・運用手順の具体化（未設計、実装フェーズで検討）

---

## 未解決事項・要判断事項（人間が決めるべき点）

1. **X APIの契約プラン・月間上限が不明。** 呼び出し回数を12本削減する設計にはしたが、正確な予算内かどうかは契約内容を人間が確認する必要がある。
2. **商品カテゴリの先読みの完全排除はできていない（自己チェック結果）。** 提案クエリ自体は「ガジェット」「デバイス」等のジャンル語・機能語にとどめ特定商品名を含まないが、Phase 2側の`GADGET_KEYWORDS`辞書（スマホ/Apple Watch/腕時計/モバイルバッテリー/充電器/ケーブル/EDC等）は依然として人間が事前列挙したカテゴリ語のリストである。「収集クエリでの先読み」は排除できても、「Phase 2の分類辞書での先読み」は本タスクの制約（Phase 2は変更しない）により残存する。この残存をどこまで許容するかは人間の判断が必要。
3. **`"proposed"`ステータスの新設・`promote_proposed_topic_group()`の新設は、本調査では設計提案のみに留めた。** 実装するかどうか、実装する場合のcommit分割方針は別タスクとして人間の指示が必要。
4. **エンゲージメント基準についての事実確認のずれ**: 背景説明にある「teacher判定はエンゲージメント基準」という前提と、実際のコード（`_classify()`はキーワード共起ベース）が完全には一致しなかった。この食い違いの解消（コードを基準に合わせるか、認識を訂正するか）は人間の判断が必要（ただし本タスクの制約によりteacher判定ロジック自体は変更していない）。
5. **ノイズ増加の実測が未実施。** ジャンルレベルの広いクエリへ切り替えた場合の実際のreject率・pre_teacher_candidate歩留まりは、実装・実行してみないと分からない。段階的なロールアウト（まず1〜2クエリだけ試す等）を検討する余地がある。
