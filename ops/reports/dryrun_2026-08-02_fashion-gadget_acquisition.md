# dryrun_2026-08-02_fashion-gadget_acquisition.md — E2E試走レポート

> このリポジトリの初期セットアップ後、担当間の引き継ぎとログ運用が成立するかを検証した最初のdry run記録。
> `ops/logs/post_log.jsonl` には残さず（mainは「設計・雛形・運用ルールの正本」であり本番ログ置き場ではないため）、本レポートに全ログを保存する。

## 試走の目的

`x-researcher → growth-marketer → x-copywriter → affiliate-compliance-reviewer → logger` の一連の引き継ぎと、`ops/logs/post_log.jsonl` へのログ運用（ID発行・再提出時の扱い）が実務上成立するかを検証する。実際のXへの投稿・外部API接続は行わない。

## 条件

- 商品カテゴリ: ファッション×ガジェット
- 運用モード: acquisition（集客）
- アフィリエイトリンクなし、開示欄は「該当なし」で扱う
- 将来の販売モード接続を見据え、カテゴリ内の有望サブテーマも整理する

---

## 1. x-researcher — カテゴリ分解

**狙う読者像（仮説）**: 20〜30代、通勤・通学があり、ガジェットは好きだが服装のバランスも気にする層

**よくある悩み（仮説）**
- ガジェットを持ち歩くとコーデ・バッグ内の見た目が崩れる
- 荷物が増える、配線がごちゃつく
- 夏場は「機能重視の暑さ対策グッズ」が野暮ったく見えがち

**サブカテゴリ（将来の販売モード接続候補）**

| サブテーマ | 内容 |
|---|---|
| 身につけるガジェット | スマートリング、コーデを崩さないワイヤレスイヤホン等 |
| 見た目を損ねない実用品 | デザイン性のあるケーブル・モバイルバッテリー |
| 通勤/通学で映える便利系 | ガジェット収納ポーチ、バッグ内オーガナイザー |
| ミニマル系 | 薄型・軽量ガジェット |
| 暑さ対策・快適性向上 | デザイン性のある携帯扇風機・冷却グッズ |

**反応が取りやすそうな切り口（仮説）**: 「あるある共感」型（見た目とガジェットの両立の葛藤）
**避けるべき切り口**: 断定的な効果効能の主張（特に暑さ対策グッズの健康効果）、価格・セール訴求（集客モードの目的とずれる）

事実として確認できたものはなく、すべて一般的な傾向に基づく仮説である旨を明記する（試走のため外部調査は未実施）。

---

## 2. growth-marketer — 施策設計

- 選定施策: 「見た目とガジェットの両立あるある」切り口
- 狙うKPI: 主 = `impressions` / `profile_visit_rate`、補助 = `follow_rate`
- CTA type: `profile_visit`
- 理由: 集客モードの目的はフォロー母数の入口を作ることであり、リンククリックを狙うCTA（販売モードの役割）は今回不要と判断

---

## 3. x-copywriter — 投稿案2件（初稿）

### 案A

- フックタイプ: あるある共感型
- 本文: 「私服はちゃんとしてるのに、ガジェット類だけ残念になる問題。ケーブルやモバイルバッテリー、気づけば見た目バラバラになりがち。地味にあるあるだけど、あまり語られない悩みかもしれない。見た目を崩さない持ち歩き方の工夫、プロフィールにまとめてます。」
- CTA文言: 「見た目を崩さない持ち歩き方の工夫、プロフィールにまとめてます。」（本文に統合）
- 開示欄: 該当なし

### 案B（初稿）

- フックタイプ: 煽り訴求型
- 本文: 「この夏、絶対後悔しない神アイテム見つけた。汗だくなのにおしゃれも諦めたくない人へ。これさえあれば見た目も涼しさも完璧に解決します。今すぐプロフィールをチェックして、あなたも試してみてください。」
- CTA文言: 「今すぐプロフィールをチェックして、あなたも試してみてください。」（本文に統合）
- 開示欄: 該当なし

---

## 4. affiliate-compliance-reviewer — レビュー判定

