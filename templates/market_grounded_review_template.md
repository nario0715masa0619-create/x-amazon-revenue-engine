# market_grounded_review_template.md — market-grounded reviewテンプレート

> `trend-reality-reviewer` / `competitor-reality-reviewer` / `audience-market-fit-reviewer` が投稿案を評価する際の型。1レビュー = このテンプレート1件。
> **既存の`templates/review_template.md`（affiliate-compliance-reviewer用）とは別物であり、混同しない。** market-grounded reviewは「外部現実（トレンド・競合・市場）との照合」であり、compliance判断・最終承認は行わない。
>
> **2026-08-04改訂**: 集客モードでは「破綻していないか」ではなく「競合比で強いか・弱いか・同等か」を中核判定とする（[phase1 spec](../ops/reports/phase1_acquisition_launch_spec_2026-08-03.md)の「集客モードの評価思想」参照）。判定は絶対評価ではなく**相対評価**（競合比で強い／同等／弱い）。フック単体を先に評価し、フックが競合比で「弱い」場合は原則として`action: hold`とし、本文全体の評価に進まない。
>
> **2026-08-06改訂（機能監査に基づく修正）**: (1) `comparison_pattern.source_ref`は`WebSearch`/`WebFetch`を実際に実行した結果、またはユーザー提示の参考情報のみを記入する。未実行のまま推測で埋めることを禁止する（未実行の場合`action`は`hold`固定。各reviewer定義の「外部根拠の取得方針」参照）。(2) reviewerはmorning-strategy-councilが示した推奨方向・フック仮説を判定根拠に使わない（本文と外部根拠のみで判定する。詳細は各reviewer定義の禁止事項）。
>
> **2026-08-08改訂（Phase B: 価値カード方式の正式運用化）**: reviewの役割は「強い/弱いの単純判定」に加えて、**「価値転写が成立しているか／不成立か／劣化しているか」を切り分けて検知すること**を含む（詳細: [ops/reports/value_transfer_design_2026-08-07.md](../ops/reports/value_transfer_design_2026-08-07.md)の11節）。**これは成果改善の実証ではなく、判定の切り分け精度を上げる目的の役割拡張である。** 価値カードを使わない投稿案（新規探索日）では`transfer_fidelity`は不要。

---

## 対象post_id / candidate_label

（記入）

## reviewer_name

`trend-reality-reviewer` / `competitor-reality-reviewer` / `audience-market-fit-reviewer` のいずれか

## comparison_scope

`direct`（直接競合: 40代男性向けに服・持ち物・ガジェット・清潔感・身だしなみ・実用品を発信する近いアカウント） / `indirect`（間接競合: 整理術・通勤・デスク環境・EDC・ミニマル持ち物・仕事道具など、同じ読者の注意を奪うアカウント） / `benchmark`（準ベンチマーク: 同業ではないがX上で短文フックが強く止める力のあるアカウント）

## comparison_pattern

（比較対象に多い型の要約。以下を含める）

- `source_type`: `official_best_practice` / `trend_search` / `competitor_observation` / `user_provided_reference`
- `source_ref`: （参照した情報源。URL・検索クエリ・提示資料名など）
- 比較対象に多い型・傾向

## hook_assessment（一文目のみを切り出して評価。他の観点より先に行う）

`強い` / `同等` / `弱い`

## whole_post_assessment（`hook_assessment`が`弱い`でない場合のみ記入）

`強い` / `同等` / `弱い`

## axis_scores（5軸必須。`whole_post_assessment`を記入した案のみ）

各軸を`強い` / `同等` / `弱い`で評価する。**2026-08-06追加: 判定基準（操作的定義）**。抽象語のまま「なんとなく強い/弱い」と判定しない。以下の基準に照らして判定し、根拠を1行添える。

- **停止力**（一文目でタイムライン上で止まるか）
  - 強い: 一文目の主語・動作・状況が具体的で、続きを読まないと分からない未解決の情報がある。説明・前置きから始まっていない
  - 弱い: 一文目が一般論・前置き・説明（「〜という問題があります」等）から始まっている、または抽象的すぎて場面が想像できない
- **自分事化**（40代男性が「それ自分のことだ」と感じるか）
  - 強い: 一文目が特定の生活場面（仕事・通勤・対人関係等）の当事者視点で書かれ、40代男性の実体験として具体的に想像できる
  - 弱い: 男女共通・年齢不問の抽象論に落ちている、または場面が一般化されすぎて「誰の話でもある＝誰の話でもない」状態になっている
- **差別化**（よくある整理論・身だしなみ論・生活感論に埋もれないか）
  - 強い: 直接競合（服・持ち物・清潔感系）・間接競合（整理術・通勤・EDC・デスク環境系）の典型的な場面設定・切り口と重ならない
  - 弱い: 「満員電車」「デスクの散らかり」等、間接競合が頻用する定番の舞台設定・切り口をそのまま使っている
