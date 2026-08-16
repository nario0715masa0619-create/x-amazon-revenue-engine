# x_api_phase1_notes.md — X API Phase 1（複数クエリ収集）運用メモ

> [x_api_smoke_test_notes.md](x_api_smoke_test_notes.md)（Phase 0・単一クエリ疎通確認）の続き。短い運用メモのみ。

## 実行コマンド

```bash
python scripts/x_api_phase1_collect.py
```

引数なし実行のみ対応（Phase 1時点では未実装）。

## クエリの置き場所

[scripts/x_api_phase1_collect.py](../../scripts/x_api_phase1_collect.py)冒頭の`QUERIES`固定配列。現在は3クエリ・各`max_results=15`（合計45件、上限50件以内）。動的生成・最適化ロジックはまだ入れていない。クエリを変える場合はこの配列を直接編集する。

## 出力ファイルの意味

| ファイル | 内容 |
|---|---|
| `outputs/x_api_phase1/raw/query_0N.json` | クエリごとの生レスポンス（失敗時は失敗情報を保存） |
| `outputs/x_api_phase1/merged_before_dedup.json` | 全クエリの結果を単純結合したもの（重複除外前） |
| `outputs/x_api_phase1/merged_deduped.json` | `id`ベースdedup **+ 本文ハッシュdedup（Phase 1.1）**を経た最終一覧 |
| `outputs/x_api_phase1/merged_deduped.csv` | 人間確認用CSV（`public_metrics`をフラット化。`text_hash`/`duplicate_count_by_text`/`duplicate_post_ids`列を含む） |
| `outputs/x_api_phase1/text_duplicate_groups.json` | 本文重複としてまとめられたグループの詳細（代表post_id・重複post_id一覧等。重複が1件もない実行では生成されない） |
| `outputs/x_api_phase1/run_summary.json` | 実行日時・クエリ別件数・id/本文それぞれのdedup件数・成功/失敗ステータス |

いずれも`.gitignore`で除外済み（`outputs/x_api_phase1/`）。実行のたびに上書きされる。

## 重複除外の基準

**Step 1: idベースdedup（維持）**
- 主キーは`id`
- 同じ`id`が複数クエリでヒットした場合は1件にまとめる
- `query_source`はどのクエリでヒットしたかを配列で保持する

**Step 2: 本文ハッシュdedup（Phase 1.1で追加、2026-08-16）**
- idが別でも本文が実質同一（同一投稿の別ユーザーによるRT、同文再掲）なら1件にまとめる
- 正規化（[scripts/x_api_phase1_collect.py](../../scripts/x_api_phase1_collect.py)の`normalize_post_text()`）: 前後空白除去／`RT @user:`・`QT @user:`プレフィックス除去／URLを`[URL]`に置換／改行・空白の正規化／小文字化 → `sha256`でハッシュ化
- 代表投稿の選定優先順位: impression_count最大 → like_count最大 → created_atが新しい → 最初の1件
- 代表投稿以外の`post_id`は`duplicate_post_ids`として保持し、後から追跡できる
- 意味類似judgeやLLM判定は行わない。あくまで「ほぼ同文」のみを対象とする保守的なdedup
- `merged_deduped.json`/`.csv`は**idと本文の両方で重複除外した後**の件数を表す（Phase 1.1以前は`id`のみだったため、`total_after_dedup`等の意味が変わっている点に注意。内訳は`run_summary.json`の`dedup_by_id_count`/`dedup_by_text_count`で確認できる）

## 失敗時の確認ポイント

- `X_BEARER_TOKEN`未設定: API呼び出し前に即終了
- クエリ単位の失敗（401/403/429/5xx）は**そのクエリだけスキップし、他クエリは継続実行する**（全体は止めない）
- 失敗したクエリの詳細は`run_summary.json`の`failures`配列、および該当する`raw/query_0N.json`に記録される
- 全クエリが失敗した場合のみ、non-zero exitで終了する

## 次フェーズに進む判断基準

- 複数クエリ実行・重複除外・CSV出力が安定して再現すること（本メモの実行結果で確認済み: 3クエリ計45件取得、重複1件、44件に集約）
- 次フェーズ（候補整理・観察分類・教師候補選定）へ進む前に、実際の研究テーマに沿ったクエリでも同様に安定するかを別途確認するとよい（今回は`QUERIES`に汎用的な疎通確認用の語のみを使用しており、実務クエリでの検証はまだ行っていない）

## 実行結果（2026-08-15確認）

- 3クエリ実行、いずれも成功（失敗0件）
- マージ前総件数: 45／重複除外後: 44／重複: 1件
- CSV: 44行、全列が正しく埋まっていることを確認

## 実行結果（2026-08-16確認・Phase 1.1本文ハッシュdedup追加後）

- クエリは2語版のまま変更なし（`40代 持ち物`／`40代 小物`／`服 ガジェット`）
- マージ前総件数: 36／idベースdedup後: 36（除外0件）／本文ハッシュdedup後: 21（除外15件）
- 本文重複グループ: 2グループ（「白Tとデニム」RT+原本の2件グループ、「演劇ジャンキー」同文RTの15件グループ）
- X「recent search」は7日間のローリングウィンドウを持つライブ検索のため、実行のたびに母数（36件）は前回実行時（38件）と多少変動する。これはAPIエラーではない
- Phase 2側でも、以前は2レコードに分かれていた「白Tとデニム」が1レコードに統合されて`manual_review`に現れることを確認済み
