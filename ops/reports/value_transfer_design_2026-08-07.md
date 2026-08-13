# value_transfer_design_2026-08-07.md — 価値転写不全（Value Transfer Failure）対策

> **2026-08-08改訂: Phase B（正式運用化）。** 価値カード方式を、投稿OSの通常運用における正式なオブジェクト・標準フローとして位置づける。**これは「価値カード方式による成果改善が実証された」ことを意味しない。** 実投稿の`profile_visits`実測が依然として不足しており、成果面の優劣は未証明のままである。Phase Bは「試験要素→正式運用単位への昇格」であり、「成果責任化」ではない。schema新設・Google Sheets構造追加・value card専用保存先・`measured_winner`昇格ロジックの実装は引き続き対象外（12節「Phase Bの非目的」参照）。judgment layerの既存の強さ判定基準（axis_scores、cta_fit_assessment、weak but safeの排除、Cold-start mode）は変更しない。
>
> 1〜8節はPhase A時点の記録（欠陥定義・方式・スキーマ試作・初期訂正・切り分けルール・試作カード・当初の使い方案・当初の未着手一覧）としてそのまま残す。9節以降がPhase Bでの追加・正式化内容。

## 1. 欠陥定義（正式反映）

現行システムの中核欠陥は「勝ち投稿を参照できないこと」ではなく、**勝ち投稿から価値を抽出し、その核を保持したまま別の場面・別の題材に再表現するという中核変換ができていないこと**である。

execution layerは勝ち投稿のテキストから表層属性（テーマ／場面／道具／CTA文言の型）を読み取り、1つを差し替える**テキストレベルの模倣**を行っている。一方でreview layerは生成された新テキストを単独で（絶対評価・相対評価いずれにせよ）採点する。この2つの間に**「なぜ元の投稿が効いたか」を保持する明示的な中間表現が存在しない**ため、新候補が弱かったとき「価値の核が新しい場面に合わなかったのか」「単に実行が拙かったのか」を区別できない。

## 2. 価値カード方式

「本文模倣」から「価値構造模倣」へ移行する。生成前に、ベンチマーク投稿から**価値カード**（価値の核を構造化した中間表現）を抽出し、新稿はそのインスタンス化として作る。不変要素（価値の核）を固定し、可変要素（表層）だけを動かす。reviewは新稿単独の強弱に加え、**価値カードとの忠実度（transfer_fidelity）**を照合する。

## 3. 価値カードの構造（試作スキーマ）

```
value_card_id:           vc-{元投稿post_id}
source_post_id:          抽出元の投稿ID
evidence_basis:          "review_approved" | "measured_winner"（4節参照）
confidence:              high / medium / low

# 不変要素（5項目。メカニズムとして記述する。固有名詞を含めない）
stopping_reason:         一文目で止まる理由
self_relevance_trigger:  自分事化する場面のカテゴリ（具体的場所は書かない）
emotional_trigger:       触っている感情と、その起動方法（出来事として提示するか、感情語で説明するか）
promised_utility:        読後に約束している効用
cta_bridge_reason:       プロフィール遷移が自然な理由

# 可変要素（表層。動かしてよい）
variable_slots:          [具体物, 場所, 語り口, 文長 等]
```

**保存先（Phase A時点）**: 専用シート・専用schemaは新設しない。`reviews`シート（`ops-state` MCP、`record_review_result`ツール）の`rationale`/`notes`に構造化テキストとして記録する。既存の自由記述欄に収まる設計のまま試験運用する。

## 4. `evidence_basis`の前提（2026-08-07訂正）

**訂正前の誤り**: 「実投稿・実測データがまだ一度もない」という前提は誤りだった。

**正しい前提**:
- Day1（`p-20260803-001`）・Day2（`p-20260804-002`）・Day3（`p-20260805-001`、後日`human_rejected_meaning_unclear`で不採用確定）は、いずれも実投稿・24h観測が存在する
- ただし、`profile_visit`CTAの主指標である`profile_visits`（プロフィール訪問数）自体は、Day1・Day2ともスクショで視認できておらず未取得のまま（Day1: impression 8のみ視認、Day2: impression 3のみ視認）
- したがって「measured_winnerと呼べる十分な証拠」はまだ存在しない。主指標（`profile_visit_rate`）が一件も取得できていないため

