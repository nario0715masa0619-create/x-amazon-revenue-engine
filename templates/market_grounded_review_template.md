# market_grounded_review_template.md — market-grounded reviewテンプレート

> `trend-reality-reviewer` / `competitor-reality-reviewer` / `audience-market-fit-reviewer` が投稿案を評価する際の型。1レビュー = このテンプレート1件。
> **既存の`templates/review_template.md`（affiliate-compliance-reviewer用）とは別物であり、混同しない。** market-grounded reviewは「外部現実（トレンド・競合・市場）との照合」であり、compliance判断・最終承認は行わない。
>
> **2026-08-04改訂**: 集客モードでは「破綻していないか」ではなく「競合比で強いか・弱いか・同等か」を中核判定とする（[phase1 spec](../ops/reports/phase1_acquisition_launch_spec_2026-08-03.md)の「集客モードの評価思想」参照）。判定は絶対評価ではなく**相対評価**（競合比で強い／同等／弱い）。フック単体を先に評価し、フックが競合比で「弱い」場合は原則として`action: hold`とし、本文全体の評価に進まない。

---

## 対象post_id / candidate_label

（記入）

## reviewer_name

`trend-reality-reviewer` / `competitor-reality-reviewer` / `audience-market-fit-reviewer` のいずれか

## comparison_scope

`direct`（直接競合: 40代男性向けに服・持ち物・ガジェット・清潔感・身だしなみ・実用品を発信する近いアカウント） / `indirect`（間接競合: 整理術・通勤・デスク環境・EDC・ミニマル持ち物・仕事道具など、同じ読者の注意を奪うアカウント） / `benchmark`（準ベンチマーク: 同業ではないがX上で短文フックが強く止める力のあるアカウント）

## comparison_pattern

（比較対象に多い型の要約。以下を含める）

- `source_type`: `official_best_practice` / `trend_search` / `competitor_observation` / `user_provided_reference`
- `source_ref`: （参照した情報源。URL・検索クエリ・提示資料名など）
- 比較対象に多い型・傾向

## hook_assessment（一文目のみを切り出して評価。他の観点より先に行う）

`強い` / `同等` / `弱い`

## whole_post_assessment（`hook_assessment`が`弱い`でない場合のみ記入）

`強い` / `同等` / `弱い`

## axis_scores（5軸必須。`whole_post_assessment`を記入した案のみ）

- 停止力: `強い` / `同等` / `弱い`
- 自分事化: `強い` / `同等` / `弱い`
- 差別化: `強い` / `同等` / `弱い`
- 緊張感: `強い` / `同等` / `弱い`
- 遷移力: `強い` / `同等` / `弱い`

## action

`keep` / `revise` / `hold`

- `keep`は**競合比で同等以上**の場合のみ使う。「安全だが弱い（weak but safe）」案は`keep`にしない
- `hook_assessment`が「弱い」の場合、原則`action`は`revise`または`hold`とする
- `comparison_pattern`（外部根拠）が空の場合、`action`は`hold`のみとする
- 両案とも`revise`／`hold`相当なら、1回だけ修正して再判定する。修正後も弱ければ「best effortだが競合比では弱い」と`rationale`に明記する

## rationale

（判定理由。1〜2行）

## suggested_fix

（1行）

## confidence

`high` / `medium` / `low`

（`high`は複数ソースが一致した場合のみ。1件の観察例だけでの一般化は`high`にしない）

## insufficient_evidence_note

（データ不足の場合のみ記入。例: 「競合アカウント候補が不足」「直近比較サンプルが少ない」「トレンド確認の粒度が粗い」）
