---
name: morning-strategy-council
description: 毎朝、投稿文を作る前に「今日何を狙うか」を決める戦略会議skill。trend-analyst/competitor-analyst/audience-representative/growth-strategist/risk-compliance-observerの5役が短い所見を出し、council-chairが要約してMorning Strategy Briefにまとめる。人間が方針を採択した後、execution layer(mode-orchestrator以降)に引き継ぐ。投稿文そのもののレビューではなく上流の戦略決定。
---

# morning-strategy-council

## 目的

その日の投稿を作り始める前に、前日実績・競合実態・トレンド実態・アカウント設計を材料として、「今日何を狙うか」をAI側で先に整理する。人間はゼロから方針を考えるのではなく、AIがまとめた候補から選ぶだけで済むようにする。**投稿文そのものを議論する機能ではなく、投稿文が存在する前の上流の戦略決定である。**

## 使う場面

- 毎朝、その日の投稿候補生成（execution layer）を始める前
- 前日実績が過去最低だった等、感覚論ではなく戦略修正が必要なとき
- 新テーマへの切り替えを検討するとき

## 入力

- 日付
- current mode（`ops/state/current_mode.yaml`）
- アカウント設計（40代ファッション×ガジェット。`ops/reports/phase1_acquisition_launch_spec_2026-08-03.md`）
- 直近投稿の要約
- 直近の24時間後実績（あれば。`ops/logs/metrics_snapshots.csv`、`ops/reports/daily_brief.md`）
- 今週のテーマ計画（T1/T2/T3）
- 画像テスト予定の有無（`ops/reports/week2_image_ab_test_plan_2026-08-03.md`）
- 競合候補URLまたは検索結果（ある場合）
- 参照ドキュメント: `README.md`、`CLAUDE.md`、`ops/reports/phase1_acquisition_launch_spec_2026-08-03.md`、`ops/reports/next_phase_alignment_review_2026-08-03.md`、dry runレポート群、`docs/roles/`、`docs/policies/`、`templates/`

## 参加AI（5役＋1議長）

**2026-08-04改訂**: 集客モードの判定は「破綻していないか」ではなく「競合比で強いか・弱いか・同等か」を中核とする（[phase1_acquisition_launch_spec_2026-08-03.md](../../../ops/reports/phase1_acquisition_launch_spec_2026-08-03.md)の「集客モードの評価思想」参照）。朝会は単に「何を変えるか」を決めるだけでなく、**今日勝ちに行く比較軸を明示する場**とする。

| 役割 | 見るもの | 出力 |
|---|---|---|
| trend-analyst | X公式ベストプラクティス、直近トレンド | 今日避けるべき型／今日試す価値のある型（**今のXで止まりやすい型と比べた相対的な強弱、一文目の勢いを必ず見る**） |
| competitor-analyst | 近接ジャンルの公開投稿傾向 | よくある型／避けるべき被り／差別化できそうな切り口（**競合にありがちなフックと比べた強い点・同等な点・弱い点を必ず出す**） |
| audience-representative | アカウント設計、トーン／禁止表現ルール | 40代男性に刺さる観点／避けるべき言い回し／今日のトーン指針（**「刺さらない理由」を遠慮なく出す。男女共通の抽象論に落ちていないかを強く監視する**） |
| growth-strategist | 前日実績、スプリント計画、current mode | 今日のテスト仮説／固定する要素・変える要素／今日の成功判定（**変える1変数が競合比のどの弱点を改善するためかを明示し、単なる比較可能性ではなく勝ち筋として意味のある差分かを判断する**）。**2026-08-08よりPhase B・正式運用: 使用する価値カードID／source_post_id／evidence_basis／固定する不変要素／試す可変要素（原則1つ）も明示する。詳細は[ops/reports/value_transfer_design_2026-08-07.md](../../../ops/reports/value_transfer_design_2026-08-07.md)参照** |
| risk-compliance-observer | policy docs、Xプラットフォームルール | 今日の注意点／やってはいけない表現（**役割は維持。ただし安全性だけで採択方向に寄せない。「強さは別問題」と明示する**） |
| council-chair | 上記5役の所見 | Morning Strategy Brief（結論のみ、新規意見を足さない。**競合比で見た総合判定／今日勝ちに行く軸／今日の案が競合比で弱くなりやすいポイントを必ずまとめる**） |