この訂正を踏まえ、**当面の`evidence_basis`は`review_approved`を基本とする**。`measured_winner`への昇格は、将来`profile_visits`を含む主指標データが十分に取得されてから判断する（`ops-state`の`count_same_condition_samples`が示すサンプル数を材料にする。Cold-start mode/Relative benchmark modeと同じ規律）。

## 5. 不変要素／可変要素の切り分けルール

判定テスト: **「この要素を別のものに差し替えたとき、読者の機能的体験（止まり方・自分事化のカテゴリ・感情トリガーの種類・約束される効用・プロフィールへ行く理由）が変わるか」**

- 変わらない → 可変要素（具体物、場所、語り口の硬軟、文長）
- 変わる → 不変要素（他者の視線・反応が実際に入るかどうか、感情が出来事として提示されているか感情語で説明されているか、オチを明かさずに終わるかどうか、等）

テーマ／ターゲット／フォーマット／CTA種類は、価値カードのレイヤーではなく朝会が固定するパイプライン定数であり、不変要素・可変要素いずれにも属さない（混同しない）。

**2026-08-08追加（通常サイクル運用での発見。high-risk可変要素）**: `variable_slots`のうち**語り口（tone/voice）**は、名目上は表層の可変要素だが、実際には`emotional_trigger`（緊張感・恥の真剣さ）を弱化させやすいことが通常サイクルで確認された（自嘲的ユーモアへ変更した結果、`stopping_reason`/`emotional_trigger`が3reviewer一致で「弱化」、`value_card_fidelity`も食い違いを検出した実例）。**語り口を変える場合は、変更前に`emotional_trigger`への影響を個別に確認すること。** 「可変要素だから自由に動かしてよい」という前提を無条件に適用しない。

## 6. 価値カード試作1枚（`p-20260807-002`＝案D）

```
value_card_id:           vc-p-20260807-002
source_post_id:          p-20260807-002
evidence_basis:          review_approved（4節参照。measured_winnerではない）
confidence:              medium（1事例のみからの抽出。次回サイクルでの再現可否が検証材料になる）

stopping_reason:         「頼まれごとに応じた直後、自分の持ち物の乱雑さが相手の目の前に
                          さらされる」という、他者との直接的な相互行為の瞬間を一文目に置く

self_relevance_trigger:  職場で誰かに何かを頼まれ、とっさに応じる中で自分の持ち物の状態を
                          意識させられる場面（「取引先のオフィス」「充電器」という固有名詞は
                          カテゴリに含めない）

emotional_trigger:       恥・気まずさ。相手が実際にケーブルの絡まりを見る/待つ、という
                          出来事として提示する。感情語(「気まずかった」)は出来事の後に
                          一言だけ添える程度に留め、出来事そのもので伝える設計

promised_utility:        同じ気まずさを繰り返さないための、見た目まで整った持ち物選びの基準

cta_bridge_reason:       何に「切り替えた」のかを本文で明かさずに終えるため、具体的な
                          中身への興味がプロフィールへの遷移理由として自然に生まれる

variable_slots:          [具体的な物品(ケーブル/ペンケース等), 頼まれごとの種類,
                          場所(オフィス/別の対人場面), 語り口の硬軟, 文の長さ]
```

元本文（参考、`ops/logs/post_log.jsonl`の`p-20260807-002`行）: 「取引先のオフィスで充電器を貸してほしいと言われ、鞄から出したケーブルが絡まっているのを、相手の前でほどく羽目になった。悪気なく渡しただけなのに、その数秒だけ気まずかった。見た目まで整えた持ち物に切り替えたのは、それからだ。切り替えた持ち物、プロフィールにまとめています。」

## 7. 次回サイクルでの使い方

1. 朝会（growth-strategist）が、Morning Strategy Briefの新設フィールド（「使用する価値カードID」「固定する不変要素」「試す可変要素」）に`vc-p-20260807-002`とその不変要素・変える可変要素を明示する
2. x-copywriterが本文生成前に「価値保持宣言」（使うベンチマーク／抽出した価値カード／保持する不変要素／変える可変要素／毀損しないと考える理由）を出す
3. 市場グラウンデッドレビュー3reviewerが、既存のaxis_scores/cta_fit_assessmentに加え`transfer_fidelity`（5項目×保持/弱化/毀損）を判定する
4. pre-post-self-checkが、宣言した不変要素との照合観点で確認する
5. 結果は`record_review_result`の`rationale`/`notes`に記録する（新規schema/シートは使わない）

