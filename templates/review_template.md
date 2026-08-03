# review_template.md — コンプライアンスレビューテンプレート

> affiliate-compliance-reviewer が投稿案をレビューする際の型。1レビュー = このテンプレート1件。

---

## 対象post_id

（記入）

## レビュー区分

初回レビュー / 再レビュー（needs_revision後の再提出）

## モード

集客 / 教育 / 販売

## チェック項目

- [ ] 開示欄の有無・明確さ（[disclosure-policy.md](../docs/policies/disclosure-policy.md)）
- [ ] 誇大表現・断定的な効果効能の主張の有無（[amazon-affiliate-policy.md](../docs/policies/amazon-affiliate-policy.md)）
- [ ] 価格・在庫・キャンペーン情報の断定表現の有無
- [ ] 誤認を招く比較表現の有無
- [ ] 同一文面の量産・不自然な自動化にあたらないか（[x-posting-policy.md](../docs/policies/x-posting-policy.md)）
- [ ] （販売モードのみ）CTAの緊急性演出が過度でないか

## 判定

`approved` / `needs_revision` / `rejected`

## 判定理由

（該当ポリシーの箇所を明示して記入）

## 差し戻し理由タグ

集計・分析用の構造タグ。`needs_revision`/`rejected`の場合は最低1つ選ぶ。`approved`の場合は空欄、または注意点があれば任意で付与してよい。

- [ ] `disclosure_missing`（開示が存在しない）
- [ ] `disclosure_weak`（開示はあるが不十分・不明確）
- [ ] `claim_too_strong`（断定的・誇大な表現）
- [ ] `cta_too_aggressive`（CTAの緊急性演出が過度）
- [ ] `insufficient_evidence`（比較・優位性主張の根拠不足）
- [ ] `mode_mismatch`（モードの目的とズレた訴求）
- [ ] `platform_risk`（同一文面の量産・不自然な自動化等）
- [ ] `other`（上記に当てはまらない場合。判定理由欄で補足）

## 修正方針（needs_revisionの場合）

（具体的に記入。差し戻すだけで終わらせない）

## レビュー担当

affiliate-compliance-reviewer

## レビュー日時

（記入）
