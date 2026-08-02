# dryrun_2026-08-02_fashion-gadget_sales.md — E2E試走レポート（販売モード）

> 1本目（[acquisition](dryrun_2026-08-02_fashion-gadget_acquisition.md)）・2本目（[education](dryrun_2026-08-02_fashion-gadget_education.md)）に続く3本目。同じ「ファッション×ガジェット」カテゴリ・同じサブテーマ（暑さ対策と見た目の両立）で、集客→教育→販売の全モードを一気通貫させた。
> 目的は販売モードにおける reviewer / disclosure / approval / logger の閉ループが成立するかの確認。実際のXへの投稿・外部API接続・実アフィリエイトリンク発行は行わない。`ops/logs/post_log.jsonl` にも追記していない（1本目・2本目と同じ方針）。

## 試走条件

- 商品カテゴリ: ファッション×ガジェット
- 運用モード: sales（販売）
- サブテーマ: 暑さ対策と見た目の両立（1本目・2本目からの継続）
- Amazonアフィリエイトの実リンクは使わず、`link_id` はダミー値
- disclosure欄は販売モードとして必須の前提で記入
- compliance-reviewerによる差し戻し→再提出→再レビュー→approvedの閉ループを必ず通す

---

## 1. x-researcher — 販売接続しやすい切り口の整理

**想定読者**: 集客・教育モードで比較軸（重量・稼働時間・静音性・素材/カラー・充電方式）を理解した層。「そろそろ自分に合うタイプを一つ選びたい」フェーズ

**商品検討文脈**: 比較軸は理解しているが、「結局どのタイプが自分に向いているか」の決め手がまだない状態

**比較軸**: 教育モードの5軸を踏まえ、販売モードでは「タイプ別（ネッククーラー型／ハンディ型／首掛けファン型など）のどれが自分の使い方に合うか」という決め手の提示に踏み込む

**推しやすい訴求**: タイプ別の向き不向きに基づく意思決定支援（特定商品の断定ではなく「こういう使い方をする人にはこのタイプ」という条件付き推奨）

**注意すべき表現**: 「絶対」「一番」等の断定、「今だけ」「売り切れる」等の根拠のない緊急性演出、熱中症対策等の健康効果の断定

**事実と仮説の区別**: 比較軸・タイプ分類はいずれも一般的な商品カテゴリの傾向に基づく仮説であり、実際の商品調査・レビュー確認は行っていない

---

## 2. growth-marketer — 施策設計

- 選定施策: 「タイプ別比較に基づく意思決定支援」
- 狙うKPI: 主 = `ctr` / `conversion`、副 = `revenue` / `epc`
- CTA type: `link_click`
- 理由: 販売モードの主要KPIが`ctr`/`conversion`であり、`profile_visit`（集客）や`save`（教育）では測定できない「実際の商品ページ遷移」という成果に直結する`link_click`が適切
- 集客/教育との差: 集客は`profile_visit`（興味喚起・新規接触が目的）、教育は`save`（保存・信頼構築が目的）、販売は`link_click`（具体的な行動・成果への転換が目的）という点で異なる

---

## 3. x-copywriter — 投稿案2件（初稿）

### 案E

- 目的: 意思決定支援・購入誘導（`link_click`）
- フック: 「涼しさとおしゃれ、結局どのタイプなら両立できるか迷ってる人へ。」
- 本文: 「ネッククーラー型は静音性重視、ハンディ型は携帯性重視、首掛けファン型はバランス型。見た目を崩さない条件で選ぶなら、この軸で見るのがおすすめ。」
- CTA文言: 「タイプ別の比較と選び方はこちらでまとめてます」
- disclosure欄: 「本投稿はAmazonアソシエイトとして紹介料を得ています」（本文末尾に独立した行として明記）
- 想定format: `thread`
- link_id: `dummy-link-e2e-006`（ダミー）

### 案F（初稿）

