# X投稿運用システム mainline 再設計

---

## 1. システム全体の欠陥診断

### 1.1 本質的欠陥（一言で）

> **mainline が「勝つ確率が高いテーマを選ぶ系」ではなく「Gate A を通過しやすい候補を生成する系」として最適化されていた。**

Gate A・人間選択・minimal_run_log 保存という「通過儀礼」は正常に回っている。しかし、その通過儀礼の先にあるべき問い——「このテーマは伸びるのか」「新規性があるのか」「まだ擦る価値が残っているのか」——が、次の run の**起動条件**にフィードバックされていない。結果として、mainline は「通せる候補を出す」ことに最適化された局所ループになっており、これは事実上、目的関数の取り違えである。

### 1.2 局所問題 vs 全体系問題の切り分け

| 症状 | 分類 | 理由 |
|---|---|---|
| 投稿済みテーマの再流入（例: ATH-PRO5MK2 × ジム用骨伝導） | **局所問題** | posted-theme exclusion guard という単一機構の欠如で説明できる |
| 不発テーマの延命 | **全体系問題** | 「テーマの実績」を状態として持たず、時間経過や実績低下で自動的に露出を絞る機構が存在しない |
| mainline / research の境界不明瞭 | **全体系問題** | 「本線を止めてよい条件」の定義が存在せず、研究都合の検証が本線のブロッカーになり得る設計になっている |
| フィードバック逆流不足 | **全体系問題** | ログは生成されているが、ログを read する「意思決定側」の入力仕様が存在しない。ログは記録止まりで、状態遷移のトリガーになっていない |

### 1.3 なぜ「既投稿テーマの再流入」だけでは不十分な説明か

再流入ガードを足せば症状 #2 は消える。しかし、それは**同じ根本原因が生む症状の一つを潰しただけ**である。根本原因は「テーマという単位に状態がない」こと。状態がないテーマは、
- 何回擦られたか分からない
- 実績が良かったか悪かったか分からない
- 最後にいつ出したか分からない
- 今後どう扱うべきか（再挑戦か、卒業か、research 送りか）判断できない

再流入は「状態がないことの一症状」に過ぎず、延命・偏り・学習不能もすべて同じ穴から出ている。ガードを一つ足しても、次の run で別の形（例: 微妙に言い換えた同一テーマ、実績最悪のテーマの居座り）で再発する。**テーマにライフサイクルを持たせること**が本質的な修正である。

---

## 2. 新しい mainline 設計原則

### 2.1 mainline の新しい目的関数

mainline が最適化すべきは **「Gate A 通過」ではなく、次の複合目的**である。

```
maximize:
    novelty_weighted_value(theme)
  + exploration_coverage_contribution(theme)
  - duplication_penalty(theme, recent_posted_themes)
  - human_review_cost(candidate_set)
subject to:
    Gate A / thresholds / shipping decision は不変
```

構成要素:
1. **新規性 (novelty)** — 直近 N 件・同一 theme_signature 系列に対する差分の大きさ
2. **投稿価値 (post value)** — 過去実績（もしあれば）または類似テーマの実績から推定される期待反応
3. **exploration coverage** — まだ十分に試されていない source / hook / structure の組み合わせをどれだけ埋めるか
4. **低品質重複の回避** — 同一 theme_signature の連続露出、または低実績テーマの居座りを罰する
5. **人間確認コストの最小化** — 候補セットの多様性・粒度を制御し、1本選びやすい状態を維持する
6. **実反応の学習可能性** — 「出しても学びにならない」候補（実績が読めない・比較対象がない）を下げる

**要点:** Gate A は「出してよいか」の門番であり続ける。新目的関数が答えるのは「そもそも Gate A に候補として送り込む価値があるか」という、Gate A の**手前**の問題である。ここが今回の再設計の中心。

### 2.2 設計原則（5か条）

1. **テーマは使い捨てではなく、状態を持つ実体である。** run 単位ではなく topic_group 単位で管理する。
2. **mainline は「意思決定」、research/shadow は「なぜ」を問う場。** 両者は非同期に接続され、research 側の検証は本線のブロッカーにならない。
3. **すべてのログは next-run の入力である。** 記録して終わりのログは存在してはならない。minimal_run_log / enrichment_record / weekly_learning_review / post_analytics はすべて topic_group の状態遷移に接続される。
4. **本線停止条件は「安全性・整合性」に限定する。** 研究上の疑問・再現性検証・スコアラー改善候補は停止条件にしない。
5. **今ある資産を壊さず、状態管理レイヤーを上乗せする。** Gate A・thresholds・shipping decision・Phase 1 query set は不可侵。

