# 勝ち投稿判定の統一設計（2026-09-01）

## 背景

前回の調査（GOV-20260901-INVESTIGATION-01）で、「勝ち投稿」の定義がGate B `quality_band`（投稿前・下書きが先生投稿並みかの予測、[scripts/external_audit_schema.py](../../scripts/external_audit_schema.py)）とtopic_performance_band（投稿後・post_analyticsからの書き込み専用フィールド、[scripts/topic_group_state.py](../../scripts/topic_group_state.py)）の2系統に分裂しており、どちらも下流の意思決定（retry_budget消費・cooldown期間・候補フィルタ）へ接続されていないことが判明した。本タスクでは、実測に基づく「勝ち/引き分け/負け/判定不能」の単一の正本判定を新設し、topic_groupのライフサイクル管理へ配線する。

## フェーズ1: アフィリエイト計測経路の調査結果

**結論: Amazonアフィリエイトのクリック・コンバージョン計測経路は、このリポジトリのどのコードパスにも実装されていない。使える実データはエンゲージメント系のみ。**

- PA-API連携・トラッキングリンク/短縮URL生成・Amazon Associatesレポート取込スクリプト: いずれも存在しない（`.py`ファイル全体をgrepしても該当箇所なし）。
- `.env.example`: Google Sheets（サービスアカウント）とX API v2（Bearer Token / User Access Token）の認証情報項目のみ。Amazon関連の項目は一つもない。
- `docs/policies/amazon-affiliate-policy.md`: 表現・開示・価格変動注意等の**コンプライアンス**ルールのみで、クリック・コンバージョンの計測方針についての記載はない。
- `scripts/x_post_analytics.py`が取得するpost_analyticsのフィールドは`public_metrics`/`non_public_metrics`/`organic_metrics`/`promoted_metrics`のみで、すべてX API v2 `tweets/{id}`エンドポイント（`tweet.fields=public_metrics,non_public_metrics,organic_metrics,promoted_metrics`）由来。アフィリエイト成果にrelateする項目はゼロ。
- 旧`schemas/metrics_snapshot.schema.json`（`ops/logs/metrics_snapshots.csv`用）には`link_clicks`/`conversions`/`revenue`/`epc`フィールドが**定義自体はされている**が、対応するCSVは実データ1行（2026-08-02のt0スナップショット、全項目0）のみで、CLAUDE.md実行ルール8により2026-08-07付けで凍結済み（正本はGoogle Sheets経由の`ops-state` MCP）。
- 現行の正本（`scripts/ops_state_mcp/server.py`の`record_metrics_snapshot()`）が受け付けるフィールドは`impression_count`/`like_count`/`reply_count`/`bookmark_count`/`user_profile_clicks`/`url_link_clicks`/`engagements`のみで、**`conversions`/`revenue`/`epc`の受け皿すら存在しない**。`url_link_clicks`はXが計測する「リンクが押された回数」であり、Amazon側での購入確定（コンバージョン）を意味しない。

## フェーズ2: 実施内容

### 新設: `scripts/post_outcome.py`

`classify_post_outcome(public_metrics, fetch_status=None, affiliate_metrics=None) -> PostOutcomeResult`。`outcome`は`"win"`/`"neutral"`/`"loss"`/`"insufficient_data"`の4値。

判定ロジック（すべての閾値は暫定値、下記「閾値一覧」参照）:
1. `affiliate_metrics`に`conversions`が正の値で渡された場合は最優先で`"win"`（フェーズ1の結論により現状どの呼び出し元からも渡されない配線待ちの受け皿）
2. `public_metrics`が無い、または`fetch_status="failed_non_blocking"`なら`"insufficient_data"`
3. `impression_count`が`MIN_SAMPLE_IMPRESSIONS_THRESHOLD`未満なら`"insufficient_data"`（極小サンプルを`"loss"`と誤判定しない）
4. エンゲージメント合計（like+reply+retweet+quote+bookmark）が0件なら`"loss"`（インプレッション数に関わらず）
5. `impression_count >= WIN_IMPRESSION_THRESHOLD`なら`"win"`、それ以外は`"neutral"`

Gate B `quality_band`（`TEACHER_FLOOR`/`SHIP_THRESHOLD`/`STRONG_SHIP_THRESHOLD`）とtopic_performance_bandは、それぞれ「投稿前予測」「投稿後実測の要約」役割のまま無変更。`classify_post_outcome()`が「勝ち投稿かどうか」を問われた場合の唯一の正本であることをdocstringとCLAUDE.mdに明記した。

### `scripts/topic_group_state.py`への配線

