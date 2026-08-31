# 投稿済みテーマのmainline恒久除外（posted-theme exclusion）— 2026-08-30

構造化データ: [posted_theme_exclusion_design_2026-08-30.json](posted_theme_exclusion_design_2026-08-30.json)
初期registry: [posted_theme_registry_2026-08-30.json](posted_theme_registry_2026-08-30.json)
関連: [learning_mode_async_enrichment_design_2026-08-28.md](learning_mode_async_enrichment_design_2026-08-28.md)（minimal_run_log/enrichment_record/weekly reviewの3層構造）

## 背景・欠陥

`ATH-PRO5MK2 × ジム用骨伝導 × 用途別使い分け`テーマは`mainline-run-2026-08-29-001`（案H）としてすでに実投稿済み（`post_url=https://x.com/ritsu_opt/status/2093850848397033676?s=20`）だった。にもかかわらず、`mainline-run-2026-08-29-002`〜`007`で同一または近縁のテーマが`source_post_id`違いで複数回mainline再生成された（gadget teacher supplyが同一RT投稿を繰り返し拾ってきたため）。**欠陥の本体はscorer（Gate A/structure/hook）ではなく、posted-theme exclusion / topic dedupeの仕組みそのものが存在しなかったこと**である。本文書はこれを恒久対策として実装する。

## 設計方針

- **`source_post_id`の完全一致だけでは不十分。** 同じテーマを別のsource_post_id（RTの再取得、表現違いの類似投稿）から拾ってくるケースを止められない
- **AIの重い意味判定には依存しない。** まずはルールベースのキーワード抽出＋正規化キー（`theme_signature`）＋既存ログ活用で止める。false positiveをある程度許容しても、実投稿済みテーマの再流入防止を優先する
- **blockしても研究価値は失わない。** blockされた候補は`route_to_research=True`として研究側（research/shadow/replay）へ回せる。「既投稿テーマをもう一度見たい」は禁止しないが、mainlineではなくresearchへ回すのが原則

## posted theme registry

過去に実投稿された（`published_at`/`post_url`/`published_draft_id`がすべて揃っている）mainline runから構築する軽量インデックス。1件のスキーマ:

`run_id` / `published_at` / `post_url` / `published_draft_id` / `source_post_id` / `target_layer` / `theme_signature` / `theme_key_terms` / `topic_group` / `exclusion_scope` / `cooldown_active` / `notes`

**`source_post_id`ではなく`theme_signature`を主キーとして持つ**ことが核心。

## theme_signatureの生成方式

ルールベースのキーワード抽出。draft本文＋source本文（可能な限り両方）から、5次元それぞれでキーワード辞書に一致するタグを抽出し、`__`で連結する。

| 次元 | 例 |
|---|---|
| product（製品/ブランド/型番） | `ath-pro5mk2` / `bone-conduction` / `neckband` |
| use_case（主用途） | `gym` / `home` / `meeting` / `commute` |
| comparison_axis（比較軸） | `lightness` / `sound-quality` / `call-quality` / `fit` / `split-use` |
| contrast（対立構造） | `two-device-split` / `bone-vs-sealed` / `priority-reversal` |
| conclusion（結論タイプ） | `split-settled` / `one-device-narrowed` |

例（実際に生成された値）: `ath-pro5mk2-bone-conduction-neckband__gym__call-quality__bone-vs-sealed__split-settled`

`topic_group`はcooldown判定用のより粗いグルーピングキー（product + comparison_axisのみで構成）。

**重要な較正結果**: candidate側の判定テキストにdraft本文だけを渡した場合（source本文を含めない）、実際には同一テーマであってもoverlap_ratioが閾値をわずかに下回ることがある（実測: 0.58、閾値0.6）。これはsource本文側にのみ現れるキーワード（例: 「マイク付き」）が拾えないため。**candidate判定は必ずdraft本文＋source本文の両方を`candidate_texts`へ渡すこと**を運用ルールとして明記する（source本文を含めた実測ではoverlap_ratio=0.92まで上昇し、正しくblockされた）。

## 判定レベル（3段階）と運用ルール

| match_type | 判定条件 | mainline |
|---|---|---|
| `exact_source_match` | `source_post_id`が過去の実投稿済みrunと完全一致 | **block** |
| `high_theme_similarity` | theme構成要素のoverlap_ratio ≥ 0.6（閾値）、または同一topic_groupかつoverlap_ratio ≥ 0.3 | **block** |
| `related_but_not_blocking` | overlap_ratio ≥ 0.3だがblock基準未満 | 継続可能、warningとして記録 |
| `none` | 一致なし | 継続可能 |

block時は`route_to_research=True`。破棄ではなく研究側へ回せることを保証する。

## hard guard / soft guard

- **hard guard**: `exact_source_match` / `high_theme_similarity` → mainline即block（自動停止）
- **soft guard**: `related_but_not_blocking` → 自動停止はしない。レポートに残し、必要ならhumanに「既投稿テーマ近縁」と見せられる

## cooldownルール

同一`topic_group`は、実投稿後`TOPIC_GROUP_COOLDOWN_DAYS`（初期値: **21日**、conservative設定、コード上で定数化）以内はcooldown対象として記録する。cooldownはtheme blockの補助情報であり、block判定の主体は`theme_signature`照合（上記3段階）である——`cooldown_active=True`単独ではmainlineをblockしない設計とした（block基準を`theme_signature`一本に絞ることで判定ロジックを単純に保つため）。

## 実装ファイル