---

## 3. 必要な状態モデル / データモデル

### 3.1 中核概念: `topic_group`

`topic_group` は「同一テーマ意図」を束ねる単位。例えば `ATH-PRO5MK2 × ジム用骨伝導 × 用途別使い分け` は 1 topic_group であり、表現違いの複数 run がこの下にぶら下がる。

```yaml
topic_group:
  topic_group_id: string            # 安定ID（source × angle × use-case のハッシュ）
  theme_signature: string           # 正規化済みテーマ指紋（表記ゆれを吸収）
  topic_status: enum                # active | cooling_down | retired_from_mainline | research_only
  topic_last_published_at: datetime | null
  topic_performance_band: enum      # unknown | low | mid | high
  topic_retry_budget: integer       # 残り挑戦可能回数（mainlineでの再露出上限）
  topic_cooldown_until: datetime | null
  topic_retired_from_mainline: boolean
  route_to_research_only: boolean
  source_diversity_tag: string      # 使用 source の系統タグ（偏り検出用）
  created_at: datetime
  updated_at: datetime
```

### 3.2 `theme_signature` の役割

自由記述テーマ文字列の表記ゆれ（語順違い・同義語）を吸収し、同一意図のテーマを同一 topic_group に正しく畳み込むための正規化キー。posted-theme exclusion guard は本来この signature に対して効くべきものであり、文字列完全一致ではなく signature 一致で判定する。

### 3.3 状態遷移

```
[新規テーマ]
    │ 初出
    ▼
 active ──(投稿・実績観測)──► topic_performance_band 更新
    │                                   │
    │ 実績 low が続く / retry_budget消尽  │ 実績 high
    ▼                                   ▼
 cooling_down                     active（優先度上昇）
    │ cooldown期間経過
    ▼
 active（再挑戦） ──(それでも low)──► retired_from_mainline
                                          │
                                          ▼
                                  route_to_research_only = true
```

- **active**: mainline の候補生成対象
- **cooling_down**: 一時的に mainline 候補から除外（露出過多 or 直近低実績）。cooldown 明けで active に復帰
- **retired_from_mainline**: mainline には出さない。ただし完全消去はしない
- **research_only**: retired 後も「なぜ効かなかったか」を調べる価値がある場合、research/shadow の分析対象として残す

### 3.4 既存ログ資産との接続

| 既存ログ | 接続先 state | 更新内容 |
|---|---|---|
| `minimal_run_log` | topic_group.topic_last_published_at / topic_retry_budget | 投稿確定時に更新 |
| `enrichment_record`（structure/hook/divergence） | topic_group.source_diversity_tag, exploration coverage 計算 | run 完了時に集計 |
| `post_analytics`（impressions, like, reply, repost, bookmark） | topic_group.topic_performance_band | 実績が閾値到達時点で再評価 |
| `weekly_learning_review` | topic_group 全体のリバランス（quota配分・retire判定の週次バッチ） | 週次で cooldown/retire を一括反映 |

---

## 4. mainline 起動条件・停止条件・ルーティング設計

### 4.1 起動条件（候補生成に進んでよい条件）

候補セット生成の際、以下をすべて満たす topic_group のみを候補プールに入れる。

1. `topic_status == active`
2. `posted-theme exclusion`: 直近ウィンドウ内で同一 theme_signature が投稿されていない
3. `topic_retry_budget > 0`
4. `topic_cooldown_until` が未来でない（cooldownでない）
5. `theme_exploration_quota`: 特定 source/angle の系統に偏りすぎていない（source_diversity_tag の分布制約）

### 4.2 停止条件（本線を止めてよい条件 / いけない条件）

**本線停止条件にしてよいもの**（安全性・整合性に限定）:
- Gate A 通過候補がゼロ
- 候補生成元データの欠損・破損
- topic_group 状態ストアの整合性エラー（例: active なのに theme_signature 重複）