- `TopicGroupState`に`has_ever_won: bool`（一度Trueになったら以後戻らない累積フラグ）と`latest_post_outcome: str | None`を追加（既存フィールドは無変更、追加のみ）。
- 新設`record_post_outcome(state, outcome)`: `latest_post_outcome`を更新し、`outcome=="win"`なら`has_ever_won=True`にする。
- `record_mainline_attempt()`: `has_ever_won=False`の場合、通常の1消費に代えて`NEVER_WON_RETRY_BUDGET_PENALTY_MULTIPLIER`倍を消費するよう変更。
- `record_publication()`: `latest_outcome`引数（デフォルトNone、既存呼び出し互換）を追加。`"loss"`なら即`topic_status="retired"`・cooldown設定なし、`"win"`ならcooldown期間を`WIN_COOLDOWN_DIVISOR`で短縮、それ以外（None含む）は既存どおり。
- `passes_mainline_candidate_filter()`: 第6条件として「win実績が一度もなく、かつ`mainline_run_count`が`NEVER_WON_MAX_RUN_COUNT_WITHOUT_WIN`を超えている」場合に除外するロジックを追加（戻り値に`never_won_exhausted_ok`キーを追加）。

### `scripts/post_generation_pipeline.py`への配線

- `record_topic_group_outcome_and_save()`: `record_topic_group_run_observed()`をこの呼び出し（＝1回のmainline run）ごとに呼ぶよう変更（前タスクではbackfillからのみ計上、ライブ経路は未配線だった項目に今回対応）。`record_publication()`へ`latest_outcome=state.latest_post_outcome`を渡すよう変更。
- `update_topic_performance_from_post_analytics()`: 引数を`impression_count: int | None`から`public_metrics: dict | None`（+`fetch_status`/`affiliate_metrics`）へ変更し、`classify_post_outcome()`→`record_post_outcome()`を内部で呼ぶよう拡張。この関数はこれまでコードベース内に呼び出し元が無かったため（GOV-20260901-INVESTIGATION-01調査で確認済み）、後方互換シムは設けていない。

### `scripts/backfill_topic_group_state.py`への配線

- `record_publication()`呼び出しに`latest_outcome=state.latest_post_outcome`を追加。
- post_analytics反映ブロックに`classify_post_outcome()`→`record_post_outcome()`を追加。

## 閾値・暫定値の一覧（人間の確認が必要な項目）

| 定数 | 値 | 根拠 | 変更方法 |
|---|---|---|---|
| `MIN_SAMPLE_IMPRESSIONS_THRESHOLD`（post_outcome.py） | 50 | `PERFORMANCE_BAND_THRESHOLDS["low"]`を流用。impression=10のような極小サンプルを"loss"と誤判定しないための最小サンプルライン | この定数のみ変更すればよい |
| `WIN_IMPRESSION_THRESHOLD`（post_outcome.py） | 200 | `PERFORMANCE_BAND_THRESHOLDS["medium"]`を流用（新規の数値は設定していない） | 同上 |
| `ZERO_ENGAGEMENT_FORCES_LOSS`（post_outcome.py） | True | 実測データ（impression=10、エンゲージメント全項目0）を踏まえた安全側の追加ルール。元のPERFORMANCE_BAND_THRESHOLDS設計には無かった新設ルールのため要確認 | 定数をFalseにすれば無効化できる |
| `NEVER_WON_RETRY_BUDGET_PENALTY_MULTIPLIER`（topic_group_state.py） | 2 | win実績が無いテーマの retry_budget消費を通常の2倍にする設計判断。倍率の妥当性は未検証 | この定数のみ変更すればよい |
| `WIN_COOLDOWN_DIVISOR`（topic_group_state.py） | 3 | win時のcooldownを21日→7日に短縮。除数の妥当性は未検証 | 同上 |
| `NEVER_WON_MAX_RUN_COUNT_WITHOUT_WIN`（topic_group_state.py） | 4 | 実データ（ATH-PRO5MK2系列、theme_signature分裂によりtopic_group_idが2つ、mainline_run_count=5/2、win実績ゼロ）のうち露出の多い側（5）を確実に検出できる水準として設定。per-topic_group単体の値であり、分裂した系列の合算値（5+2=7）は見ていない——合算判定が必要かは人間の判断が必要 | 同上 |

## 検証結果

1. `classify_post_outcome()`単体テスト: `scripts/test_post_outcome.py`検証1、win/neutral/loss/insufficient_dataの4パターン＋境界値（min_sample境界、win_threshold境界、affiliate override優先、affiliate=0では優先しない）11ケース全PASS。
2. 実データ（impression_count=10、エンゲージメント全項目0）: **`insufficient_data`に分類された**（`MIN_SAMPLE_IMPRESSIONS_THRESHOLD=50`未満のため）。`loss`ではなく`insufficient_data`となるのは設計どおり（極小サンプルを弱い実績と誤判定しないため）。
3. retry_budget/cooldown/候補フィルタへの配線の統合テスト: `scripts/test_post_outcome.py`検証3a〜3d、win実績なしのペナルティ消費・win/lossによるcooldown可変・境界値を含む候補フィルタ除外・実データ（ATH-PRO5MK2系列）での除外再現、全PASS。
4. 既存の`test_topic_group_lifecycle.py`（24件）・`test_weekly_learning_review.py`（35件）は全PASS（回帰なし）。