## 8. 未着手として残したもの（Phase A時点）

- schema新設・Google Sheets構造追加（`value_cards`専用シート等）
- `measured_winner`昇格ロジックの実装（`profile_visits`データが十分に蓄積してから）
- 価値カード方式の効果測定そのもの（次回1サイクルを実際に回してから判断）
- axis_scoresとtransfer_fidelityの概念的重複の整理（実運用で実害が出てから検討）
- judgment layerの大規模再設計、投稿文そのものの改善ロジック追加

---

# Phase B（2026-08-08、正式運用化）

## 9. `evidence_basis`の正式ルール

- **`measured_winner`**: 実測で十分な根拠がある場合のみ使う。「十分」の基準は、`docs/strategy/kpi-definition.md`の「CTA別『強い投稿』判定ルール」のCold-start mode/Relative benchmark mode切り替え閾値（同条件群の有効サンプル5件）と整合させる。具体的には、当該カード由来の投稿について`profile_visit_rate`の実測値が最低1件以上取得され、かつ同条件群内で「明確に強い」（Cold-start mode）または上位25〜30%（Relative benchmark mode）と判定された場合にのみ昇格を検討する。**この判断ロジック自体の実装はPhase B対象外**（Phase Bの非目的、12節）。今回は基準の明文化のみ行う
- **`review_approved`**: Cold-start mode下のデフォルト利用を許可する。ただし常に「フラグ付き」で扱う——`evidence_basis: review_approved`であることを、価値カード自体・morning brief・reviews記録のいずれでも省略せず明記し、`measured_winner`と混同しない
  - **サブルール（2026-08-08追加）**: `review_approved`のうち、実文面ではなくangle情報等からの再構成であるもの（例: `vc-p-20260803-001`。実投稿の本文記録が手元に残っておらず、angleからの再構成だった実例）は、`confidence: low`を必須とし、`notes`に「実文面からの抽出ではなく再構成」である旨を明記する。新しい`evidence_basis`区分は追加しない（2区分のまま）

## 10. 標準フロー見取り図

```
朝会（morning-strategy-council）
  growth-strategist: 使用する価値カードID／source_post_id／evidence_basis／
                      固定する不変要素／試す可変要素（原則1つ）を明示
        ↓（x-copywriterにのみ引き継ぐ。reviewerには渡さない。2026-08-06の
           自己追認バイアス防止ルールを価値カードにも同様に適用する）
x-copywriter
  価値保持宣言（ベンチマーク／価値カード／保持する不変要素／変える可変要素／
                毀損しないと考える理由）→ 本文生成
        ↓
market-grounded review layer（3reviewer）
  axis_scores・cta_fit_assessment（従来通り）
  + transfer_fidelity（5項目×保持/弱化/毀損。1項目でも毀損があればkeep不可）
        ↓
pre-post-self-check
  value_card_fidelity（宣言と本文の整合確認。9観点の1つとして）
        ↓
affiliate-compliance-reviewer（従来通り、判定基準は不可侵）
        ↓
logger（`record_review_result`のrationale/notesに記録。専用シートなし）
        ↓
人間最終承認（文章が壊れている場合のみ却下。“もっと刺さる”を理由にした
              人手最適化はしない）
```

## 11. reviewの役割拡張（正式反映）

market-grounded review layer（3reviewer）の役割を、「投稿案が強いか弱いか」の単純判定に加えて、**「価値転写が成立しているか／不成立か／劣化しているか」を切り分けて検知すること**を正式な責務として位置づける。これにより:

- **転写不成立**（`transfer_fidelity`に毀損あり）と、**元カードの弱さ**（`transfer_fidelity`は全保持だが`axis_scores`が弱い。実例: `vc-p-20260803-001`検証サイクル、13節参照）を区別できる
- 「弱い」という一言で終わらせず、原因が転写の失敗にあるのか、そもそも参照した価値カードのメカニズムが競合比で強くないのかを、reviewerが構造的に説明できる状態にする
- reviewerの独立性（それぞれ個別に判定し、討論しない）と、外部根拠取得の必須化（WebSearch/WebFetch）は維持したまま拡張する。役割の「拡張」であり「変更」ではない