| 案 | 判定 | 判定理由 |
|---|---|---|
| 案A | **approved** | 開示欄該当なし・断定表現なし・CTAは集客モードとして適切（`profile_visit`から逸脱なし）。承認者: affiliate-compliance-reviewer |
| 案B | **needs_revision** | 「絶対後悔しない神アイテム」「完璧に解決します」が断定的・誇大表現（`amazon-affiliate-policy.md`抵触の恐れ）。「今すぐ〜試してみてください」が集客モードにしては強すぎるCTA（販売モードの訴求に近い、`x-posting-policy.md`の品質優先方針に照らして要修正） |

**修正方針（案B）**: 断定語（「絶対」「完璧に解決」）を外し、悩み共感ベースの表現に変更。CTAの緊急性演出（「今すぐ」）を除去し、`profile_visit`型の柔らかい誘導文言に変更。CTA type自体は変更しない。

---

## 5. x-copywriter — 案B修正版（同一post_id維持で再提出）

- フックタイプ: 悩み共感型
- 本文: 「夏場、涼しさとおしゃれの両立って地味に難しい。汗対策グッズって機能重視すぎてダサくなりがちだけど、見た目を崩さない選び方もある気がしている。見た目を犠牲にしない暑さ対策の工夫、プロフィールに少しずつまとめてます。」
- CTA type: `profile_visit`のまま維持（marketerの方針から逸脱なし）

**この時点で判明した設計上の欠落（後述「詰まり」参照）**: 再提出後、誰がいつaffiliate-compliance-reviewerへの再レビューを起動するかのルールが未定義だった。案Bは再提出されたまま`status: draft`で宙に浮く状態になった。

---

## 6. logger — 試走時に記録したログ（試走当時の内容。現在は`post_log.jsonl`から削除済み）

試走中、`ops/logs/post_log.jsonl` に以下3行を一時的に追記して検証した（現在はサンプル1行の状態に戻し、mainには残していない）。

```jsonl
{"post_id": "p-20260802-002", "created_at": "2026-08-02T10:00:00+09:00", "mode": "acquisition", "campaign": "trial-e2e-fashion-gadget", "product": null, "angle": "見た目とガジェットの両立あるある", "format": "single_post", "cta_type": "profile_visit", "disclosure_included": false, "draft_text": "私服はちゃんとしてるのに、ガジェット類だけ残念になる問題。ケーブルやモバイルバッテリー、気づけば見た目バラバラになりがち。地味にあるあるだけど、あまり語られない悩みかもしれない。見た目を崩さない持ち歩き方の工夫、プロフィールにまとめてます。", "final_text": "私服はちゃんとしてるのに、ガジェット類だけ残念になる問題。ケーブルやモバイルバッテリー、気づけば見た目バラバラになりがち。地味にあるあるだけど、あまり語られない悩みかもしれない。見た目を崩さない持ち歩き方の工夫、プロフィールにまとめてます。", "asset_ids": [], "link_id": null, "status": "approved", "approved_by": "affiliate-compliance-reviewer"}
{"post_id": "p-20260802-003", "created_at": "2026-08-02T10:05:00+09:00", "mode": "acquisition", "campaign": "trial-e2e-fashion-gadget", "product": null, "angle": "スタイリッシュな暑さ対策ガジェット", "format": "single_post", "cta_type": "profile_visit", "disclosure_included": false, "draft_text": "この夏、絶対後悔しない神アイテム見つけた。汗だくなのにおしゃれも諦めたくない人へ。これさえあれば見た目も涼しさも完璧に解決します。今すぐプロフィールをチェックして、あなたも試してみてください。", "final_text": null, "asset_ids": [], "link_id": null, "status": "needs_revision", "approved_by": null}
{"post_id": "p-20260802-003", "created_at": "2026-08-02T10:20:00+09:00", "mode": "acquisition", "campaign": "trial-e2e-fashion-gadget", "product": null, "angle": "スタイリッシュな暑さ対策ガジェット", "format": "single_post", "cta_type": "profile_visit", "disclosure_included": false, "draft_text": "夏場、涼しさとおしゃれの両立って地味に難しい。汗対策グッズって機能重視すぎてダサくなりがちだけど、見た目を崩さない選び方もある気がしている。見た目を犠牲にしない暑さ対策の工夫、プロフィールに少しずつまとめてます。", "final_text": null, "asset_ids": [], "link_id": null, "status": "draft", "approved_by": null}
```

