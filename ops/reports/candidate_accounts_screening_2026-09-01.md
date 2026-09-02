# 候補アカウント10件の先生判定 + ジャンル内訳集計（2026-09-02実施）

人間が目星をつけた候補アカウント10件について、既存のteacher判定パイプライン
（`_observe()`/`_classify()`/`_apply_engagement_gate()`、無変更・importのみで再利用）に
実際に投稿を通し、閾値を超えた投稿を持つアカウントのみを`watched_account_state.json`へ
登録する方針で実施した。判定ロジック自体は一切変更していない。

**重要な制約（実施中に発覚）**: X API pay-per-useのクレジットが実行途中で枯渇し
（`HTTP 402 Payment Required`、`{"detail":"credits depleted"}`）、10アカウント中2件のみ
実データ取得に成功し、残り8件は投稿取得自体ができなかった。詳細は「未解決事項」参照。

## アカウント別判定結果

| ハンドル | user_id解決 | 総投稿数 | pre_teacher_candidate数 | layer_primary内訳 | 登録有無 |
|---|---|---|---|---|---|
| tachibana_kz | 成功 | 100 | 0 | unclear:95 / fashion:4 / gadget:1 | 未登録 |
| athlon200GE_ | 成功 | 100 | 0 | unclear:89 / gadget:11 | 未登録 |
| Akii_fit | 成功（投稿取得は失敗） | — | — | — | 未登録（HTTP 402） |
| st_r0817 | 成功（投稿取得は失敗） | — | — | — | 未登録（HTTP 402） |
| Daisuke__otoko | 成功（投稿取得は失敗） | — | — | — | 未登録（HTTP 402） |
| tatsumo11 | 成功（投稿取得は失敗） | — | — | — | 未登録（HTTP 402） |
| kaz_fukumaru | 成功（投稿取得は失敗） | — | — | — | 未登録（HTTP 402） |
| fukunokioku | 成功（投稿取得は失敗） | — | — | — | 未登録（HTTP 402） |
| ikaretemitai | 成功（投稿取得は失敗） | — | — | — | 未登録（HTTP 402） |
| shun_4colors | 成功（投稿取得は失敗） | — | — | — | 未登録（HTTP 402） |

10アカウント全件のuser_id解決自体は成功した（`GET /2/users/by`で一括解決、凍結・存在しない
アカウントは無かった）。投稿取得（`GET /2/users/:id/tweets`）は最初の2アカウント
（tachibana_kz、athlon200GE_）でクレジットを使い切り、3アカウント目（Akii_fit）以降の
8アカウントは全てHTTP 402で失敗した（実行順はHANDLES配列の記載順）。

実際に投稿を取得できた2アカウントは、いずれも`pre_teacher_candidate`到達0件だった
（tachibana_kzで`manual_review`2件・`observe`6件、athlon200GE_で`observe`6件、
それ以外は`reject`）。代表的な投稿例（`pre_teacher_examples`）は該当なし。

## 登録されたアカウント一覧

**0件。** 実際に投稿を取得できた2アカウントとも`pre_teacher_candidate`到達が0件だったため、
`watched_account_state.json`への登録は発生しなかった（`register_or_reactivate_watched_account()`
自体は一度も呼ばれていない）。`git status`で`ops/data/watched_account_state.json`・
`ops/data/watched_accounts.jsonl`に変更が無いことを確認済み。

## 登録されなかったアカウントとその理由

| ハンドル | 理由 |
|---|---|
| tachibana_kz | 投稿取得成功、100件中`pre_teacher_candidate`到達0件のため対象外 |
| athlon200GE_ | 投稿取得成功、100件中`pre_teacher_candidate`到達0件のため対象外 |
| Akii_fit / st_r0817 / Daisuke__otoko / tatsumo11 / kaz_fukumaru / fukunokioku / ikaretemitai / shun_4colors（8件） | X APIクレジット枯渇（HTTP 402 `credits depleted`）により投稿取得自体ができず、判定不能。**「先生ではないと判定された」わけではなく、判定を実施できていない**（未評価のまま） |

## ジャンルバランス集計

実際に取得できた200投稿（tachibana_kz 100件 + athlon200GE_ 100件）のみを対象に集計:

| layer_primary | 件数 | 比率 |
|---|---|---|
| unclear | 184 | 92.0% |
| gadget | 12 | 6.0% |
| fashion | 4 | 2.0% |
| intersection | 0 | 0.0% |

**手薄なジャンルの指摘**: この2アカウント分のサンプルだけを見ると、fashion（2.0%）がgadget
（6.0%）よりさらに手薄という結果になった。ただし、**この集計はサンプル数が極めて限定的
（10アカウント中2件、意図してジャンルバランスを取ったサンプリングでもない）であり、
「fashionが手薄」という一般的な結論を導くには全く不十分**なことを明記する。残り8アカウント
（未評価）にfashion寄りの投稿が多い可能性を排除できないため、クレジット回復後に残り8件を
評価してから改めてジャンルバランスを見直す必要がある。

## 未解決事項・要判断事項（最終報告本体に集約して記載）

X API pay-per-useのクレジットが枯渇しており、`GET /2/users/:id/tweets`を含む実データ取得系の
呼び出しが全てブロックされている状態にある。人間によるdeveloper portal／請求ダッシュボードでの
クレジット残高確認・追加購入（または次回請求サイクルでの自動回復待ち）が必要。詳細・影響範囲は
本タスクの最終報告を参照。