- `scripts/topic_dedupe.py`（新規）: `extract_theme_components()` / `build_theme_signature()` / `build_topic_group()` / `theme_component_overlap_ratio()` / `build_theme_profile()`。外部AI呼び出しなし
- `scripts/posted_theme_registry.py`（新規）: `PostedThemeEntry`、`build_posted_theme_entry_from_minimal_run_log()`、`backfill_posted_theme_registry_from_reports_dir()`、`check_posted_theme_guard()`（判定本体）、registry保存/読込
- `scripts/minimal_run_log.py`（更新）: `MinimalRunLog`へ`posted_theme_check_status`/`posted_theme_match_type`/`matched_past_run_id`/`matched_post_url`/`matched_theme_signature`/`block_mainline`/`route_to_research`/`cooldown_active`/`posted_theme_check_reason`の9項目を追加（すべてOptional、既定None＝未チェック）。`build_minimal_run_log()`は`posted_theme_check`引数（dict、省略可）を受け取り、渡された場合はそのままログへ格納する。**mainline_statusの判定ロジック自体は変更していない**——posted-theme guardの結果はログに記録されるだけで、mainline_statusを直接書き換えることはしない（block時にhuman selectionへ進めるかどうかの運用判断は呼び出し側の責務として残す）
- `scripts/post_generation_pipeline.py`（更新）: `run_posted_theme_guard_check()`（既定のregistryファイルを読み込んで`check_posted_theme_guard()`を呼ぶ薄いラッパー）を追加。`finalize_minimal_run_log()`に`posted_theme_check`引数を追加し、`build_minimal_run_log()`へそのまま渡す
- `scripts/external_audit_client.py`は無変更（新規の外部AI呼び出しは不要なため）

## 初期registry（backfill結果）

`ops/reports/minimal_run_log_*.json`を全走査し、`published_at`/`post_url`/`published_draft_id`がすべて揃っているrunのみから構築した。現時点で該当するのは**`mainline-run-2026-08-29-001`の1件のみ**（他のmainline run(002〜007)はいずれも未投稿のため対象外——正しくスキップされている）。

```
run_id: mainline-run-2026-08-29-001
theme_signature: ath-pro5mk2-bone-conduction-neckband__gym__call-quality__bone-vs-sealed__split-settled
topic_group: ath-pro5mk2-bone-conduction-neckband__call-quality-lightness-split-use
post_url: https://x.com/ritsu_opt/status/2093850848397033676?s=20
```

## 検証結果

| # | 検証項目 | 結果 |
|---|---|---|
| 1 | 実投稿済みテーマ（ATH-PRO5MK2×ジム用骨伝導×用途別使い分け）の近縁言い換え候補（別source_post_id、draft+source本文込み）がblockされるか | **PASS**（`high_theme_similarity`、overlap_ratio=0.92、`block_mainline=true`） |
| 2 | 同一`source_post_id`の再利用がblockされるか | **PASS**（`exact_source_match`） |
| 3 | 非投稿の新規テーマ（fashion）がmainlineを通過するか | **PASS**（`none`、`block_mainline=false`） |
| 4 | 非投稿の新規gadgetテーマ（AirPods Pro×会議×マイク）がmainlineを通過するか | **PASS**（`none`） |
| 5 | `finalize_minimal_run_log()`に`posted_theme_check`を渡しても`mainline_status`判定が変わらないか | **PASS**（`block_mainline=true`でも`mainline_status=completed`のまま、guard結果は併記されるのみ） |
| 6 | 既存の`minimal_run_log`/`enrichment_record`/週次集計ファイルが壊れず読み込めるか | **PASS**（既存10 runsのファイルは無変更のまま。新フィールドはOptionalなので後方互換） |

## 運用への組み込み方（次のmainline runから）

1. source候補選定後、draftを生成する前後いずれかのタイミングで`run_posted_theme_guard_check(candidate_source_post_id, [draft_text, source_full_text], target_layer)`を呼ぶ
2. `block_mainline=True`ならその候補はmainlineでの人間提示から外し、`route_to_research=True`としてresearch/shadow/replay側の材料として扱う（研究したい場合は別途明示的に着手する）
3. `block_mainline=False`（`related_but_not_blocking`または`none`）ならmainlineを通常どおり継続。`related_but_not_blocking`の場合は`posted_theme_check_reason`をwarningとして記録に残す
4. 該当runが実際に投稿された場合、`ops/reports/posted_theme_registry_2026-08-30.json`へその新しいtheme entryを追記する（現時点では手動/スクリプト実行によるbackfill運用。自動追記の実装は次のfollow-up）

## 固定資産・変更範囲

Gate A・thresholds（65/75/80）・shipping decision・Phase 1 query set・production `_QUALITY_SCORE_SYSTEM_PROMPT`・`teacher_reference_score`・既存structure Gate B・hook_v1/v2・divergence meta-gateのscoringロジックは一切変更していない。`external_audit_client.py`・`MockExternalAuditClient`は無変更。既存10 completed runsの`minimal_run_log`/`enrichment_record`/週次集計ファイルは無変更（読み取りのみ）。research-only扱いのroutingを追加しただけで、production shipping decisionには未接続。自動投稿は行っていない。

## 既知の限界・次のfollow-up

- キーワード辞書はgadget layer（特に今回発覚したイヤホン/ヘッドホン系テーマ）を中心に整備した最小セット。fashion/intersection layerや他のgadgetサブテーマは辞書の拡充が必要
- registryへの新規entry追加は現時点で手動実行（`backfill_posted_theme_registry_from_reports_dir()`の再実行、または個別`build_posted_theme_entry_from_minimal_run_log()`呼び出し）。投稿確定時に自動追記する仕組みは次のfollow-up
- `related_but_not_blocking`のsoft guard情報を、実際の人間レビュー画面へどう見せるかの具体的な導線は未実装（設計原則のみ明記）
- cooldownの21日という初期値は仮の保守的設定であり、実運用データが蓄積されたら見直す

## commit / push

未実施。