**本線停止条件にしてはいけないもの**:
- research/shadow の再現性検証待ち
- scorer 改善案の検討中
- weekly_learning_review の分析が終わっていない
- post_analytics の一部データ未着（non-blocking で扱う）

### 4.3 ルーティング設計

```
候補プール構築
    │
    ├─ active topic_group → mainline 候補生成 → Gate A → 人間選択 → 投稿
    │
    ├─ cooling_down / retired topic_group → research 送り（分析専用）
    │       └─ shadow/replay: 過去 run を再評価し、スコアラーの当たり外れを検証
    │           （本線には一切影響しない、non-blocking）
    │
    └─ 実績確定（post_analytics到達）
            │
            ▼
      topic_performance_band 更新
            │
            ▼
      次回起動条件（quota, cooldown, retry_budget）に反映
```

mainline に残すもの: 候補生成、Gate A、人間選択、投稿実行、状態更新（軽量・同期）
research に送るもの: 再現性検証、scorer 研究、深い分析、失敗要因分析（重量・非同期）
shadow/replay の位置づけ: 過去ログを使った「もしスコアラーがこう変わっていたら」の検証専用。recommendation-only を維持し、本線の意思決定を書き換えない。

---

## 5. 短期（今週）でやる改修

優先度順。すべて「今の実装群を壊さず上乗せする」方針。

1. **`theme_signature` 正規化関数の実装**（テーマ文字列 → 正規化キー）
2. **`topic_group` 状態ストアの新設**（既存DB/JSONストアに追加テーブル/ファイルとして。既存スキーマは変更しない）
3. **posted-theme exclusion guard を theme_signature ベースに置換**（文字列一致 → signature一致）
4. **mainline 候補生成の直前フィルタに 4.1 の起動条件を追加**
5. **minimal_run_log 書き込み時に topic_group.topic_last_published_at / topic_retry_budget を同時更新する backfill hook**

## 6. 中期（今月）でやる改修

1. **post_analytics → topic_performance_band 自動反映バッチ**（閾値: 例えば投稿後72時間の impression/engagement 実績で low/mid/high を判定。閾値の具体値は既存 Gate A の thresholds 思想に合わせて別途固定）
2. **cooldown / retire 判定の週次バッチ化**（weekly_learning_review 実行時に一括反映）
3. **theme_exploration_quota の source_diversity_tag ベース実装**（偏り検出とバランス制御）
4. **既存 posted-theme 履歴の backfill**（過去ログから theme_signature を逆算し、topic_group を初期構築）
5. **research_only ルーティングの実装**（retired topic_group を research/shadow の分析キューに接続）

---

## 7. ClaudeCode に渡す統合実行指示文

以下をそのまま ClaudeCode に一括投入する想定で作成。

