# dryrun_2026-08-02_fashion-gadget_education.md — E2E試走レポート（教育モード）

> 1本目のdry run（[dryrun_2026-08-02_fashion-gadget_acquisition.md](dryrun_2026-08-02_fashion-gadget_acquisition.md)、集客モード）に続く2本目。今回は教育モードで試走し、あわせて1本目で見つかった「needs_revision後の再レビューが起動しない」問題への修正が実際に機能するかを検証する。
> 1本目と同じ方針で、生ログは`ops/logs/post_log.jsonl`に残さず本レポートに保存する（mainは設計・雛形・運用ルールの正本であり、本番/試走ログ置き場ではないため）。

## 試走の目的

- 教育モードでの `x-researcher → growth-marketer → x-copywriter → affiliate-compliance-reviewer → logger` の引き継ぎを検証する
- 1本目で追加した「needs_revision後は必ずaffiliate-compliance-reviewerの再レビューに戻る」ルール（`.claude/agents/x-copywriter.md`、`affiliate-compliance-reviewer.md`、`mode-orchestrator.md`）が、実際に機能するかを検証する
- 実際のXへの投稿・外部API接続は行わない

## 条件

- 商品カテゴリ: ファッション×ガジェット（1本目と同一。集客モードで興味を持った層が、教育モードで比較軸を得る想定の連続性を意識）
- 運用モード: education（教育）
- サブテーマ: 「暑さ対策・快適性向上」（1本目のresearcher整理で挙げた5サブテーマの1つ）
- アフィリエイトリンクなし、開示欄は「該当なし」で扱う

---

## 1. x-researcher — 比較軸の整理

**想定読者**: 1本目の集客投稿（「涼しさとおしゃれの両立」）に反応した層。まだ具体的な比較軸を持っていない、という仮定

**よくある悩み（仮説）**: 携帯扇風機・ネッククーラー等は機能重視のデザインが多く私服に合わせにくい。選び方が分からず「とりあえず人気ランキング1位」で選んで後悔しがち

**比較軸候補（一般的な傾向としての仮説、事実確認はしていない）**
- 携帯性（重量・サイズ）
- 稼働時間
- 静音性
- 素材・カラー展開
- 充電方式（USB-C統一かどうか）

**反応が取りやすそうな切り口**: 「失敗しやすいポイント」「選び方を間違えるとどうなるか」
**避けるべき切り口**: 特定商品を名指しで「これが一番」と断定する比較、価格の押し売り感

---

## 2. growth-marketer — 施策設計

- 選定施策: 「暑さ対策ガジェットの選び方 — 見た目を犠牲にしないための比較軸」
- 狙うKPI: 主 = `save_rate`、補助 = `reply_rate`、`link_preclick_interest`
- CTA type: `save`
- 理由: 教育モードの目的は理解促進と信頼構築であり、リンククリックやプロフィール遷移より「保存してもらう」ことがこの投稿の意図に合致する

---

## 3. x-copywriter — 投稿案2件（初稿）

### 案C

- フォーマット: `thread`
- フックタイプ: 失敗回避型
- 本文: 「携帯扇風機、なんとなく人気ランキング1位で選ぶと後悔しがちな理由。比較すべきは重量・稼働時間・静音性・素材やカラー・充電方式(USB-C統一か)。見た目を崩さない視点を比較軸に入れておくと選びやすい。」
- CTA文言: 「見返せるように保存しておくと便利です。」
- 開示欄: 該当なし

### 案D（初稿）

- フォーマット: `single_post`
- フックタイプ: 断定訴求型
- 本文: 「結局これさえ選べば全部解決すると思う。見た目も機能も両立してる暑さ対策グッズって実はこれが一番です。他は正直微妙だと思う。」
- CTA文言: 「保存して損はないので、ぜひチェックしてみてください。」
- 開示欄: 該当なし

---

## 4. affiliate-compliance-reviewer — レビュー判定（1回目）

| 案 | 判定 | 判定理由 |
|---|---|---|
| 案C | **approved** | 開示欄該当なし・断定表現なし、比較軸に基づく客観的整理、CTAは`save`型で教育モードとして適切 |
| 案D | **needs_revision** | 「これが一番です」「他は正直微妙」が根拠のない断定的な優劣付け（education-playbookの失敗例、`amazon-affiliate-policy.md`の誤認を招く表現にも抵触するおそれ） |

**修正方針（案D）**: 特定商品を名指し・断定せず、「〜を優先すると失敗しにくい」という条件付きの提示に変更する。競合を貶める表現（「他は正直微妙」）を削除する。CTA type（`save`）はそのまま維持する。

---

## 5. x-copywriter — 案D修正版（同一post_id維持で再提出）

- 本文: 「暑さ対策グッズ、機能だけで選ぶと見た目に後悔しがちだけど、静音性と携帯性を優先すると失敗しにくい気がしている。」
- CTA文言: 「保存して、次に選ぶときの参考にしてもらえたら。」
- CTA type: `save`のまま維持（marketerの方針から逸脱なし）

---

## 6. mode-orchestrator — 再レビュー起動（1本目で追加した修正の検証）

再提出された案Dの修正版を検知し、affiliate-compliance-reviewerへ再レビューを明示的に依頼した。**1本目のdry runでは、この起動が行われず案が`draft`のまま宙に浮いたが、今回は`mode-orchestrator.md`に追加したルール（滞留検知→再レビュー依頼）どおりに動作し、次の再レビューにつながった。**

