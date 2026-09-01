# Phase 1広域収集クエリへの全面置き換え・初回実収集結果（2026-09-01）

## 背景

[ops/reports/broad_teacher_collection_design_2026-09-01.md](broad_teacher_collection_design_2026-09-01.md)フェーズ2で提示された、商品カテゴリを人間が先読みしないジャンルレベルの6クエリ案を、人間の明示的な承認により「Phase 1 query setは変えない」制約を今回に限り解除して実装した。`scripts/x_api_phase1_collect.py`の`QUERIES`定数を旧18クエリ（イヤホン/骨伝導語を中心とした対象語決め打ち）から、以下の年代語×ジャンル語のOR集約6クエリへ全面置き換えた。

| # | 想定layer | クエリ |
|---|---|---|
| Q1 | gadget | `(40代 OR アラフォー) (ガジェット OR デバイス OR EDC OR 携帯性)` |
| Q2 | gadget | `(40代 OR アラフォー) (愛用 OR 手放せない OR 買ってよかった OR 使い分け)` |
| Q3 | gadget | `(40代 OR アラフォー) (充電 OR バッテリー OR ケーブル OR 持ち歩き)` |
| Q4 | fashion | `(40代 OR アラフォー) (小物 OR コーデ OR 身につける OR 着映え)` |
| Q5 | fashion | `(40代 OR アラフォー) (バッグ OR 財布 OR 時計 OR ベルト OR メガネ)` |
| Q6 | intersection | `(ガジェット OR デバイス) (服 OR コーデ OR ファッション)` |

Phase 2 classify（`_classify()`／単一の`_apply_engagement_gate()`ゲート、commit `ac5012c`）自体は無変更。

## 実収集結果

- 実行日時: 2026-09-01T09:53:26Z
- API呼び出し: **6回（6クエリ、6/6成功、失敗0）**。設計文書フェーズ2で見積もった6回どおりで、旧18回から67%削減。
- 各クエリの取得件数: Q1=13, Q2=20, Q3=16, Q4=20, Q5=20, Q6=20（`max_results=20`ずつ）
- 重複除去前合計: 109件
- id基準dedup後: 107件（2件除去）
- 本文ハッシュ基準dedup後: **89件**（18件除去、最大重複グループ14件）
- 保存先: `outputs/x_api_phase1/`（`merged_deduped.json`等）

## 分類結果

Phase 2 classify（無変更ロジック）を89件に適用:

| 分類 | 件数 |
|---|---|
| reject | 44 |
| observe | 21 |
| manual_review | 24 |
| **pre_teacher_candidate** | **0** |

engagement_tier分布: `insufficient_data`=46, `low`=20, `qualifying`=23

## topic driftの発生有無

**qualifying（エンゲージメント基準を満たす）23件を全件確認したが、pre_teacher_candidateへ昇格した投稿は0件だった。** 一方、23件のうち以下のような明確なtopic drift（ジャンルと無関係だが高インプレッション/高エンゲージメント）投稿が実際に収集されていることを確認した:

- `post_id=2094379745777684618`（impression=285,476、URLのみ）: `content_too_thin`＋`genre_fit_low`でreject
- `post_id=2094563561855168854`（美容ルーティンの箇条書き、impression=6,874）: `genre_fit_low`でreject
- `post_id=2092309405996073311`（投資・資産形成についての長文、impression=120,440）: `topic_fit=medium`のため`manual_review`（`good_format_but_boundary_fit`）、昇格せず
- `post_id=2093629425120067642`（外国人犯罪をめぐる社会時評）: `genre_fit_low`でreject
- `post_id=2094387263652180109`（TikTok集客ノウハウの宣伝的投稿、topic_fit=high）: `bait_signal_strong`でreject（topic_fitが高くてもbait検出が優先）

**これらのtopic drift候補がpre_teacher_candidateへ昇格しなかった理由は、単一ゲート（engagement_tier）だけでなく、既存の`approach_value`判定（`decision_hits`/`usefulness`/`aesthetic`×`utility`等の複合条件）が同時に働いたため。** 実際、`topic_fit=="high"`まで到達した投稿が5件あった（`post_id`: 2094595036457697364／2094659621382410641／2094602879575425180／2094546773842760031／2094464775380201678）が、いずれも`approach_value=="low"`だったため`strong_genre_signal_but_low_metrics`理由で`observe`止まりとなり、単一ゲート以前の段階で候補化されなかった。**単一ゲートが「最後の砦」として機能する場面は、少なくとも今回の89件では発生しなかった**（topic_fit=="high"かつapproach_value>=mediumかつengagement_tier!="qualifying"という組み合わせは0件）。

## 検証結果

1. 新クエリでの実収集テスト: 6/6クエリ成功、API呼び出し回数は設計見積もり（6回）どおり。エラー0件。
2. 新収集データへの`_classify()`適用結果: 上記のとおり（reject 44/observe 21/manual_review 24/pre_teacher_candidate 0）。
3. topic drift発生確認: qualifying 23件中、明確なtopic drift投稿は複数存在したが、`approach_value`判定と単一ゲートの両方が正常に機能し、**pre_teacher_candidateへの誤昇格は0件**だった。
4. 既存回帰テスト（`test_topic_group_lifecycle`/`test_weekly_learning_review`/`test_post_outcome`/`test_x_api_phase2_engagement`）: 全PASS。
5. Phase 1関連テストへの影響: `test_x_api_phase2_engagement.py`の`test_real_ath_pro5mk2_post_excluded()`が、クエリ全面置き換えにより当該post_id（イヤホン/骨伝導クエリでのみ収集されていたもの）を恒久的に取得できなくなったため、従来の「見つからない場合はfailure扱い」ロジックを「skip扱い」へ修正した（該当ケースはsynthetic再現テストで恒久的に代替確認済みのため実害なし）。

## 結論・所見

- 広域収集クエリへの全面置き換えは、API呼び出し予算内（6回、67%削減）で実行でき、収集内容の多様性は実際に拡大した（美容機器・SNS運用ノウハウ・社会時評・小説投稿など、旧18クエリでは収集されなかった話題が混入するようになった）。
- 単一ゲート（`_apply_engagement_gate`）は今回のノイズ環境下でも設計どおり機能したが、**今回の89件では「単一ゲートが実際に誤昇格を防いだ」ケースは発生しなかった**（そこに到達する前に`approach_value`判定で止まっていたため）。単一ゲートの実効性そのものは、前回タスクの回帰テスト（社会風刺投稿の実例）で既に確認済みであり、今回の結果はそれと矛盾しない。
- **pre_teacher_candidateが0件**という結果は、安全性の観点では問題ない（誤昇格が無い）が、収集の歩留まり（teacher候補が実際に見つかるか）という別の観点では、今回の1回の収集だけでは判断材料が不十分。継続的な収集・観察が必要。