## 12. Phase Bの非目的（明記）

以下は今回の正式運用化の範囲に含まれない:

1. 「価値カード方式で成果改善が実証済み」という結論
2. `measured_winner`昇格ロジックの本格導入
3. `profile_visit`実測不足のままのwinner certification
4. Google Sheetsの大規模schema変更
5. value card専用DB・専用永続ストアの新設
6. `transfer_fidelity`の定量スコアリング制度化
7. Phase C相当のperformance-analyst/weekly-pdca-review統合
8. 人手で「もっと刺さる文」へ編集する運用への回帰
9. judgment layerの思想変更
10. 実投稿成果の改善を今回のマージ条件にすること

## 13. 実施した検証サイクル（実績記録）

| サイクル | value_card_id | 動かした可変要素 | transfer_fidelity | 新ゲート（hook_visibility/target_clarity/cta_bridge_clarity） | axis_scores | action |
|---|---|---|---|---|---|---|
| 1回目（Phase A） | `vc-p-20260807-002` | 具体的な物品（ケーブル→ペン） | 全5項目保持 | 未導入時 | 差別化のみ同等、他は強い | keep |
| 2回目（Phase A） | `vc-p-20260807-002` | 場所（オフィス→新幹線車内） | 全5項目保持 | 未導入時 | 差別化含め強い | keep |
| 3回目（Phase A） | `vc-p-20260803-001`（静かな違和感型、angle再構成） | 具体的な持ち物（未特定→スマホケース） | 全5項目保持 | 未導入時 | 差別化・緊張感が弱い、強い軸なし | revise |
| 4回目（Phase B・通常運用） | `vc-p-20260807-002` | 語り口（静か→自嘲的ユーモア） | `stopping_reason`/`emotional_trigger`が弱化、他3項目保持 | 未導入時 | 未評価（transfer_fidelityの弱化により`revise`確定） | revise |
| 5回目（戦略可視化ゲート導入後） | `vc-p-20260807-002` | 文の長さ（背景説明を先頭に追加） | 全5項目保持 | `hook_visibility`弱い／`target_clarity`やや曖昧（一文目に停止理由が来ず） | 未評価（新ゲートで`revise`確定） | revise |
| 6回目（5回目の修正版・プロジェクター確認版・hook修正版） | `vc-p-20260807-002` | 文の長さ（背景説明を事件の後ろへ移動、フックを一文目に配置） | 全5項目保持 | `hook_visibility`強い／`target_clarity`明確／`cta_bridge_clarity`自然 | 強い | **keep** |

6サイクルを通じて確認できたこと: (1)同一カードの継続利用でも機構は安定動作した、(2)異なるメカニズムのカードでも機構は機能した、(3)**「転写の忠実さ」と「元カードのメカニズムの強さ」は独立した軸として切り分けて検出できた**（3回目）、(4)**「語り口（tone/voice）」は表層可変要素に見えて実は`emotional_trigger`を弱化させるhigh-risk要素であることが判明した**（4回目。5節に運用ルールとして反映済み）、(5)**戦略可視化ゲート（`hook_visibility`等）が、`transfer_fidelity`全保持でも「価値カード整合性はあるがフックが見えない案」を実際に止めた**（5回目）、(6)**同じゲート基準で、フック位置を修正した再生成が`keep`に戻ることを確認した**（6回目）。これはchat上の検証であり、実ファイルへの記録・実投稿は行っていない。

**候補管理の整理（2026-08-09、レーン分離）**: 「既投稿の観測タスク」と「未投稿候補の優先順位」を混同しないため、以下の2レーンに分離する。

### レーンA: 観測レーン（投稿済み・観測補完対象。投稿候補ではない）

- **cycle2（新幹線版、`p-20260809-001`）**: 状態＝投稿済み。役割＝観測補完対象／実測サンプル。現在の主タスク＝24h観測欠損・主指標（`profile_visit`）欠損の整理と補完。**未投稿候補の順位表からは除外する**

### レーンB: 未投稿候補レーン（これから投稿できる候補のみ）

1. **第一候補: 6回目（プロジェクター確認版・hook修正版）**。新しい戦略可視化ゲートを通過した最初の`keep`案。`hook_visibility`強い／`target_clarity`明確／`cta_bridge_clarity`自然／`transfer_fidelity`・`value_card_fidelity`とも全保持
2. **第二候補（比較・バックアップ）: cycle1（ペン版）**。破棄はしない
3. **除外継続: 4回目（語り口変更版）・5回目（背景説明先頭版）**。いずれも`revise`判定のまま投稿候補一覧に含めない

