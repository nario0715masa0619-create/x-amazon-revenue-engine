# market_grounded_review_template.md — market-grounded reviewテンプレート

> `trend-reality-reviewer` / `competitor-reality-reviewer` / `audience-market-fit-reviewer` が投稿案を評価する際の型。1レビュー = このテンプレート1件。
> **既存の`templates/review_template.md`（affiliate-compliance-reviewer用）とは別物であり、混同しない。** market-grounded reviewは「外部現実（トレンド・競合・市場）との照合」であり、compliance判断・最終承認は行わない。

---

## 対象post_id / candidate_label

（記入）

## reviewer_name

`trend-reality-reviewer` / `competitor-reality-reviewer` / `audience-market-fit-reviewer` のいずれか

## claim

（投稿案に対する主張。1〜2行）

## external_evidence

- `source_type`: `official_best_practice` / `trend_search` / `competitor_observation` / `user_provided_reference`
- `source_ref`: （参照した情報源。URL・検索クエリ・提示資料名など）
- `observed_pattern`: （観察された型・傾向）

## confidence

`high` / `medium` / `low`

（`high`は複数ソースが一致した場合のみ。1件の観察例だけでの一般化は`high`にしない）

## action

`keep` / `revise` / `hold`

（`external_evidence`が空の場合は`hold`のみ）

## suggested_fix

（1行）

## insufficient_evidence_note

（データ不足の場合のみ記入。例: 「競合アカウント候補が不足」「直近比較サンプルが少ない」「トレンド確認の粒度が粗い」）
