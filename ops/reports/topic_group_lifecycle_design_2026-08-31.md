# topic_group によるテーマライフサイクル状態管理（2026-08-31）

## 背景・目的

mainline候補選定で観測された3症状は、根本原因を辿ると「テーマにライフサイクル状態がない」という単一の共通原因に帰着する。

1. **posted-theme再流入**: 同一/近縁テーマが`source_post_id`違いで繰り返しmainlineへ現れる（実例: ATH-PRO5MK2×ジム用骨伝導、`mainline-run-2026-08-29-001`で実投稿済みにもかかわらず後続runで再候補化）。
2. **不発テーマの延命**: Gate A不合格やclosed_incompleteを繰り返すテーマが際限なく再試行され続ける。
3. **フィードバック不接続**: 実投稿後の実績値（`post_analytics`）が次の候補選定に一切反映されない。

既存の`posted_theme_registry`（[posted_theme_exclusion_design_2026-08-30.md](posted_theme_exclusion_design_2026-08-30.md)）は症状1の直接的な検出・block機構としてすでに機能している。本設計はこれを置き換えず、その上にテーマ単位の**状態ストア**（`topic_group_state`）を additive に重ねることで、症状2・3にも同じ枠組みで対処する。

## スコープ外（触っていない領域）

Gate A採点/閾値本体、shipping decision判定条件、Phase 1クエリ生成、structure/hook/divergence scorerアルゴリズム、research/shadow/replayのnon-blocking性質——いずれも本タスクでは一切変更していない（`git diff`で確認済み、詳細は本文書末尾の検証結果節を参照）。

## コンポーネント構成

### 1. theme_signature 正規化（`scripts/topic_dedupe.py`）

既存の`extract_theme_components()`/`build_theme_signature()`/`build_topic_group()`/`theme_component_overlap_ratio()`/`build_theme_profile()`のAPIはそのまま維持し、表記ゆれ吸収のために内部の正規化処理のみを強化した。

- `_normalize_for_matching(s)`: NFKC正規化 → 小文字化 → ハイフン/空白/アンダースコア/中黒の除去。
- キーワード辞書（`PRODUCT_TERMS`等）に英語/カタカナ/送り仮名バリエーションを追加。
- `extract_theme_components()`は、比較対象テキストとキーワードの両方を`_normalize_for_matching()`経由してから部分一致判定する。

これにより、既存の`posted_theme_registry.check_posted_theme_guard()`（`theme_component_overlap_ratio()`を内部で使用）は、コード変更なしに表記ゆれへ強くなる。

### 2. topic_group状態ストア（`scripts/topic_group_state.py`、新規）

`TopicGroupState`データクラス（12フィールド）:

```
topic_group_id, theme_signature, topic_status, topic_last_published_at,
topic_performance_band, topic_retry_budget, topic_cooldown_until,
topic_retired_from_mainline, route_to_research_only, source_diversity_tag,
created_at, updated_at
```

主要関数: `get_or_create_topic_group()` / `record_mainline_attempt(succeeded)` / `record_publication()` / `update_performance_band()` / `is_cooldown_active()` / `passes_mainline_candidate_filter()`。

`TOPIC_GROUP_COOLDOWN_DAYS`は`posted_theme_registry`から再利用（重複定義していない）。

### 3. mainline候補生成フィルタ（`scripts/post_generation_pipeline.py`の`evaluate_topic_group_for_mainline()`）

**出典タスクの原文との整合について**: 依頼文はこのフィルタを「4条件」と呼びつつ、実際には独立した5つの条件節を列挙していた（`topic_status=active` / posted-theme exclusion / `retry_budget>0` / cooldown外 / exploration quota内）。数え違いを黙って解消せず、列挙された5条件すべてをそのまま実装し、この食い違いをここに明記する。

`evaluate_topic_group_for_mainline()`は`posted_theme_registry.check_posted_theme_guard()`（一次判定、既存のexact/high-similarity block）と`passes_mainline_candidate_filter()`（二次判定、5条件のbookkeeping）の両方を呼び出し、結果を統合して返す。既存の`finalize_minimal_run_log()`は変更していない。

### 4. minimal_run_log書き込みとの同時更新（`record_topic_group_outcome_and_save()`）

`record_mainline_attempt()` + 必要に応じて`record_publication()`を実行しストアを保存する。`finalize_minimal_run_log()`本体は変更せず、呼び出し側（運用フロー）が並行して呼ぶ設計とした。

### 5. post_analyticsからのフィードバック（`update_topic_performance_from_post_analytics()`）

`post_analytics`の`public_metrics.impression_count`から`topic_performance_band`を更新するバッチ関数。`impression_count`が`None`（取得失敗）の場合は`"unknown"`のままとし、誤って`0`扱い・`"low"`扱いにしない。

## backfill（`scripts/backfill_topic_group_state.py`、新規）

既存の`minimal_run_log_*.json`全件を**読み取り専用**で走査し、`mainline_status=="completed"`のrunからtopic_group_stateを初期構築する。`minimal_run_log`は設計上draft/source本文を保持しないため、本文は呼び出し側が別途用意する（`posted_theme_registry.backfill_posted_theme_registry_from_reports_dir()`と同じ制約）。mainline本体のコードパスから独立しており、CLIから明示実行したときのみ動く。

**実行結果**: 既知7 mainline runsすべてを処理（`skipped_run_ids=[]`）。結果は2つの`topic_group_id`に分かれた（詳細は検証結果節）。

## 検証結果・既知の限界

詳細は本タスクの最終報告（チャット）を参照。要点のみ記す。

- theme_signature正規化: 5パターン（語順/送り仮名/型番大小文字/カタカナ英語/記号有無）すべてoverlap>=0.9でPASS。
- posted-theme exclusion統合: ATH-PRO5MK2×ジム用骨伝導の実再流入ケースを再現しblock確認、非投稿テーマの誤block無しも確認。
- 候補フィルタ5条件: 全条件OK時に通過、各条件を独立にFalseにした5ケースすべてで正しくblockすることを確認。
- Gate A/thresholds/shipping decision: `git diff`で該当4関数定義への差分なし、`external_audit_schema.py`は差分ゼロを確認。
- backfillの非破壊性: 既存16ソースオブトゥルースファイルのSHA-256ハッシュが実行前後で完全一致。
- **既知の限界**: backfillの結果、本来1つのはずのテーマ（ATH-PRO5MK2×ジム用骨伝導）が`topic_group`として2つのIDに分裂した。`build_topic_group()`のタグセットベースのグルーピングが、一部draftの言い回しで"使い分け"（split-use）比較軸タグを検出できないことが原因。ただし実際のmainline block判定は`posted_theme_registry.check_posted_theme_guard()`の直接overlap比較（topic_group文字列の一致ではない）が権威を持つため、この分裂は安全性を損なわない——`mainline-run-2026-08-31-008`の実ケース再現で、この分裂が存在してもblockが正しく機能することを確認済み。今後のfollow-upとして、topic_group生成のタグ検出をより頑健にするか、theme_signatureとの二重比較を正式化するかの判断が必要。
