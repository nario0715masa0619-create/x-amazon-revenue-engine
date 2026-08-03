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

- 40代向けの落ち着きがあるか
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

## 判定

`go` / `revise` / `stop`

- `go`: 主要観点に問題なし。このままaffiliate-compliance-reviewerへ提出してよい
- `revise`: 公開は可能だがフックやトーンの修正余地がある
- `stop`: アカウント設計を壊す、または危険表現がある。構成から見直す

## 出力形式

毎回、以下の形式で返す:

- 総合判定(`go`/`revise`/`stop`)
- 5観点の短評(各1〜2行)
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

- [ ] 5観点すべてに短評が付いているか
- [ ] `revise`判定なのに修正版が付いていないケースがないか
- [ ] self-check通過を理由にaffiliate-compliance-reviewerへの提出を省略していないか
- [ ] 同一案への再提案が2回目に達していないか(ループ防止)

## 失敗例

- self-checkで`go`が出たことを理由に、affiliate-compliance-reviewerへの提出を省略してしまう(このskillはreviewerの代替ではない)
- `revise`の修正を繰り返し行い、reviewerに渡すタイミングを逃す(1回修正ルールを破る)
- `audience_fit_40s`の観点を、別のアカウント設計に流用する際に観点名だけ変えて中身(判定基準)を使い回してしまう
- 「バズるかどうか」を断定的に評価してしまう(このskillは相対評価に留める設計)