- 目的: 購入誘導
- フック: 「これ買わないと今年の夏後悔します。」
- 本文: 「涼しさもおしゃれも完璧に両立できるのはこれしかない。実際に使った人はみんな絶対リピートしてます。今すぐチェックしないと売り切れるかも。」
- CTA文言: 「在庫があるうちに今すぐこちらからチェック！」
- disclosure欄: 「#PR」（本文末尾に短いタグのみ）
- 想定format: `single_post`
- link_id: `dummy-link-e2e-007`（ダミー）

---

## 4. affiliate-compliance-reviewer — レビュー判定（1回目・初回レビュー）

### 案E: `approved`

判定理由: disclosureが明確（紹介料を得ている旨が本文内に分かりやすく明記されている）、断定表現なし、比較軸に基づく客観的整理、CTAは`link_click`型で販売モードとして適切、緊急性演出なし

### 案F: `needs_revision`

差し戻し理由（複数観点に該当）:

| 観点 | 問題点 |
|---|---|
| disclosureの弱さ | 「#PR」のみで、紹介料を得ている旨の明確な説明がない（`disclosure-policy.md`の「開示は本文を読んだ時点で認識できる位置・表現にする」要件を満たさない） |
| 断定的・誇大表現 | 「完璧に両立できるのはこれしかない」「絶対リピート」（`amazon-affiliate-policy.md`の誤認を招く表現に該当） |
| 誤認を招きうる表現（根拠のない緊急性） | 「売り切れるかも」は在庫状況を確認していない推測であり、事実確認なしに緊急性を演出している |
| CTAが強すぎて不自然 | 「今すぐ...チェック！」は販売モードの中でも煽りが過度（`sales-playbook`のチェックポイント「CTAの緊急性演出が過度でないか」に抵触） |

**修正指示（何を直せばapprovedになるか）**:
1. disclosure欄を「本投稿はAmazonアソシエイトとして紹介料を得ています」等の明確な文言に変更し、本文内の分かりやすい位置に配置する
2. 「完璧に両立できるのはこれしかない」「絶対リピート」等の断定語を削除し、タイプ別比較に基づく条件付きの推奨に変更する
3. 根拠のない「売り切れるかも」を削除する
4. CTAの緊急性演出（「今すぐ」）を弱め、比較を見てもらう通常のリンク誘導表現に変更する

レビュー区分: 初回レビュー（両案とも）

---

## 5. x-copywriter — 案F修正版（同一post_id維持で再提出）

- 本文: 「涼しさとおしゃれ、タイプによって向き不向きがある。ネッククーラー型は静音性重視、ハンディ型は携帯性重視、首掛けファン型はバランス型。自分の使い方に合うタイプで選ぶと失敗しにくい。」
- CTA文言: 「タイプ別の比較はこちらから見られます」
- disclosure欄: 「本投稿はAmazonアソシエイトとして紹介料を得ています」（本文末尾に独立行として明記。案Eと同じ表現に統一）
- 想定format: `single_post`のまま維持
- CTA type: `link_click`のまま維持（marketerの方針から逸脱なし）
- link_id: `dummy-link-e2e-007`のまま維持（同一投稿の修正のため）

---

## 6. affiliate-compliance-reviewer — レビュー判定（2回目・再レビュー）

### 案F修正版: `approved`

改善点（何が直ったか）:
- disclosureが「#PR」のみから、紹介料を得ている旨の明確な文言に変更された
- 「完璧に〜これしかない」「絶対リピート」等の断定語が削除され、タイプ別の条件付き推奨に変わった
- 根拠のない「売り切れるかも」が削除された
- CTAの緊急性演出（「今すぐ」）が解消され、比較閲覧を促す通常の誘導表現になった

レビュー区分: 再レビュー（needs_revision後の再提出）。未レビューのまま放置せず、再提出後ただちに再レビューを実施した。

---

## 7. logger — 記録される想定のJSONL行（実ファイルには追記していない）

