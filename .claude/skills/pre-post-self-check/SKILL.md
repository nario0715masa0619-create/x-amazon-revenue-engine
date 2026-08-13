---
name: pre-post-self-check
description: x-copywriterが投稿案をaffiliate-compliance-reviewerに提出する前に行う自己点検。フックの強さ・ターゲット適合性・モード適合性・プロフィール遷移ポテンシャル・危険表現の有無を評価し、go/revise/stopの判定と(revise時は)修正版1案を返す。affiliate-compliance-reviewerの代替ではなく、その前段に置く品質向上レイヤー。x-copywriterが投稿案を作成した直後に使う。
---

# pre-post-self-check

## 目的

- x-copywriterが作成した投稿案を、affiliate-compliance-reviewerに渡す前に自己点検する
- フックの強さ、ターゲット適合性、モード適合性、プロフィール遷移ポテンシャル、危険表現の有無を確認する
- 「バズるか」を断言せず、「反応の取りやすさ」「スクロール停止力」「拡散ポテンシャル」を相対評価する(過度な断定はしない)
- 必要なら軽微な修正案を1本返す
- **affiliate-compliance-reviewerの代替ではない。その前段に置く品質向上レイヤー**

## 使う場面

- x-copywriterが投稿案を作成した直後、affiliate-compliance-reviewerに提出する前
- 現在のモード・アカウント設計に照らして粗い案を早期に落としたいとき

## 入力

- x-copywriterが作成した投稿案(`templates/x_post_template.md`準拠)
- 現在のモード(mode依存部分は下記チェック観点内で明示。現状は`acquisition`を主眼に設計している)
- アカウント設計(現状: 40代ファッション×ガジェット。清潔感/上質感/実用性/無理のなさを重視し、若作り訴求・テンション高めの煽り・安さ一辺倒・若年層向け流行語を避ける。`ops/reports/phase1_acquisition_launch_spec_2026-08-03.md`参照)

## チェック観点(5項目)

### 1. hook_strength(フックの強さ)

- 冒頭1文で読者が止まるか
- 抽象的すぎないか
- 読者の生活シーンに着地しているか

### 2. audience_fit_40s(ターゲット適合性) ※アカウント設計依存、mode非依存

- 40代男性向けの落ち着きがあるか
- 清潔感/上質感/実用性/無理のなさを壊していないか
- 若作り訴求や若年層ノリになっていないか
- 別のアカウント設計に切り替える場合、この観点はそのアカウント設計の重視する価値観に置き換える(観点名・判定基準はアカウント設計に依存し、mode切り替えとは別軸で管理する)

### 3. acquisition_fit(モード適合性) ※mode依存

- 売り込み感が強すぎないか
- 集客モードとして自然な興味喚起になっているか
- 教育/販売モード寄りにズレていないか
- 教育/販売モードに拡張する場合、この観点は`education_fit`/`sales_fit`に置き換え、`docs/playbooks/`の該当モード定義に沿って判定基準を差し替える

### 4. profile_visit_potential(プロフィール遷移ポテンシャル) ※mode依存(現状はCTA type: `profile_visit`前提)

- 続きが気になってプロフィールへ行く導線になっているか
- CTAが弱すぎて行動につながらない、または強すぎて安っぽく見えないか
- 教育/販売モードでは`save_potential`/`link_click_potential`等、CTA typeに応じた観点に置き換える

### 5. risk_level(危険表現の有無) ※mode非依存、全モード共通

- 誇大表現
- 断定表現
- 安っぽい煽り
- 不自然に強い緊急性
- アカウント設計からの逸脱

### 6. hook_vs_competitors(競合比でのフック強度) ※2026-08-04追加。集客モードで重視

- 一文目だけを切り出して、競合（直接／間接／準ベンチマーク）と比べて強い／同等／弱いか
- 「一文目だけ見て続きを読みたくなるか」を強く見る
- `market-grounded review layer`の`hook_assessment`と矛盾する場合は、その旨を明記する（自分の判断で上書きしない）

### 7. differentiation_vs_competitors(競合比での差別化) ※2026-08-04追加。集客モードで重視

- よくある整理論・身だしなみ論・生活感論に埋もれていないか
- 競合と比べて差別化できているポイントがあるか

### 8. profile_visit_reason_strength(プロフィール遷移理由の強さ) ※2026-08-04追加。集客モードで重視

- プロフィールへ飛ぶ理由が自然に生まれているか
- CTAの文言だけでなく、フック〜本文の流れ全体としてプロフィールへの興味を作れているか

### 9. value_card_fidelity(価値カードとの整合) ※2026-08-07追加、2026-08-08よりPhase B・正式運用。価値カードを使った案のみ

- x-copywriterが出した「価値保持宣言」（[ops/reports/value_transfer_design_2026-08-07.md](../../../ops/reports/value_transfer_design_2026-08-07.md)参照）で「保持する」と宣言した不変要素が、実際の本文に残っているかを照合する
- 宣言と本文が食い違う場合（例: 「他者の視線を保持する」と宣言したのに本文では内面的な気づきのみになっている）は、その旨を明記する（自分の判断で宣言を上書きしない。`market-grounded review layer`の`transfer_fidelity`と矛盾する場合も同様に併記する）
- 価値カードを使わない日（新規探索日）はこの観点を省略してよい

