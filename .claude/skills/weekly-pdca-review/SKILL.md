---
name: weekly-pdca-review
description: 週次で実績ログから勝ち筋・負け筋を抽出し、来週の改善方針に落とすためのskill。performance-analystの分析結果を受けて、skills/docs/stateへの反映まで行う。週次レビューを実施するときに使う。
---

# weekly-pdca-review (週次PDCAレビュー)

## 目的

その週の投稿・施策・数値ログを振り返り、学びを構造化して次週の運用に反映する。振り返りをやりっぱなしにせず、必ず具体的な更新(state/playbook/docs)に落とすことがこのskillの存在意義。

## 使う場面

- 週次(推奨: 毎週決まった曜日)のレビュータイミング
- モード比率(`ops/state/mode_weights.yaml`)を見直したいとき
- 特定のplaybookが機能していない疑いがあるとき

## 入力

- performance-analyst による当該週の分析結果(モード別サマリ、勝ち筋・負け筋仮説)
- `ops/logs/post_log.jsonl`、`ops/logs/metrics_snapshots.csv`、`ops/logs/experiment_log.jsonl` の当該週分
- 前週の `ops/reports/weekly_review.md`(あれば、比較のため)

## 出力

- `ops/reports/weekly_review.md` の更新(`templates/weekly_report_template.md` の形式に準拠)
- 必要に応じた `ops/state/mode_weights.yaml` の更新提案
- 必要に応じた `docs/playbooks/*.md` の更新提案(playbookの前提が実態とずれている場合)
- 必要に応じた `.claude/skills/*/SKILL.md` のチェックポイント追加提案(繰り返し起きた失敗パターンがある場合)

## 手順

1. performance-analyst の分析結果を確認する(なければ先に分析を依頼する)
2. モード別のKPI達成状況を `templates/weekly_report_template.md` に沿って整理する
3. 勝ち筋・負け筋を、再現性のある要因に分解する(フックの型、CTA、投稿時間帯、商品カテゴリ等)
4. 学びをもとに、以下のうちどれに反映すべきかを判断する:
   - **state**: モード比率を変えるべきか(`mode_weights.yaml`)
   - **playbook/docs**: 設計方針そのものを見直すべきか(`docs/playbooks/*.md`)
   - **skill**: 特定モードのチェックポイントを追加すべきか(`.claude/skills/*/SKILL.md`)
5. `ops/reports/weekly_review.md` に反映内容を明記して保存する

## チェックポイント

- [ ] 分析はサンプル数が十分な範囲での結論になっているか
- [ ] 「学び」が具体的な更新(state/playbook/skill)に落ちているか、感想で終わっていないか
- [ ] mode_weightsを変更する場合、変更理由が明記されているか
- [ ] 前週との比較(改善/悪化)が明確か

## 失敗例

- 数値を眺めるだけで終わり、どのファイルも更新されない(PDCAのAがない)
- サンプル数1件の結果を「勝ち筋」として一般化してしまう
- mode_weightsを感覚で変更し、理由がweekly_review.mdに残らない
- 良かった点だけを記録し、負け筋(避けるべきパターン)を記録しない