```jsonl
{"post_id": "p-20260802-006", "created_at": "2026-08-02T16:00:00+09:00", "mode": "sales", "campaign": "trial-e2e-fashion-gadget-sales", "product": null, "angle": "タイプ別比較(涼しさとおしゃれの両立)", "format": "thread", "cta_type": "link_click", "disclosure_included": true, "draft_text": "涼しさとおしゃれ、結局どのタイプなら両立できるか迷ってる人へ。ネッククーラー型は静音性重視、ハンディ型は携帯性重視、首掛けファン型はバランス型。見た目を崩さない条件で選ぶなら、この軸で見るのがおすすめ。タイプ別の比較と選び方はこちらでまとめてます。本投稿はAmazonアソシエイトとして紹介料を得ています。", "final_text": "涼しさとおしゃれ、結局どのタイプなら両立できるか迷ってる人へ。ネッククーラー型は静音性重視、ハンディ型は携帯性重視、首掛けファン型はバランス型。見た目を崩さない条件で選ぶなら、この軸で見るのがおすすめ。タイプ別の比較と選び方はこちらでまとめてます。本投稿はAmazonアソシエイトとして紹介料を得ています。", "asset_ids": [], "link_id": "dummy-link-e2e-006", "status": "approved", "approved_by": "affiliate-compliance-reviewer"}
{"post_id": "p-20260802-007", "created_at": "2026-08-02T16:05:00+09:00", "mode": "sales", "campaign": "trial-e2e-fashion-gadget-sales", "product": null, "angle": "タイプ別比較(涼しさとおしゃれの両立)", "format": "single_post", "cta_type": "link_click", "disclosure_included": true, "draft_text": "これ買わないと今年の夏後悔します。涼しさもおしゃれも完璧に両立できるのはこれしかない。実際に使った人はみんな絶対リピートしてます。今すぐチェックしないと売り切れるかも。在庫があるうちに今すぐこちらからチェック！ #PR", "final_text": null, "asset_ids": [], "link_id": "dummy-link-e2e-007", "status": "needs_revision", "approved_by": null}
{"post_id": "p-20260802-007", "created_at": "2026-08-02T16:25:00+09:00", "mode": "sales", "campaign": "trial-e2e-fashion-gadget-sales", "product": null, "angle": "タイプ別比較(涼しさとおしゃれの両立)", "format": "single_post", "cta_type": "link_click", "disclosure_included": true, "draft_text": "涼しさとおしゃれ、タイプによって向き不向きがある。ネッククーラー型は静音性重視、ハンディ型は携帯性重視、首掛けファン型はバランス型。自分の使い方に合うタイプで選ぶと失敗しにくい。タイプ別の比較はこちらから見られます。本投稿はAmazonアソシエイトとして紹介料を得ています。", "final_text": "涼しさとおしゃれ、タイプによって向き不向きがある。ネッククーラー型は静音性重視、ハンディ型は携帯性重視、首掛けファン型はバランス型。自分の使い方に合うタイプで選ぶと失敗しにくい。タイプ別の比較はこちらから見られます。本投稿はAmazonアソシエイトとして紹介料を得ています。", "asset_ids": [], "link_id": "dummy-link-e2e-007", "status": "approved", "approved_by": "affiliate-compliance-reviewer"}
```

3行とも `schemas/post_log.schema.json` に対してバリデーション済み（必須項目・enum・`post_id`パターンすべて適合）。`disclosure_included: true` は案F初稿にも設定した — これは「開示テキスト自体は存在した（#PRのみ）が、内容として不十分だった」ケースであり、boolean型の`disclosure_included`は"開示の有無"のみを表し"開示の強さ・明確さ"までは表現できない点に注意（詰まり参照）。

---

## 8. performance-analyst — 販売モードでログが溜まったら見るべき観点