- **緊張感**（恥・損失・見栄・失敗回避・他人の視線のいずれかが立っているか）
  - 強い: 恥・損失・見栄・失敗回避・他者の視線のいずれかが、一文目の中で具体的な出来事・瞬間として示されている（抽象的な感情語のみでは不可。例:「気まずい」だけでは不可、「隣の視線が一瞬止まった」のように出来事として書かれていれば可）
  - 弱い: 緊張要素が本文中どこにも具体的な出来事として現れない、または内面的な気づきのみで外部からの反応・実害が一切ない
- **遷移力**（プロフィールを見に行く理由が自然に生まれるか）
  - 強い: 本文の終わり方に未解決の興味・続きを示唆する要素があり、CTA文言だけに遷移理由を頼っていない
  - 弱い: CTA文言（「プロフィールへ」等）だけが遷移理由で、本文内容自体には続きを見たくなる要素がない

## cta_fit_assessment（2026-08-06追加。`whole_post_assessment`を記入した案のみ）

「なんとなく強いか」ではなく、投稿案の`cta_type`（`docs/strategy/kpi-definition.md`の「CTA別『強い投稿』判定ルール」参照）に対応する主指標を実際に取りに行ける構造か、を判定する。

- 対象`cta_type`: `profile_visit` / `reply_prompt` / `link_click` / `save` / `reach`のいずれか
- 判定: `強い` / `同等` / `弱い`
  - 強い: この`cta_type`の主指標につながる導線（例: `profile_visit`なら「プロフィールを見たくなる未解決の興味」）が本文に具体的に存在し、既存のbenchmark candidate（あれば）より劣化していない
  - 弱い: CTA文言だけに導線を頼っている、または主指標につながる構造が本文にない
- `insufficient_evidence_note`: benchmark candidateが存在しない（Cold-start mode中）場合はその旨を明記する

## transfer_fidelity（2026-08-07追加、2026-08-08よりPhase B・正式運用。価値カードを使った案のみ）

投稿案が「勝ち投稿の価値カード」をどれだけ忠実に引き継いでいるかを判定する。`axis_scores`が**投稿単体の強さ**を測るのに対し、`transfer_fidelity`は**なぜその強さが生まれるはずだったメカニズムが実際に保持されているか**を、元の価値カード（[ops/reports/value_transfer_design_2026-08-07.md](../ops/reports/value_transfer_design_2026-08-07.md)参照）の5項目と1対1で照合して判定する。価値カードを使わない案（従来通りのフリー生成）では記入不要。

- `value_card_id`: 参照した価値カード（例: `vc-p-20260807-002`）
- 5項目それぞれについて`保持` / `弱化` / `毀損`のいずれかを判定する:
  - `stopping_reason`
  - `self_relevance_trigger`
  - `emotional_trigger`
  - `promised_utility`
  - `cta_bridge_reason`
  - 保持: メカニズムが変わらず引き継がれている
  - 弱化: メカニズムは残っているが効きが鈍っている（例: 出来事の提示が曖昧になった）
  - 毀損: メカニズム自体が別のものに置き換わった、または失われた
- 判定基準: **可変要素（具体物・場所・語り口等）が変わったこと自体は毀損ではない。** 不変要素（5項目のメカニズム）が変わっていれば毀損とする
- 1項目でも`毀損`があれば、`axis_scores`の結果によらず`action`は`revise`とする（「表層は変わったが強い（axis_scores）」と「価値カードが正しく転写された」は別軸であるため、両方を満たして初めて`keep`とする）

## action

`keep` / `revise` / `hold`

- `keep`は**競合比で同等以上**の場合のみ使う。「安全だが弱い（weak but safe）」案は`keep`にしない
- `hook_assessment`が「弱い」の場合、原則`action`は`revise`または`hold`とする
- **`cta_fit_assessment`が「弱い」の場合も`keep`にしない（`revise`または`hold`とする）。競合比の5軸が強くても、CTA typeの主指標につながる構造がなければ「強い投稿」ではない**（2026-08-06追加）
- **価値カードを使った案で、`transfer_fidelity`に`毀損`が1項目でもあれば`keep`にしない**（2026-08-07追加。詳細は上記`transfer_fidelity`節）
- `comparison_pattern`（外部根拠）が空の場合、`action`は`hold`のみとする
- 両案とも`revise`／`hold`相当なら、1回だけ修正して再判定する。修正後も弱ければ「best effortだが競合比では弱い」と`rationale`に明記する

## rationale

（判定理由。1〜2行）

## suggested_fix

（1行）

## confidence

`high` / `medium` / `low`

（`high`は複数ソースが一致した場合のみ。1件の観察例だけでの一般化は`high`にしない）

## insufficient_evidence_note

（データ不足の場合のみ記入。例: 「競合アカウント候補が不足」「直近比較サンプルが少ない」「トレンド確認の粒度が粗い」）
