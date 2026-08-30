# 学習モード週次研究集計（Run10〜12 + mainline-run-2026-08-29-001/002, 2026-08-30-003/004 / METAGATE-DIVERGENCE-01・ASYNC-ENRICHMENT-REDESIGN-01との接続）

構造化データ: [weekly_learning_review_2026-08-28_initial.json](weekly_learning_review_2026-08-28_initial.json)
雛形: [weekly_learning_review_template_2026-08-28.md](weekly_learning_review_template_2026-08-28.md)
実装: `scripts/weekly_learning_review.py`（`aggregate_weekly_learning_review()`）

**更新履歴**: 初回はRun10〜12（既存レポートからの再構成データ）のみで集計。mainline-run-2026-08-29-001/002・2026-08-30-003の追記でLayer1/2実データを導入。本更新でmainline-run-2026-08-30-004（`minimal_run_log_2026-08-30_mainline-run-2026-08-30-004.json`/`enrichment_record_2026-08-30_mainline-run-2026-08-30-004.json`）を追加した。

対象期間: 2026-08-27 〜 2026-08-30（対象run: 7件）

## 1. 今週の本線運用状況

- 総run数: 7
- `mainline_status=completed`: 7件
- `closed_incomplete`: 0件
- `failed`: 0件

## 2. enrichment実行状況

- `completed`: 7件
- `partial`: 0件
- `failed_non_blocking`: 0件
- `not_started`: 0件

## 3. divergence発生状況

- `structure_hook_divergence=true`: 5件
- non-divergence: 2件

## 4. human vs structure/hook傾向

- split時にstructure側が的中: 2件
- split時にhook側が的中: 3件
- split時にどちらとも不一致: 0件

## 5. contamination / fallback / source variability

- Step A disclosure contamination: 1件
- fallback source使用率: 14%（1/7件）
- source別分布: {'2092424287672311915': 2, '2092972468260774213': 1, '2093229163213996215': 1, '2093563849580691551': 3}
- split発生5件のうち、structure側が的中2件、hook側が的中3件、どちらとも不一致0件
- Step A disclosure contaminationが1件発生した
- fallback source使用率: 14%（1/7件）

## 6. 次週の研究フォーカス

- Run14: divergence meta-gateのguarded live forward validation（新規source優先、研究専用の厳密プロトコルで）
- non-divergenceのguarded live例をもう1本以上確保する（Run10はcontaminationのため代替が必要）
- gadget teacher supplyの安定化（本線条件とは分離した別issueとして継続。同一source(2093563849580691551)への依存が続いており、新規source開拓が引き続き課題）
- non-divergenceでのmachine-human不一致（mainline-run-2026-08-30-003）を含め、auto_candidate_okの安全性検証を継続

## 7. one_line_takeaway

7件のmainline runはすべて完了。splitは5件（structure的中2件・hook的中3件）、non-divergenceは2件（うち1件はmachine-human不一致）——hook側の的中がやや優勢になってきたが、n=7ではまだ断定できず、divergence・non-divergenceいずれの場合も人間レビュー前提の運用を継続する

## 対象run一覧

| run | データ種別 | 位置づけ |
|---|---|---|
| Run10 | 再構成（既存レポートより） | mainline completed。structure=hook=human 3者一致だが、Step A disclosure contaminationのため`human_initial_top`はnull扱い |
| Run11 | 再構成（既存レポートより） | mainline completed。split発生、hook側がhuman final judgmentに一致 |
| Run12 | 再構成（既存レポートより） | mainline completed。split発生、structure側がhuman final judgmentに一致 |
| mainline-run-2026-08-29-001 | 実データ | mainline completed。split発生、hook側（案H）がhuman selectionに一致。実投稿済み |
| mainline-run-2026-08-29-002 | 実データ | mainline completed。split発生、structure側（案J）がhuman selectionに一致。実投稿は未実施 |
| mainline-run-2026-08-30-003 | 実データ | mainline completed。non-divergence（structure=hook=案K）だが、human selectionは案L——structure/hookどちらとも不一致。実投稿は未実施 |
| **mainline-run-2026-08-30-004** | **実データ** | **mainline completed。split発生、hook側（案M）がhuman selectionに一致。実投稿は未実施** |

**Run13・METAGATE-DIVERGENCE-01・GOV-20260828-ASYNC-ENRICHMENT-REDESIGN-01は投稿runではないため対象外**（Run13=evaluator redesign/replay資産、METAGATE-DIVERGENCE-01=divergence判定ロジックそのもの、ASYNC-ENRICHMENT-REDESIGN-01=本集計が実装する3層構造の設計元）。既存run（Run10〜13）の元のfinal_verdict・PDCA記録は遡及的に変更していない。