- **CTA type別の`ctr`/`conversion`**: 今回は`link_click`のみだが、`purchase_consideration`や`compare_view`等が増えた場合にどのCTA typeが成果に結びつきやすいかを比較する
- **比較訴求 vs ベネフィット訴求の成果差**: タイプ別比較のような「選び方支援」型と、単純な「これがいい」ベネフィット訴求型で`conversion`にどう差が出るか
- **disclosureの強さ（明確さ）と`ctr`の関係**: 開示を明確にすることで信頼性が上がり`ctr`が伸びるのか、あるいは変化がないのかを見る。**ただし開示を弱めることでのクリック率最適化は方針として行わない**（`disclosure-policy.md`に反するため、分析結果に関わらず不採用）
- **needs_revision発生率と売り込み強度の関係**: 断定語の数・緊急性演出の有無別に`needs_revision`率を集計し、どの訴求パターンがコンプラリスクを生みやすいかを可視化する

（今回は実数値がないため、分析そのものは未実施）

---

## 閉ループの検証結果

- 案E: 初稿のまま`approved`
- 案F: 初稿`needs_revision` → 同一post_id維持で再提出 → 再レビューで`approved`

**reviewer / disclosure / approval / loggerの閉ループは成立した。** 販売モードで最も厳格な観点（disclosure、断定表現、根拠のない緊急性、CTA強度）による差し戻しから、再提出・再レビューを経て承認に至る一連の流れを、schemaバリデーション込みで確認できた。

## logger観点でのstatus / post_id / formatの妥当性

- `status`遷移: `needs_revision` → `approved`（同一post_id内で2行）。1本目・2本目と同じ「最新`created_at`が現在ステータス」というルールで一貫している
- `post_id`: 案F初稿と修正版で同一post_idを維持し、新規発行はしていない（既存ルールどおり）
- `format`: `thread`（案E）／`single_post`（案F）ともにschema enumの範囲内
- `approved_by`: `approved`の行のみ`affiliate-compliance-reviewer`が入り、`needs_revision`の行は`null`のまま — スキーマの意図どおり

---

## 販売モードで初めて見えた設計上の詰まり

1. **`disclosure_included`がboolean型のため、「開示はあるが弱い・曖昧」という状態を表現できない** — 案F初稿の「#PR」のみのケースは`disclosure_included: true`にせざるを得ず、真の問題（開示の明確さ不足）がログ上では見えない
2. **`link_id`がダミー値運用の際、trial由来のダミーリンクか本番リンクかをログ上で区別する仕組みがない** — 今回`dummy-link-e2e-XXX`という命名で区別したが、これはこの試走限りの自己流であり、正式なルールとして定義されていない
3. **`templates/review_template.md`の「判定理由」が自由記述のみで、差し戻し理由を構造的なカテゴリ（disclosure/exaggeration/urgency/cta_strength等）で分類できない** — 案Fは4つの観点にまたがる差し戻しだったが、これを集計・分析する仕組みが今はない（performance-analystが将来「needs_revision発生率と売り込み強度の関係」を見る際、この分類がないと手作業での再分類が必要になる）

## 次に修正すべき点（最大3点）

1. `review_template.md`の判定理由に、構造化タグ（例: `disclosure` / `exaggeration` / `urgency` / `cta_strength` / `comparison_basis`）を追加する案の検討（差し戻し理由の集計をしやすくするため）
2. `link_id`のダミー値運用ルールの明文化（例: 試走・ダミー時は`dummy-`プレフィックスを必須とする運用ルールをlogger関連ドキュメントに記載）
3. `disclosure_included`のboolean→enum化（例: `none` / `weak` / `clear`）の要否検討（ただしschema変更を伴うため、今回は提案のみで実施は保留が妥当）

いずれも今回はコード・ドキュメントの修正は行っていない（提案止まり）。

## レポート名について

`ops/reports/dryrun_2026-08-02_fashion-gadget_sales.md` は、1本目・2本目で確立した命名規則 `dryrun_YYYY-MM-DD_<category>_<mode>.md` と一貫しており適切。本ファイル自体がこの名前で保存されている。