```
# ClaudeCode 統合実行指示

## 目的
mainline の候補選定ロジックに「topic_group による状態管理」を追加し、
posted-theme再流入・不発テーマ延命・フィードバック不接続の3症状を
根本原因（テーマにライフサイクル状態がないこと）から解消する。
Gate A / thresholds / shipping decision / Phase 1 query set のロジックは
一切変更しない。

## 成功条件
1. theme_signature が正規化関数として実装され、既存の posted-theme
   exclusion guard がこの signature ベースで動作する。
2. topic_group 状態ストアが新設され、以下フィールドを持つ:
   topic_group_id, theme_signature, topic_status, topic_last_published_at,
   topic_performance_band, topic_retry_budget, topic_cooldown_until,
   topic_retired_from_mainline, route_to_research_only,
   source_diversity_tag, created_at, updated_at
3. mainline の候補生成直前フィルタが、topic_status=active かつ
   posted-theme exclusion かつ retry_budget>0 かつ cooldown外
   かつ exploration quota 内、の4条件を満たす topic_group のみを
   候補プールに通す。
4. minimal_run_log 書き込み時に topic_group の
   topic_last_published_at / topic_retry_budget が同時更新される。
5. post_analytics 到達時に topic_performance_band が自動更新される
   バッチ（または hook）が存在する。
6. 既存の Gate A / thresholds / shipping decision / Phase 1 query set
   の呼び出し箇所・ロジックに差分がない（diffで確認可能なこと）。
7. 既存の minimal_run_log / enrichment_record / weekly_learning_review /
   post_analytics のスキーマは破壊的変更をしない（追加は可、削除・改変は不可）。

## 実装対象ファイル
- [mainlineの候補生成モジュール（該当ファイルパスをリポジトリから特定して記載）]
- [posted-theme exclusion guard の実装ファイル]
- [minimal_run_log 書き込み処理のファイル]
- [post_analytics 取得・処理のファイル]
- 新設: topic_group 状態ストア定義ファイル
- 新設: theme_signature 正規化ロジックファイル

## 触ってはいけない領域
- Gate A のスコアリング・閾値判定ロジック本体
- shipping decision の判定条件
- Phase 1 query set の内容・生成方法
- scorer（構造/hook/divergence enrichment のスコアリング本体）のアルゴリズム
- research / shadow / replay の実行トリガー条件（non-blocking性を変えない）

## backfill 対象
- 過去の minimal_run_log 全件から theme_signature を逆算し、
  topic_group を初期構築する（既存データは読み取りのみ、書き換えない）
- 過去 post_analytics が存在するものは topic_performance_band に反映
- backfill はスクリプトとして分離し、mainline 本体のコードパスとは
  独立して実行可能にすること（誤って本線に混入させない）

## 検証項目
1. theme_signature 正規化関数の単体テスト（表記ゆれ吸収の確認、
   最低5パターン: 語順違い、送り仮名違い、型番大文字小文字、
   カタカナ/英語表記違い、記号有無）
2. posted-theme exclusion が signature ベースで機能することの
   統合テスト（既知の再流入ケース ATH-PRO5MK2 × ジム用骨伝導
   を再現し、除外されることを確認）
3. mainline 候補生成フィルタが4条件すべてを正しく適用することの
   テスト（各条件を単独でFalseにしたケースを含む）
4. Gate A / thresholds / shipping decision の出力が変更前後で
   一致することの回帰テスト（同一入力に対する既存テストスイートの
   全件PASSを確認）
5. backfill スクリプトが既存ログを破壊しないことの確認
   （backfill前後で既存ログファイルのハッシュ一致、または
   読み取り専用アクセスのみであることをコードレビューで確認）

## commit/push 方針
- 機能単位で複数commitに分割する
  （例: theme_signature実装 → topic_group状態ストア →
   候補生成フィルタ統合 → backfillスクリプト）
- 各commitは単体でビルド・既存テストが通る状態を維持する
- commit message は日本語または英語、変更理由を1行で明記
- 全commit完了後、最終テストスイート全PASSを確認してからpush
- push前に Gate A / thresholds / shipping decision関連ファイルに
  diffがないことを最終確認する

## 途中報告禁止
実装途中の逐次報告は不要。全実装・全検証が完了した時点で
一度だけ最終報告すること。

## 最終報告フォーマット
以下の形式で1回のみ報告する:

### 実施内容
- [ファイル単位の変更サマリ]

### 成功条件チェック結果
- [7項目それぞれについて Pass/Fail と根拠]

### 検証結果
- [5項目それぞれのテスト結果]

### commit一覧
- [commit hash と1行サマリのリスト]

### 未解決事項・要判断事項
- [人間の判断が必要な残課題があれば列挙。なければ「なし」]
```

---

## 8. 人間が最後に判断すべき最小項目

再設計・実装のほとんどは自動化・委譲可能だが、以下は人間の判断が必要（数値・閾値・ビジネス判断が絡むため）。

1. **`topic_performance_band` の閾値**（impression/engagement のどの水準を low/mid/high とするか）— Gate A の thresholds 思想との整合性確認が必要
2. **`topic_retry_budget` の初期値**（1テーマにつき何回まで mainline での再挑戦を許すか）
3. **`topic_cooldown` の期間**（何日休ませてから再挑戦させるか）
4. **`theme_exploration_quota` の配分方針**（source/angle の多様性をどこまで強制するか、既存の勝ちパターンをどこまで優先するか、のバランス）
5. **backfill の実行タイミング**（本番データに対していつ実行するか、実行前のバックアップ有無）
6. **最終的な commit/push の承認**（ClaudeCode の最終報告を見た上で、実際に本番反映するかどうかの最終ゴー判断）

以上が上位設計の全体像です。ClaudeCode への統合実行指示文（第7節）はそのままコピーして投入可能な形にしてあります。
