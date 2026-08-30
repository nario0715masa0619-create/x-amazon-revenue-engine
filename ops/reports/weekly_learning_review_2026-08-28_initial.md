# 学習モード週次研究集計（Run10〜12 + mainline-run-2026-08-29-001/002, 2026-08-30-003 / METAGATE-DIVERGENCE-01・ASYNC-ENRICHMENT-REDESIGN-01との接続）

構造化データ: [weekly_learning_review_2026-08-28_initial.json](weekly_learning_review_2026-08-28_initial.json)
雛形: [weekly_learning_review_template_2026-08-28.md](weekly_learning_review_template_2026-08-28.md)
実装: `scripts/weekly_learning_review.py`（`aggregate_weekly_learning_review()`）

**更新履歴**: 初回はRun10〜12（既存レポートからの再構成データ）のみで集計。mainline-run-2026-08-29-001/002の追記でLayer1/2実データを導入。本更新でmainline-run-2026-08-30-003（`minimal_run_log_2026-08-30_mainline-run-2026-08-30-003.json`/`enrichment_record_2026-08-30_mainline-run-2026-08-30-003.json`）を追加した。

対象期間: 2026-08-27 〜 2026-08-30（対象run: 6件）

## 1. 今週の本線運用状況

- 総run数: 6
- `mainline_status=completed`: 6件
- `closed_incomplete`: 0件
- `failed`: 0件

## 2. enrichment実行状況

- `completed`: 6件
- `partial`: 0件
- `failed_non_blocking`: 0件
- `not_started`: 0件

## 3. divergence発生状況

- `structure_hook_divergence=true`: 4件
- non-divergence: 2件

## 4. human vs structure/hook傾向

- split時にstructure側が的中: 2件
- split時にhook側が的中: 2件
- split時にどちらとも不一致: 0件

## 5. contamination / fallback / source variability

- Step A disclosure contamination: 1件
- fallback source使用率: 17%（1/6件）
- source別分布: {'2092424287672311915': 2, '2092972468260774213': 1, '2093229163213996215': 1, '2093563849580691551': 2}
- split発生4件のうち、structure側が的中2件、hook側が的中2件、どちらとも不一致0件
- Step A disclosure contaminationが1件発生した
- fallback source使用率: 17%（1/6件）

## 6. 次週の研究フォーカス

- Run14: divergence meta-gateのguarded live forward validation（新規source優先、研究専用の厳密プロトコルで）
- non-divergenceのguarded live例をもう1本以上確保する（Run10はcontaminationのため代替が必要）
- gadget teacher supplyの安定化（本線条件とは分離した別issueとして継続）
- mainline-run-2026-08-30-003はnon-divergence（structure=hook=K）だがhuman選択はLで、structure/hookどちらとも不一致という新パターンを観測——non-divergence=auto_candidate_okの妥当性を見直す材料として次週以降も追跡

## 7. one_line_takeaway

6件のmainline runはすべて完了し、split 4件ではstructure的中2件・hook的中2件で拮抗、さらにnon-divergenceでもmachine-human不一致が1件出たため、現時点ではどちらか一方の自動優位やauto_candidate_okの安全性を断定せず、人間レビュー前提で運用しながら追加データを蓄積するのが妥当である。

## 対象run一覧

| run | データ種別 | 位置づけ |
|---|---|---|
| Run10 | 再構成（既存レポートより） | mainline completed。structure=hook=human 3者一致だが、Step A disclosure contaminationのため`human_initial_top`はnull扱い |
| Run11 | 再構成（既存レポートより） | mainline completed。split発生、hook側がhuman final judgmentに一致 |
| Run12 | 再構成（既存レポートより） | mainline completed。split発生、structure側がhuman final judgmentに一致 |
| mainline-run-2026-08-29-001 | 実データ | mainline completed。split発生、hook側（案H）がhuman selectionに一致。実投稿済み |
| mainline-run-2026-08-29-002 | 実データ | mainline completed。split発生、structure側（案J）がhuman selectionに一致。実投稿は未実施 |
| **mainline-run-2026-08-30-003** | **実データ** | **mainline completed。non-divergence（structure=hook=案K）だが、human selectionは案L——structure/hookどちらとも不一致。実投稿は未実施** |

**Run13・METAGATE-DIVERGENCE-01・GOV-20260828-ASYNC-ENRICHMENT-REDESIGN-01は投稿runではないため対象外**（Run13=evaluator redesign/replay資産、METAGATE-DIVERGENCE-01=divergence判定ロジックそのもの、ASYNC-ENRICHMENT-REDESIGN-01=本集計が実装する3層構造の設計元）。既存run（Run10〜13）の元のfinal_verdict・PDCA記録は遡及的に変更していない。