## 手順

1. council-chairが上記入力を5役に共有する
2. 5役は各自、独立して所見を出す（**他の役の所見への反論・再討論はしない。1回だけ所見を出す**）
3. council-chairが5役の所見を要約し、`templates/morning_strategy_brief.md`の形式でMorning Strategy Briefを出力する
4. 人間がBrief内の「2-3 candidate directions」から1つを採択する（または独自の判断で変更する）
5. 採択された方針を、その日限定の前提条件としてmode-orchestrator以降のexecution layerに引き継ぐ

## 出力

- `templates/morning_strategy_brief.md`準拠のMorning Strategy Brief 1件

## 人間承認ポイント

- **人間はBrief先頭のTL;DRと「Recommended direction」だけ読めば選べる。** Briefの「2-3 candidate directions for human approval」から、その日の投稿方針を1つ選ぶ
- 「Recommended direction」はAI側の推奨であり、人間は別の候補を選んでもよい
- 詳細欄（5役それぞれの所見）は、判断の根拠を確認したいときだけ読めばよく、毎回読む前提にしない（ユーザーオペレーション最小化の原則）

## execution layerへの引き継ぎ方法

- 採択された方針（テーマ・角度・フック方向・CTA方針・避ける表現）を、mode-orchestratorがその日の前提条件として受け取る
- x-researcher／growth-marketer／x-copywriterは、採択された方針に沿って動く。勝手に別テーマへ逸れない
- **この方針はその日限りの条件であり、`docs/playbooks/`や`.claude/skills/*-playbook/SKILL.md`等の恒久ルールを書き換えるものではない**
- 投稿文そのもののレビュー（market-grounded review layer、pre-post-self-check、affiliate-compliance-reviewer）はexecution layer側で別途行う。朝会はその代替ではない
- **2026-08-06追加（自己追認バイアスの防止）**: 採択された方針（「今日勝ちに行く軸」「今日のフック仮説」「Recommended direction」等）は**x-copywriterの執筆材料としてのみ**引き継ぐ。**`market-grounded review layer`（trend-reality-reviewer/competitor-reality-reviewer/audience-market-fit-reviewer）には渡さない。** 朝会が立てた仮説をreview layerがそのまま追認してしまう構造（2026-08-06の機能監査で実際に確認された不具合）を避けるため、reviewerには投稿案本文とテーマ／ターゲット／CTA等の客観条件のみを渡し、「どの仮説で書かれたか」は伝えない

## チェックポイント

- [ ] 5役の所見がそれぞれ独立して出ており、討論・反論になっていないか
- [ ] council-chairが新しい意見を足さず、要約に徹しているか
- [ ] 根拠が弱い項目に「insufficient evidence」等の明記があるか
- [ ] Briefに人間が選べる候補が2〜3個提示されているか
- [ ] 採択された方針が「その日限り」であり、playbook等の恒久ルールと混同されていないか
- [ ] 「競合比で今日勝ちに行く軸」「競合比で避けるべき弱さ」がBriefに明記されているか
- [ ] 採択された仮説・推奨方向が、x-copywriterにのみ引き継がれ、market-grounded review layerには渡っていないか（2026-08-06追加。自己追認バイアス防止）
- [ ] （価値カードを使う日のみ）「使用する価値カードID」「source_post_id」「evidence_basis」「固定する不変要素」「試す可変要素」がBriefに明記されているか（2026-08-08よりPhase B・正式運用）
- [ ] 「who_and_pain_summary」（誰の・どの痛みを狙うか）がBriefに一文で明記されているか（2026-08-09追加。5役所見の合成であり新しい主張ではないことを確認する）

## 失敗例

- 5役がお互いの所見に反論し、長い討論になってしまう
- council-chairが独自の新しい意見を追加してしまう（要約役に徹していない）
- 朝会の結論を「投稿文の最終承認」であるかのように扱い、affiliate-compliance-reviewerを省略してしまう
- 採択された当日方針を、翌日以降も自動的に引き継いでしまう（本来は日次でリセットされるべき）
- 朝会が示した仮説・推奨方向をmarket-grounded review layerにそのまま渡してしまい、reviewerが独立した検証ではなく仮説の追認になってしまう（2026-08-06追加。過去に実際に発生した不具合）
