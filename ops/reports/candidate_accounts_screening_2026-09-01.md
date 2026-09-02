# 候補アカウント13件の先生判定 + ジャンル内訳集計（2026-09-02実施、最終版）

人間が目星をつけた候補アカウントについて、既存のteacher判定パイプライン
（`_observe()`/`_classify()`/`_apply_engagement_gate()`、無変更・importのみで再利用）に
実際に投稿を通し、閾値を超えた投稿を持つアカウントのみを`watched_account_state.json`へ
登録した。判定ロジック自体は一切変更していない。

**実施経緯**:
1. 1回目（10アカウント、うち2件）: X API pay-per-useのクレジットが実行途中で枯渇し
   （`HTTP 402 Payment Required`、`{"detail":"credits depleted"}`）、tachibana_kz・
   athlon200GE_のみ完了、残り8件は投稿取得不能のまま停止。
2. 2回目（10アカウントの残り8件）: 人間によるクレジット追加課金後、1アカウント分の
   試験取得でHTTP 200を確認してから再開し、8件全てで投稿取得に成功（クレジット枯渇の
   再発なし）。10アカウント全件が完了。
3. 3回目（gadget系候補3件、本ドキュメントの最新更新分）: fashion軸17.61%に対しgadget軸
   3.14%という供給不足を受け、人間が「完全にガジェット系」と確信を持って選定した
   taishonpresso・SASSAN99999・niwaka_audioを追加スクリーニング。前回10件との重複は
   無いことを確認済み（user_id・handle両方で照合）。3件とも投稿取得に成功（クレジット
   枯渇なし）。

本ドキュメントは13アカウント全ての統合結果。

## アカウント別判定結果（13件全て、最終版）

| ハンドル | 総投稿数 | pre_teacher_candidate数 | layer_primary内訳 | 登録有無 |
|---|---|---|---|---|
| tachibana_kz | 100 | 0 | unclear:95 / fashion:4 / gadget:1 | 未登録 |
| athlon200GE_ | 100 | 0 | unclear:89 / gadget:11 | 未登録 |
| Akii_fit | 100 | 0 | unclear:98 / fashion:1 / gadget:1 | 未登録 |
| st_r0817 | 95 | 1 | fashion:43 / unclear:52 | **登録** |
| Daisuke__otoko | 100 | 2 | unclear:61 / fashion:39 | **登録** |
| tatsumo11 | 99 | 0 | unclear:91 / gadget:7 / fashion:1 | 未登録 |
| kaz_fukumaru | 97 | 0 | unclear:88 / gadget:8 / fashion:1 | 未登録 |
| fukunokioku | 98 | 1 | unclear:75 / fashion:22 / gadget:1 | **登録** |
| ikaretemitai | 100 | 1 | fashion:32 / unclear:68 | **登録** |
| shun_4colors | 99 | 2 | fashion:31 / unclear:66 / gadget:2 | **登録** |
| taishonpresso | 100 | 0 | unclear:92 / gadget:5 / fashion:3 | 未登録 |
| SASSAN99999 | 97 | 1 | unclear:86 / gadget:10 / fashion:1 | **登録** |
| niwaka_audio | 100 | 0 | unclear:98 / gadget:2 | 未登録 |

13アカウント全件の投稿取得・判定が完了した（総投稿数1,285件）。

代表的な投稿例（今回3件分、post_id／engagement_tier／layer_primary／confidence）:

- SASSAN99999: `1980559690141773950`／qualifying／**unclear**／medium

**注目すべき点**: gadget系と確信を持って選定した3アカウントのうち、唯一
`pre_teacher_candidate`に到達したSASSAN99999の該当投稿も、layer_primaryは"gadget"では
なく"unclear"だった。13アカウント全体を通じて、`pre_teacher_candidate`に到達した投稿は
fashion 6件・unclear 1件・**gadget 0件**であり、依然としてgadget層由来の
`pre_teacher_candidate`は1件も発生していない。

## 登録されたアカウント一覧

6アカウントが新規登録された（`watched_account_state.json`、いずれも`watch_status=active`・
新規登録＝`was_known=False`）:

| ハンドル | author_id | pre_teacher_candidate数 |
|---|---|---|
| st_r0817 | 765724766502170624 | 1 |
| Daisuke__otoko | 812466877184126977 | 2 |
| fukunokioku | 720220197668278273 | 1 |
| ikaretemitai | 756768794513584128 | 1 |
| shun_4colors | 55126678 | 2 |
| **SASSAN99999** | **4068452893** | **1** |

## 登録されなかったアカウントとその理由

| ハンドル | 理由 |
|---|---|
| tachibana_kz | 投稿取得成功、`pre_teacher_candidate`到達0件のため対象外 |
| athlon200GE_ | 投稿取得成功、`pre_teacher_candidate`到達0件のため対象外 |
| Akii_fit | 投稿取得成功、`pre_teacher_candidate`到達0件のため対象外 |
| tatsumo11 | 投稿取得成功、`pre_teacher_candidate`到達0件のため対象外 |
| kaz_fukumaru | 投稿取得成功、`pre_teacher_candidate`到達0件のため対象外 |
| taishonpresso | 投稿取得成功、`pre_teacher_candidate`到達0件のため対象外 |
| niwaka_audio | 投稿取得成功、`pre_teacher_candidate`到達0件のため対象外 |

いずれも投稿取得・判定は完了しており、明確に`pre_teacher_candidate`基準を満たさなかった
という結果。

