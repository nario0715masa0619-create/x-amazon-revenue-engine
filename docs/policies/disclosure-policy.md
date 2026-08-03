# disclosure-policy.md — 開示ポリシー

アフィリエイトリンクを含む発信について、読者に誤解を与えないための開示ルールを定める。

## 1. 開示をどう扱うか

- Amazon商品への誘導を含む投稿は、アフィリエイト関係にあることを読者が認識できる形で開示する
- 開示は「あとから気づく」ものではなく、投稿を読んだ時点で認識できる位置・表現にする
- 開示を省略してよい例外はこのプロジェクトでは設けない（すべてのリンク付き投稿で開示する）

## 2. 投稿文内での表現方針

- 開示は本文の末尾、または本文中の分かりやすい位置に明記する（例: 「※Amazonアソシエイトとして紹介料を得ています」等、平易な表現を使う）
- 小さすぎる・分かりにくい表現（絵文字のみ、極端な省略形のみ）で済ませない
- `templates/x_post_template.md` の「開示欄」フィールドは、投稿案の段階から独立した項目として必ず埋める。文案作成時に本文と一体化させず、後から欠落が分かるようにする

## 3. 販売モード時の厳格さ

- 販売モード（sales-playbook）の投稿は、開示ルールにおいて最も厳格に扱う。開示欄が空、または曖昧な投稿案は `affiliate-compliance-reviewer` が承認しない（[docs/policies/amazon-affiliate-policy.md](amazon-affiliate-policy.md)、[.claude/skills/sales-playbook/SKILL.md](../../.claude/skills/sales-playbook/SKILL.md)）
- 集客・教育モードでリンクを含める場合も、同様に開示を行う。モードによって開示ルール自体が緩くなることはない（緩くなるのは訴求の強さであり、開示の要件ではない）
- 開示の強さの目安: 「#PR」「#ad」のみ、絵文字のみといった短いタグだけの表示は**不十分な開示**として扱う。「本投稿はAmazonアソシエイトとして紹介料を得ています」等、平易な文章で紹介料を得ている旨が明記されているものを**十分な開示**とする。affiliate-compliance-reviewerは、開示が全くない場合は`templates/review_template.md`の`disclosure_missing`タグ、存在するが不十分な場合は`disclosure_weak`タグを用いて`needs_revision`とする

## 4. ログとの関係

- `post_log.schema.json` の `disclosure_included` フィールドで、開示の有無を機械的に追跡する（[schemas/post_log.schema.json](../../schemas/post_log.schema.json)）
- `disclosure_included: false` かつリンクを含む投稿は、`logger` が警告を出す運用とする
- `disclosure_included`は開示の「有無」のみを表すboolean値であり、「開示はあるが弱い」までは表現できない。その差は`post_log`ではなくレビュー記録（`disclosure_weak`タグ）側で追跡する運用とする（schema自体の拡張は将来の検討課題とする）

## 5. 参照

- Amazonアソシエイト・プログラムの公式開示要件は随時更新されるため、最新の公式規約を必ず確認すること。本ポリシーは社内運用チェックリストであり、規約そのものではない