- **`evidence_basis`は全候補とも引き続き`review_approved`。`measured_winner`扱い・winner認定はしていない。** これは既投稿サンプルの観測タスクと未投稿候補の優先順位を分離するための運用整理であり、成果改善の実証ではない
- **段階**: 未投稿候補（第一候補＝6回目）確定済み。実投稿・投稿URL記入は人間の操作待ち。post_id発行・正式ログ記録（`ops-state` MCP経由）は、MCP接続確認後に行う（`ops/logs/post_log.jsonl`は凍結済みのため直接追記しない）
- 以後、ユーザーへの候補提示は「観測中の既投稿サンプル（レーンA）」と「次に出す未投稿候補（レーンB）」を分けて提示する

## 14. 未解決課題（Phase B移行後も残るもの）

- **独立性の課題**: 3サイクルとも同一実行コンテキスト（私）による評価であり、過去の機能監査で指摘した自己採点構造は未解決のまま
- **`measured_winner`昇格の実運用ロジック**: 9節で基準は明文化したが、実装・自動判定はPhase C以降の課題
- **`axis_scores`と`transfer_fidelity`の概念的重複**: 実運用で頻発するようなら整理を検討（Phase B時点では未整理のまま）
- **`vc-p-20260803-001`のような再構成カードの品質保証**: `confidence: low`＋`notes`明記で運用するが、根本的な保証策ではない
- **`evidence_basis: measured_winner`への到達条件（`profile_visits`実測）自体がまだ一度も満たされていない**: Phase Bはこの状態を前提に正式運用化しており、状況が変わればここに立ち返る必要がある

---

# 戦略可視化ゲート（2026-08-09追加）

## 15. 問題認識

直近の差戻し案では、`transfer_fidelity`と`value_card_fidelity`は通っていた一方で、運用責任者が「この投稿のフックは何か」「どのターゲットのどの層に刺すのか」「どの恥・不快・違和感を止める文なのか」を説明できない状態が生じた。これは価値カード方式そのものの失敗ではなく、**「価値カードの整合性（転写の忠実度）」と「価値の可視性（読者から見えているか）」が別軸であるにもかかわらず、後者を検証する仕組みが本文生成前・生成後のいずれにも存在しなかったことによる実行モードの不一致**である。

## 16. 3-mode構成

| Mode | 実行者 | 内容 |
|---|---|---|
| **朝会（接続補強）** | growth-strategist所見＋audience-representative所見 → council-chairが合成 | `who_and_pain_summary`（誰の・どの痛みを狙うかの一次案）をBriefに明記する |
| **Mode 1: 戦略可視化** | x-copywriter | Briefの`who_and_pain_summary`を起点に、想定フック／想定ターゲット／刺したい感情／自分事化トリガー／プロフィール遷移理由／一文要約の6項目を具体化する。**本文は書かない** |
| **Mode 2: 生成** | x-copywriter | Mode 1通過後、value retention declaration→本文生成（既存のまま） |
| **Mode 3: 検証** | 3reviewer／self-check | 既存の`transfer_fidelity`/`value_card_fidelity`に加え、`hook_visibility`/`target_clarity`/`cta_bridge_clarity`を判定する |

## 17. 差戻し基準（value card整合性が保たれていても差戻しになるケース）

以下のいずれかに該当する場合、`transfer_fidelity`が全保持でも`keep`にしない:

1. フックが説明できない（`hook_visibility`が弱い/不明）
2. ターゲットがぼやけている（`target_clarity`がやや曖昧/不明）
3. 状況説明はあるが止まる理由が見えない
4. CTAに進む理由が弱い（`cta_bridge_clarity`が弱い/不成立）
5. 「何に刺す文か」を一文で説明できない

## 18. 位置づけの確認

この修正は、**value card方式をやめるためではなく、価値が読者に見える形で前景化されるよう、本文生成前・生成後の戦略可視化ゲートを追加するための修正である。** 価値カード方式・tone/voiceのhigh-risk運用・measured_winnerとreview_approvedの区別・人手による"もっと刺さる文"編集の禁止は、いずれも変更していない。