## 重要シグナルの確認（gadget系3アカウントの追加調査結果）

gadget系3アカウント（taishonpresso・SASSAN99999・niwaka_audio）のうち、2/3
（taishonpresso・niwaka_audio）が`pre_teacher_candidate`到達0件、残る1/3
（SASSAN99999）も到達した1件はlayer_primary="unclear"（gadgetではない）だった。「3件とも
（または大半が）0件」に該当したため、依頼どおり追加調査を実施した。

**調査対象**: 3アカウントの投稿のうち、`layer_primary=="gadget"`かつ
`observed_engagement_tier=="qualifying"`だが`pre_teacher_candidate`に届かなかった投稿を
全件抽出（コード変更は行わず、`_observe()`/`_classify()`の出力をそのまま記録しただけ）。
該当**10件**（taishonpresso 3件、SASSAN99999 7件、niwaka_audio 0件）。

### 10件の`obs`集計（事実のみ）

| 観測項目 | 分布 |
|---|---|
| `gadget_signal_strength` | **medium: 10/10（"high"は0件）** |
| `fashion_signal_strength` | low: 10/10 |
| `intersection_signal_strength` | low: 10/10 |
| `observed_topic_fit` | low: 9/10、medium: 1/10 |
| `observed_structure_fit` | low: 7/10、medium: 3/10 |
| `observed_approach_value` | low: 8/10、medium: 2/10 |

### classification内訳と該当reason

| classification | 件数 | reason（重複含む） |
|---|---|---|
| reject | 6 | `genre_fit_low`（6件）、`trend_signal_is_broad_only`（うち2件は併記） |
| manual_review | 2 | `gadget_signal_without_style_connection`（2件） |
| observe | 2 | `list_or_selection_structure_detected`（1件）、`strong_approach_but_not_enough_structure`（1件） |

**事実として確認できたこと**:
- 該当10件は`observed_engagement_tier=="qualifying"`（`_apply_engagement_gate()`の
  基準自体は満たしている）にもかかわらず、いずれも`gadget_signal_strength`が
  "medium"止まりで"high"に到達した投稿は0件だった。
- `fashion_signal_strength`／`intersection_signal_strength`はいずれも10件全てで"low"
  （fashionとの交点を示す要素が乏しい、純粋にgadget寄りの投稿だった）。
- reject 6件の主reasonは`genre_fit_low`（「40代ファッション×ガジェットとの交点・観察価値
  ともに乏しい」）。manual_review 2件は明示的に`gadget_signal_without_style_connection`
  （「ガジェットシグナルはあるがスタイル/見え方接点が弱い」）というreasonだった。
- これは`_observe()`関数のdocstring（2026-09-01改訂コメント、[scripts/x_api_phase2_classify.py:558-576](../../scripts/x_api_phase2_classify.py)）
  に記載されている、「fashionが本ジャンルの主題軸・gadgetが補助主題軸」という既存の
  ジャンル定義（[docs/roles等が参照する x_exploration_genre_redefinition_2026-08-15.md](../../ops/reports/x_exploration_genre_redefinition_2026-08-15.md)）
  と整合する観測結果である——バグではなく、現在の分類器がgadget単体コンテンツに
  fashion/style的な接点を要求する設計になっていることの実データでの再確認、という
  形で事実のみを報告する。**コード変更は一切行っていない。**

## ジャンルバランス集計（13アカウント合計の最終版）

| layer_primary | 件数 | 比率 |
|---|---|---|
| unclear | 1,059 | 82.41% |
| fashion | 178 | 13.85% |
| gadget | 48 | 3.74% |
| intersection | 0 | 0.00% |

（内訳: 10アカウント分 unclear:783/fashion:174/gadget:31/intersection:0、
gadget系3アカウント分 unclear:276/fashion:4/gadget:17/intersection:0、
総投稿数1,285件）

**手薄なジャンルの指摘（最終版）**: gadget系と確信を持って選定した3アカウントを追加しても、
gadgetの比率は3.14%→3.74%とわずかな上昇に留まり、fashion（13.85%）との差は依然として
大きい（約3.7倍）。**候補アカウントの質の問題ではなく、これらのアカウントの投稿内容が
実際に「gadget寄りではあるがfashion/style的な接点が乏しい」投稿主体であり、かつ
`gadget_signal_strength`が"medium"止まりで頭打ちになっている**ことが、上記「重要シグナル
の確認」の実データで確認された。intersection（fashion×gadget交点）は13アカウント通じて
依然として0件。

## 未解決事項・要判断事項

- **gadget軸のpre_teacher_candidateが13アカウント通じて依然として0件。**
  「候補アカウント選定の問題」ではなく「gadget単体コンテンツに対するtopic_fit/
  approach_value計算がfashion的な接点を暗黙に要求する設計になっている可能性」が
  実データで示唆された。この設計自体の妥当性（意図した仕様か、見直すべき非対称か）は
  人間の判断が必要（今回はコード変更・提案は一切行っていない、事実確認のみ）。
- 新規登録した6アカウント（st_r0817・Daisuke__otoko・fukunokioku・ikaretemitai・
  shun_4colors・SASSAN99999）は、次回の深掘り収集ワークフロー（`phase1_deepdive_
  collection.yml`、UTC 22:00日次）から実際に監視対象として動き出す。
- X APIクレジットは今回の3アカウント分（投稿297件）でも消費している。運用ペースに対する
  残高監視は引き続き人間の確認が必要。