4行すべて（サンプル行含む）`schemas/post_log.schema.json`（format enum適用後）に対してバリデーション済み。必須項目・enum・`post_id`のパターンすべて適合を確認した。

---

## 7. performance-analyst — 実運用開始後に見るべき観点

- モード別・訴求角度別の`profile_visit_rate`比較（「あるある共感」vs「悩み共感」等フックタイプ別の差）
- `needs_revision`発生率を担当・訴求角度別に集計し、コンプラ観点で崩れやすいパターンを早期検知
- 将来販売モードに接続する際、どのサブテーマ（researcherが整理した5分類）由来の集客投稿がフォロー転換率に効いているかを追跡

（今回は実データがないため、成果分析そのものは未実施）

---

## 再提出ルールの検証結果

- 同一post_id（`p-20260802-003`）を維持したまま、needs_revision後の修正版を新しい行として追記する運用は、schema上・JSONL運用上問題なく機能した
- 最新`created_at`の行が現在ステータスを表すという前提も、実際に2行（`needs_revision`→`draft`）で確認できた
- **一方で、「再提出後に誰が再レビューを起動するか」のルールが試走時点で未定義だったため、案Bは`status: draft`のまま停滞する結果になった。** これを受けて、x-copywriter・affiliate-compliance-reviewer・mode-orchestratorの3エージェント定義に再レビュー起動ルールを追記済み（後述）

## post_id運用の検証結果

- `post_id`命名規則（`p-YYYYMMDD-連番`）は問題なく運用できた
- 「同一投稿案は同一post_idを維持し、新規投稿案にのみ新しいpost_idを発行する」というルールも、案Aと案Bで異なるpost_idを発行し、案Bの再提出では新規発行しないという形で一貫して運用できた
- `format`フィールドがフリーテキストだったため、担当間で"single"という表記を使ったが、後にenum定義（`single_post`等）とズレていたことが判明（詰まり参照）

## 今回見つかった設計上の詰まり（3点）

1. **needs_revision後の再レビュー起動ルールが未定義だった** — copywriterが再提出した後、誰が・いつaffiliate-compliance-reviewerへ再レビューを依頼するかがCLAUDE.mdにもcompliance.mdにも書かれておらず、案Bが`draft`のまま宙に浮いた
2. **`post_log.schema.json`の`format`フィールドがフリーテキストでenum定義されていなかった** — `single`と記入したが、担当間で表記ゆれ（`single`/`単発`/`text`等）が起きうる状態だった
3. **`product`フィールドに将来接続用のサブテーマ情報を残す場所がない** — 商品未確定の集客投稿では`product: null`とせざるを得ず、後で販売モードに接続する際「どのサブテーマ由来の集客投稿か」をログから機械的に追跡できない

## 今回採用した修正内容の要約

- **詰まり1への対応**: `.claude/agents/x-copywriter.md`、`.claude/agents/affiliate-compliance-reviewer.md`、`.claude/agents/mode-orchestrator.md`（および対応する`docs/roles/*.md`、`templates/review_template.md`）に、再提出は必ずaffiliate-compliance-reviewerの再レビューを経ること、orchestratorが滞留を検知して再レビューを依頼することを明記
- **詰まり2への対応**: `schemas/post_log.schema.json`の`format`を`["single_post", "thread", "reply", "quote", "image_post", "poll"]`のenumに変更
- **詰まり3への対応**: schema変更は保留。暫定運用として、`campaign`フィールドに`subtheme:<slug>`のプレフィックスを付ける運用ルールを提案済み（例: `campaign: "subtheme:heat-comfort/trial-e2e-fashion-gadget"`）。まだファイルには反映していない

## 次にやるべきこと

1. `campaign`フィールドの`subtheme:`プレフィックス運用ルールを実際に採用するか判断し、採用する場合は`docs/roles/logger.md`等に明文化する
2. 教育モード・販売モードでも同様のend-to-end試走を行い、特に販売モードではコンプラレビューの厳格運用とdisclosure欄の実運用を検証する
3. 数件分の試走・実運用ログが溜まった段階で、`weekly-pdca-review` skillを実際に実行し、`ops/reports/weekly_review.md`への反映まで一巡できるか検証する