### 10. hook_visibilityの自己点検 ※2026-08-09追加

- x-copywriterがMode 1（戦略可視化）で宣言した「想定フック」（読者が止まる理由）が、実際の本文の一文目から読み取れるか照合する
- 出来事の説明に留まり、停止理由が見えていない場合はその旨を明記する

### 11. target_clarityの自己点検 ※2026-08-09追加

- Mode 1で宣言した「想定ターゲット」（40代男性のどの層か）が、本文の具体性から読み取れるか照合する
- 場面が一般化されすぎて対象が曖昧になっていないか確認する

### 12. CTA bridgeの自己点検 ※2026-08-09追加

- Mode 1で宣言した「プロフィール遷移理由」が、本文内で実際に成立しているか照合する
- CTA文言だけに遷移理由を頼っていないか確認する

## 判定

`go` / `revise` / `stop`

- `go`: 主要観点に問題なし。**かつ`hook_vs_competitors`/`differentiation_vs_competitors`が「弱い」ではない。かつhook_visibility/target_clarity/CTA bridgeの自己点検で問題が見つかっていない**（2026-08-09追加）。このままaffiliate-compliance-reviewerへ提出してよい
- `revise`: 公開は可能だがフックやトーンの修正余地がある。**「安全だが弱い（weak but safe）」案、つまり誇大表現等はないが競合比で弱い案は`go`にせず`revise`とする**
- `stop`: アカウント設計を壊す、または危険表現がある。構成から見直す

**2026-08-04改訂**: 集客モードでは「破綻していないか」だけでなく「競合比で強いか」を判定に含める（[phase1 spec](../../../ops/reports/phase1_acquisition_launch_spec_2026-08-03.md)の「集客モードの評価思想」参照）。危険表現がなく無難にまとまっているだけの案（weak but safe）を安易に`go`にしない。

## 出力形式

毎回、以下の形式で返す:

- 総合判定(`go`/`revise`/`stop`)
- 12観点の短評(各1〜2行。価値カードを使わない日は`value_card_fidelity`を「該当なし」と記す)
- 強み
- 弱み
- 危険表現の有無
- 修正方針(`revise`/`stop`の場合)
- 修正版1案(`revise`の場合のみ。`stop`の場合は構成からの見直しが必要なため修正版は出さない)

## 運用ルール

- このskillはaffiliate-compliance-reviewerの代替ではない。self-checkで`go`でも、最終レビューは必ずreviewerを通す。self-check通過を理由にレビュー提出を省略しない
- self-checkで`revise`の場合、x-copywriterは**1回だけ**修正してaffiliate-compliance-reviewerに提出する(自己修正のループを防ぐため)
- self-checkで`stop`の場合、x-copywriterは構成から見直す(小手先の修正では対応しない)
- **ループ防止**: このskillは同一投稿案に対して最大1回の再提案に留める。2回目のself-checkでも`revise`/`stop`が続く場合は、そのままaffiliate-compliance-reviewerに提出し判断を委ねる(self-check単体で無限に往復しない)

## チェックポイント

- [ ] 12観点すべてに短評が付いているか(価値カード未使用日は`value_card_fidelity`を「該当なし」と明記)
- [ ] `revise`判定なのに修正版が付いていないケースがないか
- [ ] 危険表現がないだけで「安全だが弱い」案を`go`にしていないか
- [ ] self-check通過を理由にaffiliate-compliance-reviewerへの提出を省略していないか
- [ ] 同一案への再提案が2回目に達していないか(ループ防止)
- [ ] 価値カードを使った案で、宣言した不変要素が本文に残っているか確認したか(2026-08-08よりPhase B・正式運用)
- [ ] Mode 1の宣言（想定フック／想定ターゲット／プロフィール遷移理由）と本文が一致しているか確認したか(2026-08-09追加)

## 失敗例

- self-checkで`go`が出たことを理由に、affiliate-compliance-reviewerへの提出を省略してしまう(このskillはreviewerの代替ではない)
- `revise`の修正を繰り返し行い、reviewerに渡すタイミングを逃す(1回修正ルールを破る)
- `audience_fit_40s`の観点を、別のアカウント設計に流用する際に観点名だけ変えて中身(判定基準)を使い回してしまう
- 「バズるかどうか」を断定的に評価してしまう(このskillは相対評価に留める設計)
- 誇大表現や危険表現がないことだけを根拠に`go`にしてしまい、競合比で埋もれている（weak but safe）ことを見落とす
- `transfer_fidelity`/`value_card_fidelity`が全て「保持」であることだけを根拠に`go`にしてしまい、フックが誰の何を刺す文か本文から見えない（`hook_visibility`/`target_clarity`が弱い）ことを見落とす（2026-08-09追加。「価値カードの整合性」と「本文の可視性」は別問題）