---

## 7. affiliate-compliance-reviewer — レビュー判定（2回目・再レビュー）

| 案 | 判定 | 判定理由 |
|---|---|---|
| 案D修正版 | **approved** | 断定表現・競合を貶める表現が除去され、条件付きの提示になっている。CTAも`save`のまま逸脱なし |

---

## 8. logger — 試走時に検証したログ（一時構築、mainには残していない）

以下2件（案D修正版を含め3行）を検証用に一時構築し、schemaに対してバリデーションした（結果は後述）。ログは`ops/reports/`にのみ保存し、`ops/logs/post_log.jsonl`には追記していない。

```jsonl
{"post_id": "p-20260802-004", "created_at": "2026-08-02T14:00:00+09:00", "mode": "education", "campaign": "trial-e2e-fashion-gadget-edu", "product": null, "angle": "暑さ対策ガジェットの選び方比較", "format": "thread", "cta_type": "save", "disclosure_included": false, "draft_text": "携帯扇風機、なんとなく人気ランキング1位で選ぶと後悔しがちな理由。比較すべきは重量・稼働時間・静音性・素材やカラー・充電方式(USB-C統一か)。見た目を崩さない視点を比較軸に入れておくと選びやすい。", "final_text": "携帯扇風機、なんとなく人気ランキング1位で選ぶと後悔しがちな理由。比較すべきは重量・稼働時間・静音性・素材やカラー・充電方式(USB-C統一か)。見た目を崩さない視点を比較軸に入れておくと選びやすい。", "asset_ids": [], "link_id": null, "status": "approved", "approved_by": "affiliate-compliance-reviewer"}
{"post_id": "p-20260802-005", "created_at": "2026-08-02T14:05:00+09:00", "mode": "education", "campaign": "trial-e2e-fashion-gadget-edu", "product": null, "angle": "暑さ対策ガジェットの選び方比較", "format": "single_post", "cta_type": "save", "disclosure_included": false, "draft_text": "結局これさえ選べば全部解決すると思う。見た目も機能も両立してる暑さ対策グッズって実はこれが一番です。他は正直微妙だと思う。", "final_text": null, "asset_ids": [], "link_id": null, "status": "needs_revision", "approved_by": null}
{"post_id": "p-20260802-005", "created_at": "2026-08-02T14:25:00+09:00", "mode": "education", "campaign": "trial-e2e-fashion-gadget-edu", "product": null, "angle": "暑さ対策ガジェットの選び方比較", "format": "single_post", "cta_type": "save", "disclosure_included": false, "draft_text": "暑さ対策グッズ、機能だけで選ぶと見た目に後悔しがちだけど、静音性と携帯性を優先すると失敗しにくい気がしている。", "final_text": "暑さ対策グッズ、機能だけで選ぶと見た目に後悔しがちだけど、静音性と携帯性を優先すると失敗しにくい気がしている。", "asset_ids": [], "link_id": null, "status": "approved", "approved_by": "affiliate-compliance-reviewer"}
```

3行とも `schemas/post_log.schema.json` に対してバリデーション済み（必須項目・enum・`post_id`パターンすべて適合）。`format: "thread"` を使ったのは今回が初めてで、1本目で追加したformat enumが集客モード以外の形式でも問題なく機能することを確認できた。

---

## 再提出ルールの検証結果（1本目からの修正の検証）

- **1本目で見つかった「再提出後、再レビューが起動しない」問題は、今回は発生しなかった。** mode-orchestratorが滞留を検知し、affiliate-compliance-reviewerへの再レビュー依頼を明示的に行い、案Dの修正版は最終的に`approved`まで到達した
- 同一post_id（`p-20260802-005`）を維持したまま3行（初稿→needs_revision→再提出→approved）の流れが一貫して追跡できた

## post_id運用の検証結果

- education モードでも `post_id` 命名規則・再提出時の同一ID維持ルールは問題なく運用できた
- `format` フィールドに `thread` を使用し、1本目で導入したenumが集客モード以外でも機能することを確認した

## 見つかった気づき（新規の詰まりではない）

- `cta_type` フィールドは（`format`と異なり）enum化されていないフリーテキストのままである。今回は`profile_visit`（1本目）・`save`（2本目）の2種類しか使っていないが、今後CTA種類が増えた場合に表記ゆれが起きる可能性がある。今回は問題化しなかったため、修正は提案せず観察のみ記録する
- 1本目で提案した「`campaign`フィールドへの`subtheme:`プレフィックス運用」は今回未採用（`campaign`は単純な試走識別名`trial-e2e-fashion-gadget-edu`のみ使用）。引き続き保留中の提案として残る

## 今回は修正を行っていない

1本目のような新規の設計上の詰まりは見つからなかった（1本目の修正が正しく機能したことの確認が主目的だったため）。したがって今回はコード・ドキュメントの修正は行っていない。

## 次にやるべきこと

1. 販売モードでも同様のend-to-end試走を行い、コンプラレビューの厳格運用とdisclosure欄の実運用を検証する
2. `cta_type`のenum化が必要かどうか、CTA種類が増えてきた段階で再検討する
3. 教育モード・集客モードの試走で得られたダミー相当の数値を使い、`weekly-pdca-review` skillの動作を検証する（→ 別レポート [dryrun_2026-08-02_weekly-pdca-review.md](dryrun_2026-08-02_weekly-pdca-review.md) を参照）
