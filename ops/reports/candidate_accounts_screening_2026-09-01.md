# 候補アカウント10件の先生判定 + ジャンル内訳集計（2026-09-02実施、最終版）

人間が目星をつけた候補アカウント10件について、既存のteacher判定パイプライン
（`_observe()`/`_classify()`/`_apply_engagement_gate()`、無変更・importのみで再利用）に
実際に投稿を通し、閾値を超えた投稿を持つアカウントのみを`watched_account_state.json`へ
登録した。判定ロジック自体は一切変更していない。

**実施経緯**: 1回目の実施（同日）でX API pay-per-useのクレジットが実行途中で枯渇し
（`HTTP 402 Payment Required`、`{"detail":"credits depleted"}`）、10アカウント中2件
（tachibana_kz、athlon200GE_）のみ完了、残り8件は投稿取得不能のまま停止した。人間による
クレジット追加課金後、2回目の実施として残り8件を処理した（再開前に1アカウント分の
試験取得でHTTP 200を確認してから本実行に進んだ）。2回目は8件全てで投稿取得に成功し、
クレジット枯渇の再発は無かった。本ドキュメントは10件全ての最終結果を統合したもの。

## アカウント別判定結果（10件全て、最終版）

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

10アカウント全件の投稿取得・判定が完了した（総投稿数988件）。`pre_teacher_candidate`に
到達した投稿は全てlayer_primary="fashion"・observed_engagement_tier="qualifying"だった
（gadget/intersection由来のpre_teacher_candidateは今回0件）。

代表的な投稿例（`pre_teacher_examples`、post_id／engagement_tier／layer_primary／confidence）:

- st_r0817: `2075099443200991643`／qualifying／fashion／medium
- Daisuke__otoko: `2071186861377077643`／qualifying／fashion／medium、`2049081203400294821`／qualifying／fashion／medium
- fukunokioku: `2088777767747735983`／qualifying／fashion／medium
- ikaretemitai: `2082035837789716650`／qualifying／fashion／medium
- shun_4colors: `2026848313962803294`／qualifying／fashion／**high**、`1920279945374245275`／qualifying／fashion／medium

## 登録されたアカウント一覧

5アカウントが新規登録された（`watched_account_state.json`、いずれも`watch_status=active`・
`teacher_count=1`・新規登録＝`was_known=False`）:

| ハンドル | author_id | pre_teacher_candidate数 |
|---|---|---|
| st_r0817 | 765724766502170624 | 1 |
| Daisuke__otoko | 812466877184126977 | 2 |
| fukunokioku | 720220197668278273 | 1 |
| ikaretemitai | 756768794513584128 | 1 |
| shun_4colors | 55126678 | 2 |

## 登録されなかったアカウントとその理由

| ハンドル | 理由 |
|---|---|
| tachibana_kz | 投稿取得成功、`pre_teacher_candidate`到達0件のため対象外 |
| athlon200GE_ | 投稿取得成功、`pre_teacher_candidate`到達0件のため対象外 |
| Akii_fit | 投稿取得成功、`pre_teacher_candidate`到達0件のため対象外 |
| tatsumo11 | 投稿取得成功、`pre_teacher_candidate`到達0件のため対象外 |
| kaz_fukumaru | 投稿取得成功、`pre_teacher_candidate`到達0件のため対象外 |

「登録されなかった」全5アカウントは、いずれも**投稿取得・判定は完了しており、明確に
`pre_teacher_candidate`基準を満たさなかった**という結果（前回報告時点の8件「未評価のまま」
とは異なり、今回は全て評価済み）。

## ジャンルバランス集計（10アカウント合計の最終版）

| layer_primary | 件数 | 比率 |
|---|---|---|
| unclear | 783 | 79.25% |
| fashion | 174 | 17.61% |
| gadget | 31 | 3.14% |
| intersection | 0 | 0.00% |

（内訳: 1回目バッチ2アカウント分 unclear:184/fashion:4/gadget:12/intersection:0、
2回目バッチ8アカウント分 unclear:599/fashion:170/gadget:19/intersection:0、
総投稿数988件）

**手薄なジャンルの指摘（最終版）**: 10アカウント全件を評価した結果、**fashionではなく
gadgetの方が明確に手薄**であることが判明した（fashion 17.61% に対し gadget 3.14%、
約5.6倍の開き）。前回2アカウントのみのサンプルでは「fashionの方が手薄」という暫定観察
だったが、これは**サンプル不足による誤った印象**だったことが今回の10件全体集計で
明らかになった。intersection（fashion×gadget交点）は今回0件のままで、依然として最も
稀少な層である。

`pre_teacher_candidate`に到達した投稿が全てlayer_primary="fashion"だった点も踏まえると、
**この10候補アカウント群はfashion軸の教師供給には貢献したが、gadget軸の教師供給には
今回何も貢献しなかった**——今後gadget軸の候補アカウントを別途探す必要性を示唆する結果。

## 未解決事項・要判断事項

- gadget軸の教師供給が今回の10候補では明確に手薄だったため、gadget寄りの候補アカウントを
  別途探索・追加スクリーニングする必要性が示唆される（人間の判断が必要）。
- 新規登録した5アカウントは、次回の深掘り収集ワークフロー（`phase1_deepdive_collection.yml`、
  UTC 22:00日次）から実際に監視対象として動き出す。`consecutive_unproductive_deepdive_runs`が
  閾値（暫定値10）に達するまでの推移は今後の運用で確認が必要。
- X APIクレジットは人間の追加課金により復旧済みだが、今回の10アカウント分（合計988件の
  投稿取得）で相応のクレジットを消費している。今後の運用ペース（日次収集＋深掘り収集の
  継続実行）に対してクレジット残高が十分かは、引き続き人間が請求ダッシュボードで
  監視する必要がある。
