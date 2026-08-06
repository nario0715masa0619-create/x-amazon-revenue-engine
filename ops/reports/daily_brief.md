# daily_brief.md — 日次ブリーフ（テンプレート）

> mode-orchestratorが自動生成・維持するAI主導の記録。**人間が毎日ゼロから埋める運用ではない。** 当日方針の決定は`.claude/skills/morning-strategy-council/SKILL.md`（Morning Strategy Brief）が担い、このファイルはその後の実行結果・記録を控える場所に役割を絞る（[phase1_acquisition_launch_spec_2026-08-03.md](phase1_acquisition_launch_spec_2026-08-03.md)の「最小オペレーション標準フロー」参照）。人間の入力が必要な欄には都度「（人間が入力）」と明記し、それ以外は原則AI側が埋める。

## 対象日

YYYY-MM-DD

## 現在モード

- `ops/state/current_mode.yaml` の値: (AI記入)
- 直近のモード別投稿比率（実績）: 集客 __% / 教育 __% / 販売 __%（AI記入）

## 前日の実績サマリ

- 投稿件数・特筆すべき数値変化・ログの欠損（AI記入。performance-analystが要約）

## 本日の方針（Morning Strategy Briefからの転記）

- 採択されたテーマ・角度・フック方向・CTA方針（AI記入。人間が朝会で選んだ結果をここに転記するのみで、このファイル側で改めて計画を書く必要はない）

## 実投稿記録（投稿完了後。**人間の入力は投稿URLのみ**）

承認済み候補（`post_log.jsonl`の`status: approved`）はpost_idが既に確定しているため、AI（logger）が行を事前に用意する。人間は**投稿URLを貼るだけ**でよい。投稿時刻はURL記入時点、投稿者は既定値（単独運用中は固定名）をAI側で補う。

| post_id | 投稿URL（人間が入力） | 投稿時刻（AI補完） | 投稿者（AI補完・既定値） |
|---|---|---|---|
| （AI事前記入） | | | |

## 24時間後実績記録（投稿翌日。**現在は暫定評価フェーズ中のスクショ運用**）

**現在はPhase 1の暫定評価フェーズ中。** X API半自動化（x-metrics-collector）はコードとして温存しているが、課金判断が下りるまで正式レーンとして起動しない（詳細: [provisional_evaluation_phase_2026-08-04.md](provisional_evaluation_phase_2026-08-04.md)）。人間は見えている数値のスクリーンショットを1枚渡すだけでよく、AIが見えた値だけ`metrics_24h`に記入する。**空欄＝未取得**（「未取得」と書き添える必要はない）。最小5項目: `impressions` / `likes` / `replies` / `profile_visits` / フォロワー純増数（参考）。`data_quality`は`manual`とし、`notes`に「スクショ確認ベース」と見えた範囲を残す。`link_clicks`等リンク関連はAIが常に`0`で補う（集客モードはリンクを使わないため実測ゼロ）。

| post_id | impressions（人間） | likes（人間） | replies（人間） | profile_visits（人間） | フォロワー純増数・参考（人間） |
|---|---|---|---|---|---|
| （AI事前記入） | | | | | |

## 投稿案の競合比較記録（複数候補から1本を選んだ場合のみ。AI記入）

**2026-08-06追加**: `post_log.schema.json`に`notes`フィールドが存在しないため（2026-08-06の機能監査で判明）、複数候補を比較した際の競合比判定・採否理由はここに記録する（schema変更なし。`posted_url`等と同じく、schemaに格納場所がない情報を扱う欄）。詳細は[.claude/agents/logger.md](../../.claude/agents/logger.md)の「競合比判定の記録」参照。

| 対象日 | 採用post_id | 不採用post_id | hook_competitor_assessment（採用案） | whole_post_competitor_assessment（採用案） | strongest_axis | weakest_axis | why_selected | why_rejected（不採用案） |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

## スキップ/持ち越し記録（AIが下書き、人間は確認のみ）

当日中に`approved`が出ない場合、mode-orchestratorが状況・理由・翌日の扱い案を自動で下書きする。人間はそれを確認し、必要なら1点だけ修正すればよい（ゼロから書かない）。

| 対象post_id | 状況（AI記入） | 理由（AI記入） | 翌日の扱い案（AI記入） | 人間の確認・修正（あれば） |
|---|---|---|---|---|
| | | | | |

## 懸念・要確認

- (AI記入。人間の判断が必要な項目のみ、ここに絞って提示する)
