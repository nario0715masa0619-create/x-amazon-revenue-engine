# PDCA 実験台帳（索引）

最終更新日: **2026-08-28**

このファイルは[pdca_experiment_registry.json](pdca_experiment_registry.json)（機械可読の単一台帳、1配列=複数実験レコード）の人間可読な索引。個別の失敗記録は[failed_experiment_registry_2026-08-25.md](failed_experiment_registry_2026-08-25.md)にも残っているが、以降はこのPDCA台帳を最優先の参照先として更新していく（`failed_experiment_registry`の内容はEXP-20260825-QS-COMPRESSION-01として本台帳へ統合済み、改ざんなし）。

**プロジェクト上位定義**: このリポジトリは単なるSNS投稿自動化ではなく「投稿運用OS」として再定義されている。レイヤー構造（L0〜L6）・固定資産・研究対象・運用/研究ブランチ分離の全体像は[project_redefinition_posting_os_2026-08-25.md](project_redefinition_posting_os_2026-08-25.md)を参照。**運用ブランチ（L0→L1→L2→L3→L6）と研究ブランチ（L2→L4→L5）の具体的な責務分離・KPI・promotion/rollback基準は[operations_research_split_plan_2026-08-25.md](operations_research_split_plan_2026-08-25.md)を参照。** 新規の修正・実験に着手する前に、これらの文書と本台帳の両方を確認すること。

## 概要

- 登録実験数: **34件**（+ governanceレコード6件、詳細は末尾「governance updates」参照）
- 判定内訳: `validated_improvement` 9 / `inconclusive_result` 13 / `measurement_bug` 2 / `partial_improvement` 8 / `failed_experiment` 2
- 再利用方針内訳（全40件対象）: `reusable` 13 / `reusable_with_conditions` 23 / `do_not_reuse` 2 / `do_not_reuse_blindly` 2
- follow-up待ち（`followup_required=true`）: **32件**（うち実質未着手は2件: EXP-20260821-TEACHER-REPRO-01、GOV-20260830-POSTED-THEME-EXCLUSION-01のregistry自動追記・辞書拡充待ち。GOV-20260827-LEARNING-MODE-MAINLINE-SHADOW-SPLIT-01は運用方針決定のためfollow-upは「この分割ルールの下で複数runが安定的に回ることの確認」という継続監視項目）
- 対象期間: 2026-08-21〜2026-08-28（先生原文の変換精度検証から、quality_score圧縮是正のarchitecture実験、プロジェクト再定義、運用/研究ブランチ分離計画、Phase D shadow mode Run 1〜12、R2-2 score mapping、first-line hook evaluator設計・実装・replay検証・forward validation試行×2、gadget query再設計（Round1〜3）、live forward validation（Run10・Run11・Run12、Step A非開示guard導入）、hook evaluator再設計（opening span evaluator/hook_v2、replayで仮説不支持・live未実施）、structure/hook divergence meta判定の設計・実装（replayで3パターン再現）、学習モードのL1/L2/L3再分割（governance）、Run14以降の研究方針明文化（governance）、投稿時最小ログ/非同期enrichment/週次研究集計の3層構造再設計（governance）まで）
- **independent_shadow_runs = 11**（Run1: mismatch/proxy、Run2: mismatch/proxy、Run3: match/proxy、Run4: mismatch/real（`human_initial_top`のみ取得、`closed_incomplete`）、Run5: mismatch/real（フルサイクル完了）、Run6: mismatch/real（フルサイクル完了、Run5の再現）、Run7: mismatch/real（hook_augmented_v1、フルサイクル完了、Run5/6の再現）、Run8: closed_incomplete（gadget教師投稿供給が枯渇し、Gate A以降に進めず）、Run9: closed_incomplete（供給回復確認を再試行するも未回復、Run8と合わせて通算4回連続で教師投稿0件）、Run10: first-line hook evaluator初のlive forward validation。structure/hook/human 3者が一致（分離は非再現）。Step A disclosure contaminationが発生し、initial側のmatch指標は無効化（final側のみ有効）、Run11: Step A非開示guard付きで再実施。structure≠hook、hook=human（initial/final両方）というRun5/6/7 replayパターンがlive runで再現し、Run10の3者一致とは異なる結果、**Run12: Run10/Run11と異なるsourceでStep A非開示guard付き再実施。今回はstructure=human（initial/final両方）、hook≠humanとなり、「hook=human」パターンが初めて崩れた**。gadget layerの教師投稿供給はRound3クエリ再設計以降回復し、Run10〜Run12とも実施できた。first-line hook evaluatorの人間判断予測力はreplay 3/3 + live 1/3（Run10=区別力なし、Run11=hook的中、Run12=structure的中）となり、単純な優位仮説は保留状態）

**運用原則**（このファイルで必ず守ること）:
- 「失敗」は否定的記録ではなく、再発防止と次実験の起点として扱う
- `validated_improvement`と`failed_experiment`は同列に並べず、必ず分類する
- 実験的なprompt/rubric変更は、before/after比較による検証があるまで本番ルールに昇格させない
- `measurement_bug`（実装の純粋な不具合）を、政策判断の失敗（`failed_experiment`）と混同しない
- 次の実験が未定義の`failed_experiment`を放置しない（本台帳では全件に`next_experiments`を必須化）

---

## 実験一覧（全30件）

| experiment_id | title | final_verdict | reuse_policy | operational_impact | root_cause_family | one_line_takeaway |
|---|---|---|---|---|---|---|
| EXP-20260821-TEACHER-REPRO-01 | 先生原文→再現の変換精度検証 | inconclusive_result | reusable_with_conditions | no_change | source_truncation | 変換失敗は実在した。Intersectionは原文欠損でblocked、捏造せず正しく停止 |
| EXP-20260821-FASHION-HEADLINE-01 | Fashion見出し断定型テンプレート等の修正 | validated_improvement | reusable | production_enabled | — | テンプレート骨格固定化で3つの故障点を構造的に解消 |
| EXP-20260821-EXCL-01 | own-post exclusion | validated_improvement | reusable | guardrail_added | — | 初回から現在まで一貫して有効な本番ガードレール |
| EXP-20260821-GADGET-TIER-01 | gadget_minimal/gadget_rich二層化 | validated_improvement | reusable | production_enabled | — | sparse source対応として有効。直後にage_angleバグが発覚 |
| EXP-20260821-GADGETAGE-01 | render_comparison() age_angle欠落バグ修正 | partial_improvement | reusable_with_conditions | guardrail_added | — | コードバグは完全解決。監査モデル制御はprompt修正だけでは限界 |
| EXP-20260821-FIXNORM-01 | required_fixes正規化中間層 | validated_improvement | reusable | guardrail_added | audit_model_overreach | 正規化層は成功。ただしsafe判定と監査passの別軸問題は未解決のまま残り、Gate A/B分離へ |
| EXP-20260823-SHIPTHRESH80-01 | 旧SHIP_THRESHOLD=80過剰ブロック | **measurement_bug** | do_not_reuse | needs_followup | threshold_misalignment, insufficient_sample | 未検証のまま運用されていた閾値。実測分布との突き合わせで発覚 |
| EXP-20260823-GATESPLIT-01 | Gate A / Gate B split | validated_improvement | reusable | production_enabled | — | 監査アーキテクチャの中核的な前進。後続タスク全ての前提 |
| EXP-20260823-THRESH-01 | two-threshold redesign | validated_improvement | reusable | production_enabled | — | teacher floor/ship thresholdの分離で、score=75の安全な案を初めて正しく扱えるように |
| EXP-20260825-TEACHERBUG-01 | teacher_reference_score誤rubric正規化 | **measurement_bug** | do_not_reuse | guardrail_added | score_normalization_bug, rubric_ambiguity | 実装漏れの純粋なバグ。政策判断の失敗ではない |
| EXP-20260824-SCORECONSIST-01 | Gate B score consistency normalization fix | validated_improvement | reusable | production_enabled | score_normalization_bug | score算出元を1点に統一。既存rerunバッチの重要な訂正を導いた |
| EXP-20260825-TEACHERDIST-RERUN-01 | teacher distribution再測定 | inconclusive_result | reusable_with_conditions | needs_followup | insufficient_sample | 上方シフトしたが原因が測定方法の変化のため閾値変更は保留 |
| EXP-20260825-SCALECHECK-01 | quality_score vs teacher_reference_scoreスケール比較 | inconclusive_result | reusable_with_conditions | needs_followup | rubric_ambiguity, score_compression | 中心差は小さいが共有軸圧縮という分解能問題を発見 |
| EXP-20260825-QS-COMPRESSION-01 | quality_score shared-axis compression fix | failed_experiment | do_not_reuse_blindly | caution_added | prompt_anchoring, rubric_ambiguity, single_draft_absolute_scoring, score_compression | numeric anchors + anti-compression prompt worsened dispersion; do not reuse as production improvement |
| EXP-20260825-QS-NEXT-01 | quality_score圧縮是正 次実験（アンカー除去版A / 軸境界シャープ化版B） | failed_experiment | do_not_reuse_blindly | caution_added | single_draft_absolute_scoring, score_compression | numeric-anchor removal and axis-boundary sharpening both worsened dispersion further; prompt/rubric-level fixes are exhausted, next step is multi-draft comparative evaluation architecture |
| EXP-20260825-QS-MULTIDRAFT-01 | Comparative Gate B v1（multi-draft比較評価）試験実装 | partial_improvement | reusable_with_conditions | needs_followup | single_draft_absolute_scoring, score_compression | comparative framing solved the differentiation problem that 2 prompt-only attempts could not, but the v1 rank-to-score conversion over-amplifies mild qualitative gaps into extreme scores; tier-weighted conversion is the next required step |
| EXP-20260825-QS-SHADOWMODE-RUN1-01 | Phase D shadow mode Run 1（comparative Gate B並走、real production batch） | inconclusive_result | reusable_with_conditions | needs_followup | score_compression | shadow mode execution works without disrupting the operational branch; the single run observed a real mismatch (fashion pair) revealing that single-draft and comparative Gate B encode different implicit quality values, but n=1 run is insufficient to generalize — Run 2+ required before Phase E |
| EXP-20260826-QS-SHADOWMODE-RUN2-01 | Phase D shadow mode Run 2（2本目のindependent run） | inconclusive_result | reusable_with_conditions | needs_followup | score_compression | 2 independent shadow-mode runs both completed without disrupting operations; gadget-layer direction was consistent across runs and mismatches were objectively explainable, but proxy human judgment and the unresolved tier-blind score conversion keep this at partially_ready, not ready for Phase E |
| EXP-20260826-QS-MAPPING-R2-2-01 | Comparative ranking to bounded normalized score mapping（R2-2） | validated_improvement | reusable_with_conditions | needs_followup | score_compression | replacing only the rank-to-score conversion layer preserved top-1 in 4/4 batches while cutting average score spread by ~90% (85.0 -> 8.5 points), validating that the over-amplification was a conversion-layer problem, not a judgment problem — though 3-tier rounding still under-differentiates larger vs smaller real gaps |
| EXP-20260826-QS-SHADOWMODE-RUN3-01 | Phase D shadow mode Run 3（tier_bounded_v1 live適用の初回検証） | partial_improvement | reusable_with_conditions | needs_followup | score_compression | tier_bounded_v1 mapping reproduced its offline gains in a live run for the gadget pair (gap 100->7, top-1 retained, first-ever match with the operational recommendation), while the fashion pair could not be tested due to real Gate A rejections — including a re-rejection of an already-validated safe pattern, surfacing Gate A non-determinism as a separate open issue |
| EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01 | Phase D shadow mode Run 4（gadget layer real human judgment取得、closed_incomplete） | inconclusive_result | reusable_with_conditions | needs_followup | missing_artifact, reporting_inconsistency, human_alignment_pending | Run 4 obtained the first real human_initial_top data point for the gadget layer (a mismatch with the comparative recommendation), but the human review flow was interrupted before disclosure and final judgment could be collected, so the run was honestly closed as incomplete rather than fabricating a final decision |
| EXP-20260826-QS-SHADOWMODE-RUN5-REALFINAL-01 | Phase D shadow mode Run 5（gadget layer real human final judgment、初のフルサイクル完了） | inconclusive_result | reusable_with_conditions | needs_followup | human_alignment_pending, evaluation_axis_gap_candidate | Run 5 completed the first full real human_judgment_mode=real cycle for the gadget layer without fabrication: the comparative recommendation did not change the human's final choice, but it measurably reduced their confidence in it, and the human's stated reasoning (opening-hook strength) pointed to a possible axis gap in comparative Gate B's evaluation criteria that requires n>=2 real runs to confirm |
| EXP-20260826-QS-SHADOWMODE-RUN6-REALHUMAN-01 | Phase D shadow mode Run 6（gadget layer real human full cycle、Run5 mismatchパターンの再現確認） | inconclusive_result | reusable_with_conditions | needs_followup | human_alignment_pending, evaluation_axis_gap_candidate, structure_fidelity_bias_candidate | Run 6 independently reproduced Run 5's exact mismatch pattern (comparative favors structure/fidelity, real human favors opening-hook strength; decision unchanged, confidence high->medium both times) — raising the evidence from n=1 anecdote to n=2 reproduction and motivating a follow-up experiment that augments comparative Gate B with hook-oriented axes |
| EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01 | Phase D shadow mode Run 7（hook_augmented_v1 comparative Gate B real-human verification） | inconclusive_result | reusable_with_conditions | needs_followup | structure_fidelity_bias, hook_axis_added_but_not_effective, human_stop_power_preference, comparative_human_alignment_gap | Adding hook-oriented axes did not change the model's top-1; the model still preferred the structurally faithful draft while the human still preferred the sharper opening-hook draft, so this was recorded as inconclusive_result (not failed_experiment) requiring a next design change |
| EXP-20260827-FLHOOK-01 | first-line hook evaluator（冒頭句専用の独立判定器）設計・実装・replay検証 | partial_improvement | reusable_with_conditions | needs_followup | first_line_hook_evaluator_candidate, opening_hook_vs_structure_split, human_stop_power_signal_extraction | The first-line hook evaluator reproduced the hypothesized split in a 3/3 replay of Run5/6/7's known drafts: comparative Gate B's structure-favored top stayed unchanged, while the hook evaluator's top matched the real human's initial and final choice in every case, though this is a replay of already-known cases and not yet independent new human validation |
| EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01 | Phase D shadow mode Run 8（first-line hook evaluator forward validation、closed_incomplete） | inconclusive_result | reusable_with_conditions | needs_followup | opening_hook_vs_structure_split, human_stop_power_signal_extraction, forward_validation_pending, teacher_supply_variability | Run 8 attempted the first forward validation of the first-line hook evaluator on genuinely new data, but two real X API collection attempts found zero viable gadget-layer teacher candidates (the source that had appeared in all 7 prior runs), so the run was honestly closed as incomplete rather than substituting a low-quality candidate or switching layers outside the run's stated scope |
| EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01 | Phase D shadow mode Run 9（gadget教師投稿供給回復確認・forward validation再試行、closed_incomplete） | inconclusive_result | reusable_with_conditions | needs_followup | opening_hook_vs_structure_split, human_stop_power_signal_extraction, forward_validation_pending, teacher_supply_variability | Run 9, run as an independent supply-recovery check (not a reopening of Run 8), confirmed that gadget-layer teacher supply had still not recovered after 2 more real collection attempts (4 total across Run 8 and Run 9), so it was honestly closed as incomplete under the same insufficient_gadget_teacher_candidates condition rather than substituting a lower-quality source or switching layers |
| EXP-20260827-GADGET-QUERY-REDESIGN-01 | Phase 1 gadget teacher collection queryの再設計と2ラウンドA/Bテスト | partial_improvement | reusable_with_conditions | needs_followup | teacher_supply_variability, query_design_over_constrained | The gadget query redesign confirmed that AND-combining '比較' with any other specific term collapses X API recent search results to zero, while axis-only queries (音漏れ/装着感) reliably surface gadget-relevant content that is qualitatively closer to teacher material than before, but none reached the teacher-candidate bar in this test batch, so Run 10 forward validation remains blocked pending a third query iteration |
| EXP-20260827-GADGET-QUERY-REDESIGN-ROUND3-01 | Phase 1 gadget query Round3（axis/scene語主軸）、初のgadget teacher候補確保に成功 | validated_improvement | reusable_with_conditions | needs_followup | teacher_supply_variability, query_design_over_constrained | Round 3 confirmed the hypothesis from Round 2: dropping '比較'/'実体験' as AND-required terms and using axis/scene words as the primary query strategy recovered a genuine gadget teacher candidate (post_id=2092424287672311915) for the first time since Run7, unblocking forward validation of the first-line hook evaluator, though 2 of the 4 pre_teacher_candidate hits were ad content manually excluded |
| 2026-08-27 | EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01 | shadow-run-2026-08-27-010 | live forward validation（Step A誤開示あり） | completed | partial_improvement | structure=B / hook=B / human final=B で3者一致、ただしStep A汚染のため initial系一致判定は無効 |
| 2026-08-27 | EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01 | shadow-run-2026-08-27-011 | guarded live forward validation（Step A非開示維持） | completed | partial_improvement | structure=D / hook=C2 / human initial=C2 / human final=C2、hook=human再現・structureはinitial/finalともmismatch |
| 2026-08-28 | EXP-20260828-QS-SHADOWMODE-RUN12-FLHOOK-LIVE-GUARDED-02 | shadow-run-2026-08-28-012 | guarded live forward validation（別source・primary使用） | completed | inconclusive_result | structure=E / hook=F2 / human initial=E / human final=E、hook=humanパターン崩れ・structureがinitial/finalともmatch |
| 2026-08-28 | EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01 | shadow-run-2026-08-28-013 | hook evaluator再設計 replay（opening span / hook_v2、live未実施） | completed | inconclusive_result | hook_v2はRun12改善なし・Run11で悪化、span拡張でstructure寄りとなり独立シグナル性が弱まる可能性 |
| 2026-08-28 | EXP-20260828-METAGATE-DIVERGENCE-01 | — | structure/hook divergence meta判定の設計・実装（勝敗判定ではなくreview priority signal） | replay_only | partial_improvement | Run10=divergence false/auto_candidate_ok、Run11・Run12=divergence true/mutual_disagreement/high/human_review_priority_high。期待した3パターンをすべて再現。的中方向はRun11=hook側、Run12=structure側と逆転したが「split自体が高価値」という判定は両方成立 |

---

## failed_experiments（2件）

### EXP-20260825-QS-COMPRESSION-01: quality_score shared-axis compression fix

- **final_verdict**: `failed_experiment`
- **reuse_policy**: `do_not_reuse_blindly`
- **operational_impact**: `caution_added`
- **root_cause_family**: `prompt_anchoring` / `rubric_ambiguity` / `single_draft_absolute_scoring` / `score_compression`
- **hypotheses_supported**: H1（promptが中庸点誘導）、H2（rubric共有軸定義の曖昧さ）、H4（軸スケール使用域の狭さ）
- **hypotheses_rejected**: H3（weight配分。単純合計のため1:1感度で反証済み）、H5（正規化処理。クリップ・丸めのみで反証済み）
- **one_line_takeaway**: numeric anchors + anti-compression prompt worsened dispersion; do not reuse as production improvement
- **next_experiments**: qualitative-anchor-free prompt variant / multi-draft comparative Gate B / mandatory draft_text retention in logs
- **evidence_reports**: [quality_score_compression_fix_2026-08-25.md](quality_score_compression_fix_2026-08-25.md) / [.json](quality_score_compression_fix_2026-08-25.json)

### EXP-20260825-QS-NEXT-01: quality_score圧縮是正 次実験（parent: EXP-20260825-QS-COMPRESSION-01）

- **final_verdict**: `failed_experiment`
- **reuse_policy**: `do_not_reuse_blindly`
- **operational_impact**: `caution_added`
- **root_cause_family**: `single_draft_absolute_scoring` / `score_compression`
- **試した内容**: variant A（数値アンカー完全除去・質的定義のみ）、variant B（軸境界シャープ化。数値アンカー・anti-compression指示とも無し）
- **結果**: variant A stdev=0.0（4件全て同一スコア、既存4件中もっとも圧縮）、variant B stdev=0.5。**どちらも親実験（failed_variant、stdev=1.0）より悪化**
- **hypotheses_supported**: H3（1draft独立評価の制約）、H4（multi-draft evaluationが必要）
- **hypotheses_rejected**: H1（数値アンカーが主因）、H2（軸重複が主因、単独では不十分）
- **one_line_takeaway**: numeric-anchor removal and axis-boundary sharpening both worsened dispersion further; prompt/rubric-level fixes are exhausted, next step is multi-draft comparative evaluation architecture
- **next_experiments**: multi-draft evaluation（同一候補群の並列比較採点、または absolute+relative hybrid scoring）の実装 / Gate B監査ログへのdraft_text必須保存
- **evidence_reports**: [quality_score_next_experiment_2026-08-25.md](quality_score_next_experiment_2026-08-25.md) / [.json](quality_score_next_experiment_2026-08-25.json)

---

## partial_improvements（8件、明確な前進はあるが完全解決ではない）

### EXP-20260821-GADGETAGE-01: render_comparison() age_angle欠落バグ修正

コードバグは完全解決したが、監査モデルの過剰要求はprompt修正だけでは制御しきれなかった。

### EXP-20260825-QS-MULTIDRAFT-01: Comparative Gate B v1（parent: EXP-20260825-QS-NEXT-01）

- **final_verdict**: `partial_improvement`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `single_draft_absolute_scoring` / `score_compression`
- **試した内容**: 同一candidate由来の複数draftを1回のGate B評価で横並び比較させ（絶対スコアは要求しない）、順位付け結果をコード側でBorda count正規化してscore化する設計を試験実装した
- **結果**: **差別化そのものは劇的に回復した**（9軸中0軸が同点、pairwise gapは0点→100点まで拡大）。ただし軸ごとの`tiers`（strong/medium/weak）を見るとモデルの実際の判断は「medium vs strong」という穏やかな差であり、`ranking_tiers`の順位位置だけを見るv1のBorda変換がこれを0対100という極端な数値へ過剰増幅してしまう新たな限界が判明した
- **hypotheses_supported**: 主仮説（comparative Gate Bで差が回復する）、モデルは比較対象を同時に見せられれば明確な相対判断ができる
- **hypotheses_rejected**: 「ranking位置だけで妥当な数値正規化ができる」という副次的想定
- **one_line_takeaway**: comparative framing solved the differentiation problem that 2 prompt-only attempts could not, but the v1 rank-to-score conversion over-amplifies mild qualitative gaps into extreme scores; tier-weighted conversion is the next required step before any production consideration
- **next_experiments**: tier重み付きBorda変換の実装 / n≥3バッチでの再現性確認 / 本番経路への統合可否の判断（上記2点クリア後）
- **evidence_reports**: [quality_score_multidraft_gate_b_2026-08-25.md](quality_score_multidraft_gate_b_2026-08-25.md) / [.json](quality_score_multidraft_gate_b_2026-08-25.json)

### EXP-20260826-QS-SHADOWMODE-RUN3-01: Phase D shadow mode Run 3（parent: EXP-20260825-QS-MULTIDRAFT-01）

- **final_verdict**: `partial_improvement`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `score_compression`
- **試した内容**: R2-2の`tier_bounded_v1`マッピングを初めてlive run（実Gate A→Gate B→comparative Gate B）で検証した
- **結果**: gadget pairで**raw gap 100→mapped gap 7、top-1完全維持、gap_over_amplification解消**（Run1のgadget pairと完全に同じ結果を再現）。さらに運用ブランチの推奨とcomparative推奨が**3run中初めて一致（match）**した。一方fashion pairは、初回生成2件がGate Aでreject、修正版も含めて2回ともrejectされたため（うち1回はRun1/Run2で確立済みの安全パターンの再reject）、比較対象が確保できずcomparative検証ができなかった
- **hypotheses_supported**: H1（live実行でもtop-1維持）、H2（live実行でもgap moderation改善）——いずれもgadget pairで支持
- **new_finding**: fashion pairでのGate A再rejectは、既存の安全パターンが常に安全とは限らないというGate A/Bの非決定性（過去タスクの`gadget-restart-A`と同種）を改めて示した。これは新たなopen issueとして別枠で扱う
- **one_line_takeaway**: tier_bounded_v1 mapping reproduced its offline gains in a live run for the gadget pair (gap 100->7, top-1 retained, first-ever match with the operational recommendation), while the fashion pair could not be tested due to real Gate A rejections — including a re-rejection of an already-validated safe pattern, surfacing Gate A non-determinism as a separate open issue
- **next_experiments**: 実ユーザーによるhuman_judgment_mode=realの取得（gadget layerは技術条件が揃っているため最優先） / fashion layerのGate A非決定性の別途調査 / tier段階の精緻化
- **evidence_reports**: [shadow_mode_run_2026-08-26_run3.md](shadow_mode_run_2026-08-26_run3.md) / [.json](shadow_mode_run_2026-08-26_run3.json)

### EXP-20260827-FLHOOK-01: first-line hook evaluator 実装・replay検証（parent: EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01）

- **status**: `implemented_replay_validated`（`planned`から更新）
- **final_verdict**: `partial_improvement`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `first_line_hook_evaluator_candidate`、`opening_hook_vs_structure_split`、`human_stop_power_signal_extraction`
- **試した内容**: 設計文書どおりに`scripts/first_line_hook_evaluator.py`（新設、pure function層）、`external_audit_schema.py`（`FirstLineHookAxisResult`/`FirstLineHookEvaluationResult`等）、`external_audit_client.py`（`_FIRST_LINE_HOOK_EVALUATOR_SYSTEM_PROMPT`、`audit_first_line_hook_multidraft()`）、`post_generation_pipeline.py`（`run_first_line_hook_evaluator_experiment()`、`run_shadow_mode_first_line_hook_evaluator()`）を実装。既存のcomparative Gate B系コード・single-draft path・teacher_reference_score pathは一切変更していない。Run5/6/7の既存draft（`gadget-shadow5/6/7-A/B`）へ、新規Gate A/comparative Gate B呼び出しなしでfirst-line hook evaluatorのみを実API経由でreplay実行した
- **結果**: **`hook_top_candidate_id`が3/3バッチすべてでhuman_initial_top・human_final_topの両方と一致した。** `structure_hook_alignment`も3/3バッチすべて`false`（structure側は一貫してB案、hook側は一貫してA案）。これは設計文書の理想条件（「structure側=案2、hook側=案1、human側=案1というズレを安定して再現・説明できる」）を満たす結果
- **new_finding**: hook_summary_reasonはいずれも「個人的要素・明確な対比・具体的実体験による興味喚起」を挙げており、structure側の推奨理由（構造保持・忠実度）とは明確に異なる観点だった。opening_textのみを渡す設計（`format_candidates_for_prompt()`がdraft_text全文をprompt候補に含めないことをコードレベルで保証）により、モデルの判断が構造忠実度側の判断から実際に分離されたことが示唆される
- **caveat**: n=3は既知3ケースへのreplayであり、新規batch・新規sourceでの独立検証ではない。real humanへhook_topを開示した上でのfull cycle検証（Run5/6/7と同型の新規run）もまだ実施していない。この2点が揃うまでは`validated_improvement`としない
- **one_line_takeaway**: The first-line hook evaluator, implemented as a fully separate research-only layer that only ever sees an 8-20 character opening excerpt, reproduced the hypothesized split in a 3/3 replay of Run5/6/7's known drafts: comparative Gate B's structure-favored top stayed unchanged, while the hook evaluator's top matched the real human's initial and final choice in every case, though this is a replay of already-known cases and not yet independent new human validation
- **next_experiments**: 新規batchでのreal human full cycle検証（hook_topを開示した上でのhuman_initial/final judgment再取得） / fashion layerでの検証 / n≥2の独立した新規sourceでの再現性確認
- **evidence_reports**: [first_line_hook_evaluator_implementation_2026-08-27.md](first_line_hook_evaluator_implementation_2026-08-27.md) / [first_line_hook_evaluator_replay_results_2026-08-27.json](first_line_hook_evaluator_replay_results_2026-08-27.json) / [first_line_hook_evaluator_design_2026-08-27.md](first_line_hook_evaluator_design_2026-08-27.md) / [.json](first_line_hook_evaluator_design_2026-08-27.json)

### EXP-20260827-GADGET-QUERY-REDESIGN-01: Phase 1 gadget teacher collection queryの再設計（parent: EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01）

- **final_verdict**: `partial_improvement`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `teacher_supply_variability`、`query_design_over_constrained`
- **試した内容**: Run8・Run9でgadget teacher供給が通算4回0件だったことを受け、`scripts/x_api_phase1_collect.py`のQUERIES定数のgadget部分のみを、対象語単独（「40代 イヤホン」）からteacher-post構造語（比較/実体験/usage_scene/comparison_axis）を含む構成へ再設計した。A案（既知teacher再捕捉寄り）3本・B案（新規teacher開拓寄り）3本で2ラウンドのテストを実施した。Phase 2 classify・own-post exclusion・Gate A・thresholds・shipping decision・teacher_reference_score・downstream loggingは無変更、fashionクエリも対象外で無変更
- **結果**: Round1（4〜6語AND）は6/6が0件。Round2（2〜3語へ緩和）で、**「比較」をAND必須語に含めるクエリは全パターン（A案3本+B案1本、計4本）が0件だった一方、axis語単独クエリ（音漏れ・装着感）2本は各15件ヒットした。** gadgetタグ付き投稿28件を得たが、pre_teacher_candidateには到達しなかった
- **new_finding**: 「比較」という語をAND条件に含めると、他のどんな語と組み合わせても0件になるという明確なパターンを確認した。X API recent searchのこのニッチな話題での母数が小さく、複数の具体語をAND指定すると急速に0件へ収束することが分かった。一方、manual_review落ち候補の質はニュース/愚痴/雑談（以前100%）から製品レビュー/ギブアウェイ/使用感インプレッション（今回0%がニュース/愚痴/雑談）へ質的にシフトした
- **hypotheses_rejected**: 「比較構造語をクエリに含めれば比較構造を持つ投稿を直接収集できる」という仮説は反証された（「比較」を含むクエリは全パターンで0件）
- **one_line_takeaway**: The gadget query redesign confirmed that AND-combining '比較' with any other specific term collapses X API recent search results to zero, while axis-only queries (音漏れ/装着感) reliably surface gadget-relevant content that is qualitatively closer to teacher material than before (no more news/complaint noise), but none reached the teacher-candidate bar in this test batch, so Run 10 forward validation remains blocked pending a third query iteration that drops the '比較' AND-constraint entirely
- **next_experiments**: 「比較」をAND必須語から外し、axis語を単独または2語以内で使うクエリセット（round3）を試す / usage scene語も単独または2語以内で試す / 収集後のPhase 2分類器側で比較構造の有無を判定する設計を徹底する
- **evidence_reports**: [gadget_query_redesign_2026-08-27.md](gadget_query_redesign_2026-08-27.md) / [.json](gadget_query_redesign_2026-08-27.json)

### EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01: Phase D shadow mode Run 10（parent: EXP-20260827-FLHOOK-01）

- **final_verdict**: `partial_improvement`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `teacher_supply_recovered_for_gadget`、`forward_validation_live_result`、`structure_hook_alignment_case`、`source_dependent_alignment`
- **試した内容**: Round3で確保した真正teacher quality source（post_id=2092424287672311915、「会議 イヤホン マイク」由来）を用い、first-line hook evaluatorの初のlive forward validationを実施した。初回draft Aは実Gate Aで構造/比較フレーム/具体性の喪失によりreject、指摘を反映した修正版A2を1回のみ再生成しpass。A2とBでcomparative Gate B本体（structure評価）とfirst-line hook evaluatorを実行し、`comparative_snapshot_persisted=true`を確認した
- **結果**: **`structure_top_candidate_id`と`hook_top_candidate_id`がともに`gadget-run10-B`で一致（`structure_hook_alignment=true`）、`human_final_top`も同じくB案で一致した。** Run5/6/7 replayで観測された「structure=B、hook=A、human=A」という分離パターンは、このlive sourceでは再現しなかった
- **new_finding**: **Step A（非開示でのhuman_initial_top取得）の直前メッセージで、structure/hook推奨結果を誤って開示してしまう手続き上のミスが発生した。** このためhuman_initial_topはdisclosure-contaminatedとして無効化し、`structure_vs_human_initial_match`・`hook_vs_human_initial_match`は`null`のまま記録した。`human_final_top`以降は有効なデータとして扱い、`structure_vs_human_final_match`・`hook_vs_human_final_match`はともに`match`
- **one_line_takeaway**: Run 10 completed the first live forward validation of the first-line hook evaluator on a newly recovered gadget teacher source: structure evaluator, hook evaluator, and real human final judgment all converged on the same draft, a result that does not reproduce the structure-vs-hook split seen in the Run5/6/7 replay but does confirm the hook evaluator did not diverge from human judgment on live data — though the run's own Step A disclosure error means human_initial_top could not serve as valid blind-judgment evidence, so only the final-judgment match is counted
- **next_experiments**: 別のgadget teacher sourceでの追加live validation実施 / structure/hookが一致するケースと分離するケースをsource特性で整理する / Step A非開示の徹底（開示前チェックの運用手順化）
- **evidence_reports**: [shadow_mode_run_2026-08-27_run10_flhook_live.md](shadow_mode_run_2026-08-27_run10_flhook_live.md) / [.json](shadow_mode_run_2026-08-27_run10_flhook_live.json)

### EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01: Phase D shadow mode Run 11（parent: EXP-20260827-FLHOOK-01、sibling: EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01）

- **final_verdict**: `partial_improvement`（`phase_e_readiness=partially_ready`）
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `opening_hook_vs_structure_split`、`human_stop_power_signal_extraction`、`structure_hook_alignment_case`、`score_compression`
- **試した内容**: Run 10のStep A disclosure contaminationを踏まえ、`step_a_recommendation_hidden`/`step_a_disclosure_contamination`の明示追跡フラグを導入し、first-line hook evaluatorのlive forward validationを再実施した。第一候補source（`2092972468260774213`）はdraft A・修正版A2ともGate Aで構造崩壊によりrejectされ有効ペアを確保できず、フォールバックとして既知source（`2092424287672311915`、Run10と同一だが新規draft文面）へ切替え、draft C→C2（修正後pass）とdraft D（初回pass）の2案で実施した。comparative Gate B・first-line hook evaluatorの実行はコード側で標準出力にstructure_top/hook_topを一切printせず、チャット上でもStep A（本文のみ提示）完了までは一切言及しなかった
- **結果**: **`structure_top_candidate_id=gadget-run11-D`、`hook_top_candidate_id=gadget-run11-C2`で`structure_hook_alignment=false`（分離）。`human_initial_top`=C2（開示前）、`human_final_top`=C2（開示後も不変）。** `hook_vs_human_initial_match`・`hook_vs_human_final_match`はともに`match`、`structure_vs_human_initial_match`・`structure_vs_human_final_match`はともに`mismatch`。`human_final_confidence_self_report`はhigh→mediumへ低下したが決定は変わらず（`did_any_recommendation_change_human_decision=false`）
- **new_finding**: **Run5/6/7・FLHOOK-01 replayで確立していた「structure≠hook、hook=human」パターンが、Step A非開示guardを守った状態のlive runで初めて再現した。** Run10（3者一致）とは異なる結果であり、structure/hook分離が起こる条件はsourceの性質に依存する可能性が示唆されたが、n=1のため一般化はできない。n=2バッチのtier_bounded_v1マッピングは、raw gap 100をmapped gap 9まで圧縮してもなおn=2 pairwise閾値7をわずかに超過し、3段階丸めの精度限界が改めて確認された
- **one_line_takeaway**: Run11では、Step A非開示guardを守ったlive条件でも「structure≠hook、hook=human」パターンが再現し、first-line hook evaluator が実人間判断に沿う可能性を前進させたため、partial_improvement と記録する。
- **note**: Run11は、Run10と同じ教師ソースをフォールバック使用しつつ、Step Aでstructure/hook推奨を非開示のまま human initial judgment を取得し、その後の開示を経て final judgment まで完了した guarded live forward validation である。結果は structure_top=gadget-run11-D、hook_top=gadget-run11-C2、human_initial_top=gadget-run11-C2、human_final_top=gadget-run11-C2 で、structure は initial/final とも mismatch、hook は initial/final とも match となった。これは Run5/6/7 および FLHOOK-01 replay で観測された「structure≠hook、hook=human」パターンを live 条件で再確認したものであり、Run10の3者一致ケースとは異なる。production設定や閾値は無変更で、現時点では recommendation-only 運用を維持しつつ、追加live runで source依存性と再現性を継続検証する。
- **next_experiments**: 別sourceでの追加live validationを重ね、structure/hook分離が起こる条件（source性質との相関）を特定する / n=2バッチのtier_bounded_v1丸め精度の改良（R2-3）
- **evidence_reports**: [shadow_mode_run_2026-08-27_run11_flhook_live_guarded.md](shadow_mode_run_2026-08-27_run11_flhook_live_guarded.md) / [.json](shadow_mode_run_2026-08-27_run11_flhook_live_guarded.json)

### EXP-20260828-METAGATE-DIVERGENCE-01: structure/hook divergence meta判定（勝敗判定ではなくreview priority signal）（parent: EXP-20260827-FLHOOK-01、sibling: EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01, EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01, EXP-20260828-QS-SHADOWMODE-RUN12-FLHOOK-LIVE-GUARDED-02, EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01）

- **final_verdict**: `partial_improvement`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `opening_hook_vs_structure_split`、`structure_hook_alignment_case`、`hook_vs_structure_scope_design_issue`
- **試した内容**: Run11(hook=human)/Run12(structure=human)で的中方向が逆転し、Run13のhook_v2改良も仮説を支持しなかったことを受け、「hookをstructureより強くする」路線から「structure/hookのsplit自体をreview priority signalとして検知する」路線へ転換した。`scripts/first_line_hook_evaluator.py`へ`compute_hook_v1_axis_consensus()`、`external_audit_schema.py`へ`MetaGateDivergenceResult`等、`post_generation_pipeline.py`へ`evaluate_structure_hook_divergence()`（外部AI呼び出しなしの純粋な後段計算）を追加した。divergence判定の入力はhook_v1のみとし、hook_v2は採用しない。Run10/11/12の既存結果へreplayした
- **結果**: **期待した3パターンをすべて再現できた——Run10: `structure_hook_divergence=false`／`recommended_review_mode=auto_candidate_ok`。Run11・Run12: `structure_hook_divergence=true`／`divergence_type=mutual_disagreement`／`divergence_severity=high`／`recommended_review_mode=human_review_priority_high`。** Run11のmapped_gap=9・hook_v1_axis_consensus=0.5（4軸中2軸合意）、Run12のmapped_gap=7・hook_v1_axis_consensus=1.0（4軸全一致）
- **new_finding**: hook_v1の内部軸合意度の強さと、その判断が実際に人間判断へ的中するかどうかは相関しなかった（Run11: consensus=0.5でも的中／Run12: consensus=1.0でも不的中）。Run11とRun12で「どちらが人間に当たるか」は自動では確定しなかったが（実際に逆方向）、「split自体を高優先度レビュー対象として検出できるか」という主目的は両runとも達成できた
- **one_line_takeaway**: reframing structure/hook disagreement from a winner-take-all contest into a review-priority signal successfully classified all 3 known cases as expected, even though which side actually matched human judgment flipped between Run11 and Run12 — confirming that divergence itself, not its direction, is the useful signal
- **next_experiments**: fashion layer等でのdivergence判定の再現性確認 / `recommended_review_mode`を実際の運用フローへ接続する設計の検討 / `hook_v1_axis_consensus`と的中方向の相関をn≥5で再検証する
- **evidence_reports**: [meta_gate_divergence_design_2026-08-28.md](meta_gate_divergence_design_2026-08-28.md) / [.json](meta_gate_divergence_design_2026-08-28.json) / replay: [meta_gate_divergence_replay_2026-08-28.json](meta_gate_divergence_replay_2026-08-28.json)

---

## validated_improvements（9件）

EXP-20260821-FASHION-HEADLINE-01（テンプレート修正）、EXP-20260821-EXCL-01（own-post exclusion）、EXP-20260821-GADGET-TIER-01（gadget二層化）、EXP-20260821-FIXNORM-01（required_fixes正規化層）、EXP-20260823-GATESPLIT-01（Gate A/B split）、EXP-20260823-THRESH-01（two-threshold redesign）、EXP-20260824-SCORECONSIST-01（Gate B score consistency fix）

上記7件はいずれも`operational_impact`が`production_enabled`または`guardrail_added`であり、現行の本番パイプラインの前提として稼働中。

### EXP-20260826-QS-MAPPING-R2-2-01: Comparative ranking to bounded normalized score mapping（R2-2）

- **final_verdict**: `validated_improvement`
- **operational_impact**: `needs_followup`（research-only pathのまま。本番shipping decisionには未接続）
- **内容**: comparative Gate Bのgap over-amplification（0対100等）は、judgment自体ではなくranking→score変換層（v1 Borda）の粗さが主因であるという仮説を実証した。`tier_bounded_v1`マッピング（rank baseline + tier差分 + confidence差分、67-84点でcap）へ変換層のみを差し替え、Run1/Run2の4バッチへオフライン再適用した結果、**top-1は4/4で完全維持、平均spreadは85.0点→8.5点（約90%縮小）**
- **残る限界**: tier/confidence調整が3段階丸めのため、実質的な差の大小（weak含みの大きな差 vs medium/strongのみの穏やかな差）を完全には区別できていない
- **evidence_reports**: [comparative_score_mapping_r2_2_2026-08-26.md](comparative_score_mapping_r2_2_2026-08-26.md) / [.json](comparative_score_mapping_r2_2_2026-08-26.json)

### EXP-20260827-GADGET-QUERY-REDESIGN-ROUND3-01: Phase 1 gadget query Round3（parent: EXP-20260827-GADGET-QUERY-REDESIGN-01）

- **final_verdict**: `validated_improvement`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`（新規teacher候補は確保できたが、Run10相当のforward validationはまだ実施していない）
- **root_cause_family**: `teacher_supply_variability`、`query_design_over_constrained`
- **試した内容**: Round2の知見（「比較」をAND必須語に含めると母数の小さいこの話題では0件へ収束する）を踏まえ、「比較」「実体験」を完全に外し、axis/scene語（通勤/会議/ランニング/音漏れ/装着感/耳痛い/聞こえ方/マイク/充電/オープンイヤー/ながら聴き/耳を塞がない等）を主軸にした16クエリへ拡張した
- **結果**: **16本中15本がヒットし、gadget layerでpre_teacher_candidateが初めて複数件（4件）確保できた。** 内容を個別確認したところ、2件は`#PR`/`#ad`タグ付き広告投稿でteacher扱いせず除外、1件（post_id 2092424287672311915、「会議 イヤホン マイク」由来）が実体験・優先順位逆転の比較構造・usage_scene・明確な結論のすべてを満たす真正のteacher候補、1件がborderline候補だった
- **new_finding**: ヒット数の増加は同時に広告投稿の混入も増やした。Phase 2分類器の広告タグ検出には限界があり、機械的なpre_teacher_candidate判定を鵜呑みにせず内容を個別確認する運用が引き続き必要であることを確認した
- **one_line_takeaway**: Round 3 confirmed the hypothesis from Round 2: dropping '比較'/'実体験' as AND-required terms and using axis/scene words as the primary query strategy recovered a genuine gadget teacher candidate (post_id=2092424287672311915) for the first time since Run7, unblocking forward validation of the first-line hook evaluator, though 2 of the 4 pre_teacher_candidate hits were ad content that a Phase 2 classifier limitation let through and were manually excluded rather than treated as teachers
- **next_experiments**: post_id 2092424287672311915を使ったRun10相当のforward validation（gadget draft生成→Gate A→comparative Gate B→first-line hook evaluator→real human full cycle） / Phase 2 classifyの広告タグ検出強化（本タスクの変更対象外、別タスク）
- **evidence_reports**: [gadget_query_redesign_round3_2026-08-27.md](gadget_query_redesign_round3_2026-08-27.md) / [.json](gadget_query_redesign_round3_2026-08-27.json)

## measurement_bugs_fixed（2件、政策判断の失敗と区別）

| experiment_id | title | 内容 |
|---|---|---|
| EXP-20260823-SHIPTHRESH80-01 | 旧SHIP_THRESHOLD=80過剰ブロック | 実測分布の裏付けなしに運用されていた閾値。teacher実測でp7%しか通過できないと判明し、two-threshold redesignで是正 |
| EXP-20260825-TEACHERBUG-01 | teacher_reference_score誤rubric正規化 | Gate B score consistency fix実装時の漏れ。teacher_reference_scoreに誤ってGate B配点を適用していた実装バグ |

**この2件は`failed_experiment`ではなく`measurement_bug`に分類している。** 「試したが効果が無かった実験」ではなく「実装・運用検証の不備」であるため。

## inconclusive_results（13件、follow-up前提）

| experiment_id | title | 保留理由 |
|---|---|---|
| EXP-20260821-TEACHER-REPRO-01 | 先生変換精度検証 | Intersection原文が完全な形で入手できていない |
| EXP-20260825-TEACHERDIST-RERUN-01 | teacher distribution再測定 | 上方シフトの原因が測定方法の変化か実質的な質の差かを未分離 |
| EXP-20260825-SCALECHECK-01 | モード間スケール比較 | 圧縮の根本原因（rubric側かprompt側か）は本比較だけでは未確定 |
| EXP-20260825-QS-SHADOWMODE-RUN1-01 | Phase D shadow mode Run 1 | n=1 runのみで、mismatch傾向が一般化できるか未確認だった（Run 2で2件目を確保） |
| EXP-20260826-QS-SHADOWMODE-RUN2-01 | Phase D shadow mode Run 2 | 2回目のrunでもhuman_judgment_modeがproxyのまま、tier重み付き変換も未実装のためPhase Eには未達 |
| EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01 | Phase D shadow mode Run 4（gadget layer real human judgment） | human_initial_topは実取得できたが、comparative推奨開示後のhuman_final_topが未収集のままrun_status=closed_incompleteで終了したため |
| EXP-20260826-QS-SHADOWMODE-RUN5-REALFINAL-01 | Phase D shadow mode Run 5（gadget layer real human final judgment） | フルサイクルは完了したがn=1のみで、comparative推奨とhuman final判断のmismatchが評価軸ギャップか個人嗜好かを判別できないため |
| EXP-20260826-QS-SHADOWMODE-RUN6-REALHUMAN-01 | Phase D shadow mode Run 6（Run5 mismatchパターンの再現確認） | n=2への到達で系統的パターンの候補としては強まったが、評価軸改良実験（hook軸追加）が未着手だったため |
| EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01 | Phase D shadow mode Run 7（hook_augmented_v1 comparative Gate B real-human verification） | hook軸追加という対策を試したが効果が確認できず、次の対策（first-line evaluator等）が必要なため |
| EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01 | Phase D shadow mode Run 8（first-line hook evaluator forward validation） | gadget layerの教師投稿供給が枯渇し、Gate A以降の工程に進めなかったため（closed_incomplete） |
| EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01 | Phase D shadow mode Run 9（gadget教師投稿供給回復確認・forward validation再試行） | 供給回復確認を再試行したが2回とも未回復のため、Run8同様closed_incompleteで終了したため |
| EXP-20260828-QS-SHADOWMODE-RUN12-FLHOOK-LIVE-GUARDED-02 | Phase D shadow mode Run 12（別sourceでのguarded live forward validation） | hookがhuman initial/finalのいずれとも不一致となり（structure側が的中）、「hook=human」仮説が単一runで反証されたが、n=3（live）のため一般化・棄却いずれも時期尚早なため |
| EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01 | hook evaluator再設計（opening span evaluator/hook_v2） | replayでRun12（狙ったケース）が無改善、Run11（既存hook_v1が正解していたケース）はむしろ悪化したため。窓拡張がstructure寄りの判断を招くという別の仮説が浮上したが、n=3のreplayのみで一般化不可 |

### EXP-20260828-QS-SHADOWMODE-RUN12-FLHOOK-LIVE-GUARDED-02: Phase D shadow mode Run 12（parent: EXP-20260827-FLHOOK-01、sibling: EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01, EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01）

- **run_status**: `completed`
- **final_verdict**: `inconclusive_result`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `opening_hook_vs_structure_split`、`structure_hook_alignment_case`、`human_stop_power_signal_extraction`、`score_compression`
- **試した内容**: Run11の追加follow-up（別sourceでの再検証）として、Round3緩和済みクエリで新規収集した`2092972468260774213`（Run10/Run11とは異なる、Run11で一度draft失敗し未成立だったsource）をprimaryに採用し、Step A非開示guard付きでlive forward validationを実施した。draft E（初回pass）とdraft F（捏造比較軸+構造崩壊でreject）→F2（1回のみの修正、pass）の2案でcomparative Gate B・first-line hook evaluatorを実行した
- **結果**: **`structure_top_candidate_id=gadget-run12-E`、`hook_top_candidate_id=gadget-run12-F2`で`structure_hook_alignment=false`（分離）。`human_initial_top`=E、`human_final_top`=E。structure側は初期・最終とも`match`、hook側は初期・最終とも`mismatch`。** Run5/6/7・FLHOOK-01 replay・Run11で確立していた「hook=human」パターンが本runで初めて崩れた
- **new_finding**: human側の理由づけから、E案自体の冒頭（「ジム用は…自宅用は…」）が強い比較フックを持っていた可能性があり、first-line hook evaluatorが評価対象とする冒頭8〜20文字の範囲では、文全体に及ぶ比較構造の効き方を十分に捉えられていない可能性が新たな仮説として浮上した。first-line hook evaluatorの人間判断予測力はreplay 3/3 + live 1/3（Run10=区別力なし、Run11=hook的中、Run12=structure的中）となり、単純な優位仮説を保留する必要がある
- **one_line_takeaway**: Run11まで見えていた「hook=human」パターンが、別sourceのguarded live条件（Step A非開示guard維持）で崩れ、今回はstructure側がhuman判断（initial/finalとも）を的中させた。これによりfirst-line hook evaluatorの優位仮説はまだ確定できず、production shipping decisionには接続せずrecommendation-only運用を維持する。
- **note**: run_status=completed、phase_e_readiness=partially_ready。primary source（2092972468260774213、Run10/Run11とは異なる新規source）でGate A生存2本（gadget-run12-E、gadget-run12-F2）を確保でき、fallbackは不要だった（used_fallback_source=false）。structure_top_candidate_id=gadget-run12-E、hook_top_candidate_id=gadget-run12-F2、human_initial_top=gadget-run12-E、human_final_top=gadget-run12-Eで、structure_vs_human_initial_match=match、structure_vs_human_final_match=match、hook_vs_human_initial_match=mismatch、hook_vs_human_final_match=mismatch。Step A非開示guard（step_a_recommendation_hidden=true、step_a_disclosure_contamination=false）は遵守された。mainline_status=completed_mainline かつ shadow_status=completed_shadow_optional の両方を満たした。hook=humanパターンが崩れたためfirst-line hook evaluatorの優位性は確定できず、production設定・thresholds・shipping decisionは無変更のままrecommendation-only運用を維持する。research-only、本番shipping decisionには未接続。自動投稿は行っていない。
- **next_experiments**: 少なくとも2〜3件の追加live runで、hook/structureのどちらが人間判断を予測するかの方向性とsource特性（冒頭文の構造、比較軸の提示位置）との相関を特定する / first-line hook evaluatorの評価対象範囲（冒頭8〜20文字）が比較構造が文全体に及ぶケースを正しく評価できているかを検証する
- **evidence_reports**: [shadow_mode_run_2026-08-28_run12_flhook_live_guarded.md](shadow_mode_run_2026-08-28_run12_flhook_live_guarded.md) / [.json](shadow_mode_run_2026-08-28_run12_flhook_live_guarded.json)

### EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01: hook evaluator再設計（opening span evaluator/hook_v2）（parent: EXP-20260827-FLHOOK-01、sibling: EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01, EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01, EXP-20260828-QS-SHADOWMODE-RUN12-FLHOOK-LIVE-GUARDED-02）

- **final_verdict**: `inconclusive_result`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `opening_span_underreach`、`comparison_lockin_window_misalignment`、`hook_vs_structure_scope_design_issue`
- **試した内容**: Run11(hook_v1=human)/Run12(structure=human)の食い違いを受け、「hook_v1の冒頭8〜20文字固定窓が比較構造を取りこぼしている」という仮説を検証するため、research/shadow mode限定のopening span evaluator（hook_v2）を実装した。`scripts/first_line_hook_evaluator.py`へ冒頭句/冒頭1文/比較軸成立位置/結論着地位置の4スパン候補を抽出し実際に評価対象とするspanを選定する`select_opening_span()`等を追加、`external_audit_schema.py`/`external_audit_client.py`/`post_generation_pipeline.py`へhook_v2用のスキーマ・システムプロンプト・呼び出し関数を追加した（7軸: opening_phrase_sharpness/comparison_axis_lockin_speed/use_case_contrast_emergence/conclusion_landing_compactness/scroll_stop_power/ambiguity_penalty/theme_clarity_at_first_read）。hook_v1・comparative Gate B本体・production pathは無変更。実装後、Run10/11/12の既知draftペアへreplayを実施した
- **結果**: **Run10（hook_v2_top=B）はhuman final judgment(B)とmatchを維持したが、これは元々structure/hook_v1双方が正解していたケースで差別化力がない。Run11（hook_v2_top=D）はhuman final judgment(C2)とmismatchとなり、hook_v1が元々matchしていたケースを悪化させた。Run12（hook_v2_top=F2）もhuman final judgment(E)とmismatchのままで、狙っていた改善は得られなかった。**
- **new_finding**: opening spanを拡張するほどhook_v2の判断はstructure evaluatorの判断に近づく傾向が観測された（Run11で顕著: 両draftのspanがdraft全文近くまで拡張され、hook_v1が拾っていたC2の瞬発力的優位がstructureと同じD優位判断に上書きされた）。Run12ではE案のspanが比較構造を正しく含めて拡張されていたにもかかわらず、モデルの相対評価は依然としてF2を7軸すべてで優位と判断した。**hook_v1が意図的に短い窓に限定していたことが、structureとは異なる独立したシグナルを取り出す機能として働いていた可能性**が新たな仮説として浮上した
- **live実施の判断**: 事前に定めた実施条件（replayで最低限の説明力改善が見えた場合のみguarded liveに進む）を満たさなかったため（Run12は無改善、Run11はむしろ悪化）、**Run13のguarded live検証は実施しなかった**
- **one_line_takeaway**: widening the opening span to capture comparison structure and conclusion landing did not fix Run 12 and actively regressed Run 11 — expanding the window pulled hook_v2's judgment toward the structure evaluator's judgment rather than preserving hook_v1's distinct quick-impact signal, so the narrow-window hypothesis was not supported and guarded live validation was skipped per the pre-defined gate
- **next_experiments**: span拡張とstructure寄り判断の相関を、fashion layer等の別ケースでも確認する / 「spanが長くても構造の完成度ではなく最初の一撃としての強さを評価する」ことを明示的に強化したhook_v2b設計案の検討 / hook_v1とhook_v2を併用し両者が一致する場合のみrecommendationの確信度を上げる組み合わせ運用の検討
- **evidence_reports**: [hook_evaluator_window_redesign_2026-08-28.md](hook_evaluator_window_redesign_2026-08-28.md) / [.json](hook_evaluator_window_redesign_2026-08-28.json) / replay: [hook_evaluator_window_redesign_replay_2026-08-28.json](hook_evaluator_window_redesign_replay_2026-08-28.json)

### EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01: Phase D shadow mode Run 9（parent: EXP-20260827-FLHOOK-01）

- **run_status**: `closed_incomplete`（`close_reason=insufficient_gadget_teacher_candidates`）
- **final_verdict**: `inconclusive_result`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `opening_hook_vs_structure_split`、`human_stop_power_signal_extraction`、`forward_validation_pending`、`teacher_supply_variability`
- **試した内容**: Run8のclosed_incompleteを維持したまま再オープンせず、独立した別runとしてgadget layer教師投稿供給の回復確認を先行させ、回復していればforward validationへ進む設計で実X API収集を2回実行した
- **結果**: **2回とも、gadget layerのpre_teacher_candidateが0件だった。** Run8と合わせて通算4回の独立した収集試行すべてで、既知gadget先生（source_post_id=2086972244987900332）が一度も再出現しなかった。manual_review層の7件のgadget候補もすべて教師投稿要件を満たさず不採用とし、開始条件未達成のため`closed_incomplete`として終了した
- **new_finding**: gadget layerの教師投稿供給枯渇は一時的な変動ではなく、Run8・Run9の2run（通算4回の収集試行）にわたって継続している。これはfirst-line hook evaluator自体の性能とは独立した、上流のsource探索段階の供給問題であることを改めて確認した
- **one_line_takeaway**: Run 9, run as an independent supply-recovery check (not a reopening of Run 8), confirmed that gadget-layer teacher supply had still not recovered after 2 more real collection attempts (4 total across Run 8 and Run 9), so it was honestly closed as incomplete under the same insufficient_gadget_teacher_candidates condition rather than substituting a lower-quality source or switching layers
- **next_experiments**: gadget layerの教師投稿供給状況を定期的に確認する軽量チェック運用を検討する。供給が回復した時点でRun10相当の新規forward validation runを実施する。gadget layer以外でもforward validationが行えるよう、Run設計をlayer非依存に一般化することを検討する（別experiment_idとして正式に立てる）
- **evidence_reports**: [shadow_mode_run_2026-08-27_run9_flhook_live_retry.md](shadow_mode_run_2026-08-27_run9_flhook_live_retry.md) / [.json](shadow_mode_run_2026-08-27_run9_flhook_live_retry.json)

---

### EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01: Phase D shadow mode Run 8（parent: EXP-20260827-FLHOOK-01）

- **run_status**: `closed_incomplete`（`close_reason=insufficient_gadget_teacher_candidates`）
- **final_verdict**: `inconclusive_result`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `opening_hook_vs_structure_split`、`human_stop_power_signal_extraction`、`forward_validation_pending`、`teacher_supply_variability`
- **試した内容**: first-line hook evaluator（EXP-20260827-FLHOOK-01）を、既知replayではなく新規batchで前向き検証するため、実X API収集を2回実行した
- **結果**: **2回とも、gadget layerのpre_teacher_candidateが0件だった。** Run1〜7で7回連続ヒットしていた既知gadget先生（source_post_id=2086972244987900332）が今回は出現せず、manual_review層の8件のgadget候補もすべて比較構造・実体験を欠くため不採用とした。Gate A・comparative Gate B・first-line hook evaluator・human judgmentのいずれも実行できず、`closed_incomplete`として終了した
- **new_finding**: gadget layerの教師投稿供給が、8回目のrunで初めて枯渇した。これはfirst-line hook evaluator自体の性能とは無関係な、上流のsource探索段階の供給変動によるものであり、混同しないよう明記した。fashion layerへの切替も本runの目的逸脱となるため見送った
- **one_line_takeaway**: Run 8 attempted the first forward validation of the first-line hook evaluator on genuinely new data, but two real X API collection attempts found zero viable gadget-layer teacher candidates (the source that had appeared in all 7 prior runs), so the run was honestly closed as incomplete rather than substituting a low-quality candidate or switching layers outside the run's stated scope
- **next_experiments**: 後日、gadget layerで教師投稿供給が回復したタイミングでforward validation runを再実施する。gadget以外のlayerでも検証できるようRun 8の設計をlayer非依存に一般化することを検討する。教師投稿供給の枯渇傾向自体を別トピックとして記録・監視する
- **evidence_reports**: [shadow_mode_run_2026-08-27_run8_flhook_live.md](shadow_mode_run_2026-08-27_run8_flhook_live.md) / [.json](shadow_mode_run_2026-08-27_run8_flhook_live.json)

---

### EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01: Phase D shadow mode Run 7（parent: EXP-20260825-QS-MULTIDRAFT-01）

- **run_status**: `completed`
- **final_verdict**: `inconclusive_result`（Run7着手時の指示「単発runの最終判定は原則inconclusive_resultまたはpartial_improvementに留める」に従う。既存指標を悪化させたわけではないため`failed_experiment`は不適切と判断）
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `structure_fidelity_bias`、`hook_axis_added_but_not_effective`、`human_stop_power_preference`、`comparative_human_alignment_gap`
- **試した内容**: comparative Gate Bにhook系4軸（opening_hook_strength/first_phrase_sharpness/timeline_stop_power/instant_comparison_clarity、数値アンカーなし・相対順位+rationaleのみ）を追加した`comparative_rubric_version=hook_augmented_v1`を新設。既存9軸のロジック・legacy経路（audit_quality_score_multidraft_v1等）は一切変更せず、並行する新関数として実装。gadget layerで新規2draftを生成、実Gate Aで2件pass。`comparative_snapshot_persisted=true`をfinal human step前に確認し、非開示のままhuman_initial_topを取得（A、confidence=high）、comparative推奨（B）とhook軸結果を開示してhuman_final_topを再確認（A、confidence=medium、変更なし）
- **結果**: hook系4軸すべてが`B>A`という結果になり、`legacy_axes_top_candidate_id`と`hook_augmented_top_candidate_id`は完全に一致（変化なし）。`recommendation_vs_human_initial_match`・`recommendation_vs_human_final_match`はいずれも`mismatch`。Run5・Run6と完全に同型のパターン（confidence high→medium含む）が3run目でも再現した
- **new_finding**: hook軸を独立に評価させても、モデル自身はstructure/fidelity寄りの案の方がhook強度でも優れると判断した。これは、単純な軸追加だけでは人間の直感的な「冒頭の止まりやすさ」評価とモデルの評価を一致させるには不十分であることを示す、否定的だが有用な知見
- **one_line_takeaway**: Run 7 では hook 系評価軸を追加しても comparative-human mismatch は解消されず、モデルは引き続き構造忠実度の高い案2を推し、人間は冒頭フックの強い案1を選んだため、failed_experiment ではなく、次の設計変更を要する inconclusive_result として記録する
- **next_experiments**: 冒頭数語だけを比較するdedicated first-line hook evaluatorの設計。structure-fidelity scoringとhook-strength scoringの分離比較。additional real-human full-cycle runsによるmismatch再現性のさらなる確認（n≥4）
- **evidence_reports**: [shadow_mode_run_2026-08-26_run7_gadget_hookaxis.md](shadow_mode_run_2026-08-26_run7_gadget_hookaxis.md) / [.json](shadow_mode_run_2026-08-26_run7_gadget_hookaxis.json)

---

### EXP-20260826-QS-SHADOWMODE-RUN6-REALHUMAN-01: Phase D shadow mode Run 6（parent: EXP-20260825-QS-MULTIDRAFT-01）

- **run_status**: `completed`
- **final_verdict**: `inconclusive_result`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `human_alignment_pending`、`evaluation_axis_gap_candidate`、`structure_fidelity_bias_candidate`
- **試した内容**: Run5の再現確認として、独立した別runでgadget layer向けに新規2draftを生成。実Gate Aで2件pass。comparative Gate B raw + tier_bounded_v1 mappingをlive実行（raw: A=0/B=100、mapped: A=72/B=81、top-1維持、gap100→9）し、`comparative_snapshot_persisted=true`をfinal human step前に確認。非開示のままhuman_initial_topを取得（A、confidence=high）、comparative推奨（B）を開示してhuman_final_topを再確認（A、confidence=medium、変更なし）
- **結果**: `recommendation_vs_human_initial_match`・`recommendation_vs_human_final_match`はいずれも`mismatch`。Run5と完全に同型のパターン（comparative=構造/忠実度優位、human=冒頭フック優位、confidence high→medium）がn=2で再現した
- **new_finding**: mismatchがランダムなブレではなく系統的な評価軸ギャップの可能性を高めた。次実験として、comparative Gate Bにhook系軸を追加した場合の効果検証（Run 7）が妥当と判断された
- **one_line_takeaway**: Run 6 independently reproduced Run 5's exact mismatch pattern (comparative favors structure/fidelity, real human favors opening-hook strength; decision unchanged, confidence high->medium both times) — raising the evidence from n=1 anecdote to n=2 reproduction and motivating a follow-up experiment that augments comparative Gate B with hook-oriented axes
- **next_experiments**: comparative Gate Bにhook系軸を追加したrubric v2でmismatchが改善するか検証する（→EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01で着手・実施済み）
- **evidence_reports**: [shadow_mode_run_2026-08-26_run6_gadget_real_final.md](shadow_mode_run_2026-08-26_run6_gadget_real_final.md) / [.json](shadow_mode_run_2026-08-26_run6_gadget_real_final.json)

---

### EXP-20260826-QS-SHADOWMODE-RUN5-REALFINAL-01: Phase D shadow mode Run 5（parent: EXP-20260825-QS-MULTIDRAFT-01）

- **run_status**: `completed`
- **final_verdict**: `inconclusive_result`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `human_alignment_pending`、`evaluation_axis_gap_candidate`
- **試した内容**: Run4の再オープンではなく独立した別runとして、gadget layer向けに新規3draftを生成。実Gate Aで3本ともpass。comparative Gate B raw + tier_bounded_v1 mappingをlive実行（raw: A=23/B=100/C=23、mapped: A=75/B=81/C=69、top-1維持、gap77→12）し、`comparative_snapshot_persisted=true`をfinal human step前に確認。比較結果を非開示のままhuman_initial_topを取得（A、confidence=high）、その後comparative推奨（B）とその理由を開示してhuman_final_topを再確認（A、confidence=medium、変更なし）
- **結果**: `recommendation_vs_human_initial_match`・`recommendation_vs_human_final_match`はいずれも`mismatch`。`did_comparative_recommendation_change_human_decision=false`だが、`human_final_confidence_self_report`はhigh→mediumへ低下し、決定は変えなかったが確信度には影響した
- **new_finding**: 人間側の理由づけ（「冒頭数語で止める力」「比較軸の即時伝達」）は、comparative Gate Bの明示的な評価軸（構造保持・must_keep保持・原文忠実度・具体性密度等）に含まれておらず、評価軸ギャップの可能性を初めて実データで示唆した。ただしn=1のため一般化はできない
- **one_line_takeaway**: Run 5 completed the first full real human_judgment_mode=real cycle for the gadget layer without fabrication: the comparative recommendation did not change the human's final choice, but it measurably reduced their confidence in it, and the human's stated reasoning (opening-hook strength) pointed to a possible axis gap in comparative Gate B's evaluation criteria that requires n>=2 real runs to confirm
- **next_experiments**: real human judgmentをもう1〜2 run追加取得しmismatchパターンの再現性を確認する。comparative Gate Bの評価軸に「冒頭フック強度」を独立軸として追加する設計を検討する。fashion layerのGate A非決定性調査は本runと独立に継続する
- **evidence_reports**: [shadow_mode_run_2026-08-26_run5_gadget_real_final.md](shadow_mode_run_2026-08-26_run5_gadget_real_final.md) / [.json](shadow_mode_run_2026-08-26_run5_gadget_real_final.json)

---

### EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01: Phase D shadow mode Run 4（parent: EXP-20260825-QS-MULTIDRAFT-01）

- **run_status**: `closed_incomplete`（`close_reason=human_review_flow_interrupted_after_initial_judgment`）
- **final_verdict**: `inconclusive_result`
- **reuse_policy**: `reusable_with_conditions`
- **operational_impact**: `needs_followup`
- **root_cause_family**: `missing_artifact`、`reporting_inconsistency`、`human_alignment_pending`
- **試した内容**: gadget layerに限定し、実X API収集からGate A pass draft 2件（gadget-shadow4-A/C）を確保。comparative Gate B raw + tier_bounded_v1 mappingをlive実行（raw: A=0/C=100、mapped: A=72/C=81、top-1維持）。比較結果を一切開示せずにdraft本文2件を実ユーザーへ提示し、`human_judgment_mode=real`で`human_initial_top`を取得した
- **結果**: `human_initial_top=gadget-shadow4-A`。comparative推奨（raw top / mapped top ともに`gadget-shadow4-C`）とは**初のmismatch**を実データで観測した。しかしcomparative推奨の開示、およびその後の`human_final_top`確認の工程がセッション内で完了せず、`human_final_top`は`null`のまま記録した
- **new_finding**: comparative結果は当初「欠損」と誤認されかけたが、実際にはレポート・JSONに永続化されていた。これを`null`で上書き記録することは捏造にあたるため拒否し、正確な状態（comparative結果は実値、human final judgmentのみ未収集）で`closed_incomplete`とした。この訂正プロセス自体が、記録欠損の誤認とreal human final judgmentの未収集を同一のfailure classとして扱わないという再発防止事例になった
- **one_line_takeaway**: Run 4 obtained the first real human_initial_top data point for the gadget layer (a mismatch with the comparative recommendation), but the human review flow was interrupted before disclosure and final judgment could be collected, so the run was honestly closed as incomplete rather than fabricating a final decision
- **next_experiments**: 同一2draftに対しcomparative推奨開示込みでfinal judgment取得を再実施する。human_initial vs comparativeのmismatch傾向をn≥2で確認する。fashion layerのGate A非決定性調査は本runと独立に継続する
- **evidence_reports**: [shadow_mode_run_2026-08-26_run4_gadget_real.md](shadow_mode_run_2026-08-26_run4_gadget_real.md) / [.json](shadow_mode_run_2026-08-26_run4_gadget_real.json)

---

## 現在の active follow-ups（`followup_required=true`、23件）

| experiment_id | why_next | depends_on | blocked_by | priority | suggested_owner |
|---|---|---|---|---|---|
| EXP-20260821-TEACHER-REPRO-01 | Intersection先生の完全な原文があれば同じ手順で検証を再開できる | — | Intersection先生の完全な原文が未入手 | low | manual（ユーザーからの原文提供待ち） |
| EXP-20260821-GADGETAGE-01 | 監査モデルの過剰要求を制御する中間層が必要（→EXP-20260821-FIXNORM-01で着手済み） | EXP-20260821-GADGETAGE-01 | — | done（EXP-20260821-FIXNORM-01として完了） | claude_code |
| EXP-20260821-FIXNORM-01 | 単一judgeが安全性と品質を混同している問題自体の解消（→EXP-20260823-GATESPLIT-01で着手済み） | EXP-20260821-FIXNORM-01 | — | done（EXP-20260823-GATESPLIT-01として完了） | claude_code |
| EXP-20260823-SHIPTHRESH80-01 | teacher実測分布に基づく閾値再設定が必要（→EXP-20260823-THRESH-01で着手済み） | EXP-20260823-SHIPTHRESH80-01 | — | done（EXP-20260823-THRESH-01として完了） | claude_code |
| EXP-20260825-TEACHERDIST-RERUN-01 | quality_scoreモードとのスケール比較で閾値再校正の要否を判断する必要（→EXP-20260825-SCALECHECK-01で着手済み） | EXP-20260825-TEACHERDIST-RERUN-01 | — | done（EXP-20260825-SCALECHECK-01として完了） | claude_code |
| EXP-20260825-SCALECHECK-01 | quality_score共有軸の圧縮是正・構造系軸のalignment検討が必要（→EXP-20260825-QS-COMPRESSION-01で着手、失敗） | EXP-20260825-SCALECHECK-01 | — | done（EXP-20260825-QS-COMPRESSION-01として完了・失敗） | claude_code |
| EXP-20260825-QS-COMPRESSION-01 | quality_score圧縮是正の別仮説（質的アンカー版・軸境界シャープ化版）を試す必要がある（→EXP-20260825-QS-NEXT-01で着手、失敗） | EXP-20260825-QS-COMPRESSION-01 | — | done（EXP-20260825-QS-NEXT-01として完了・失敗） | claude_code |
| EXP-20260825-QS-NEXT-01 | prompt/rubric微修正は2連続失敗。multi-draft evaluationの設計・実装が必要（→EXP-20260825-QS-MULTIDRAFT-01で着手、partial_improvement） | EXP-20260825-QS-NEXT-01 | — | done（EXP-20260825-QS-MULTIDRAFT-01として完了・partial） | claude_code |
| EXP-20260825-QS-MULTIDRAFT-01 | comparative frameingの差別化効果は実証されたが、ranking→score変換（v1 Borda）がtier強度を無視して過剰増幅する。実batchでのshadow mode検証が必要（→EXP-20260825-QS-SHADOWMODE-RUN1-01で着手、n=1で観測） | EXP-20260825-QS-MULTIDRAFT-01 | — | done（EXP-20260825-QS-SHADOWMODE-RUN1-01として一部着手） | claude_code |
| EXP-20260825-QS-SHADOWMODE-RUN1-01 | n=1 runのみで一般化できなかった。Run 2以降のindependent runでmismatch傾向の再現性を確認する必要があった（→EXP-20260826-QS-SHADOWMODE-RUN2-01で着手、2件目確保） | EXP-20260825-QS-SHADOWMODE-RUN1-01 | — | done（EXP-20260826-QS-SHADOWMODE-RUN2-01として完了） | claude_code |
| EXP-20260826-QS-SHADOWMODE-RUN2-01 | 2回のindependent runでgadget layerの方向性は一致し、mismatchも客観的に説明できたが、human_judgment_modeが2回ともproxyのまま、かつtier重み付きBorda変換（R2-2）が未実装だった（→EXP-20260826-QS-MAPPING-R2-2-01で着手、validated_improvement） | EXP-20260826-QS-SHADOWMODE-RUN2-01 | — | done（EXP-20260826-QS-MAPPING-R2-2-01として完了） | claude_code |
| EXP-20260826-QS-MAPPING-R2-2-01 | オフライン再適用ではtop-1維持・spread90%削減を確認したが、live runでの再現性が未検証だった（→EXP-20260826-QS-SHADOWMODE-RUN3-01で着手、live再現を確認・partial_improvement） | EXP-20260826-QS-MAPPING-R2-2-01 | — | done（EXP-20260826-QS-SHADOWMODE-RUN3-01として完了） | claude_code |
| EXP-20260826-QS-SHADOWMODE-RUN3-01 | gadget layerはtop-1維持・gap moderation・matchの3点が揃い、tier_bounded_v1のlive再現は確認できた。残る課題は実ユーザーによるhuman_judgment_mode=real確認（→EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01で着手、closed_incomplete） | EXP-20260826-QS-SHADOWMODE-RUN3-01 | fashion layerのGate A非決定性調査、tier段階の精緻化 | done（human_initial_top取得はEXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01として一部着手・未完了） | claude_code |
| EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01 | human_initial_topは実取得できmismatchを観測したが、comparative推奨開示後のhuman_final_topが未収集のままclosed_incompleteで終了した（→EXP-20260826-QS-SHADOWMODE-RUN5-REALFINAL-01で独立runとしてフルサイクル完了） | EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01 | — | done（human final judgment回収はEXP-20260826-QS-SHADOWMODE-RUN5-REALFINAL-01として完了。Run4自体はclosed_incompleteのまま） | claude_code |
| EXP-20260826-QS-SHADOWMODE-RUN5-REALFINAL-01 | gadget layer初のreal human final judgmentを回収できたが、comparative推奨とはinitial/finalともmismatchし、n=1では評価軸ギャップかレビュアー個人の嗜好かを判別できなかった（→EXP-20260826-QS-SHADOWMODE-RUN6-REALHUMAN-01で着手、n=2で再現確認） | EXP-20260826-QS-SHADOWMODE-RUN5-REALFINAL-01 | — | done（EXP-20260826-QS-SHADOWMODE-RUN6-REALHUMAN-01として完了） | claude_code |
| EXP-20260826-QS-SHADOWMODE-RUN6-REALHUMAN-01 | n=2でmismatchパターンが再現し、系統的な評価軸ギャップの可能性が高まった。次はcomparative Gate Bへの評価軸改良（hook軸追加）が必要（→EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01で着手・実施済み） | EXP-20260826-QS-SHADOWMODE-RUN6-REALHUMAN-01 | — | done（EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01として完了） | claude_code |
| EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01 | hook系4軸を追加してもcomparativeモデル自身の判断は変わらず、n=3でmismatchパターンが再現した。次はhook軸を独立した評価ステップとして切り出すfirst-line evaluatorの設計・実装が必要（→EXP-20260827-FLHOOK-01で着手・実装・replay検証まで完了） | EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01 | — | done（EXP-20260827-FLHOOK-01として完了） | claude_code |
| EXP-20260827-FLHOOK-01 | 実装・既知3ケースへのreplayでは理想条件を満たす結果（hook_top=human final top、3/3）を得たが、n=3は既知ケースの再適用に留まる。新規batchでのreal human full cycle検証が必要（→EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01で着手、教師投稿供給枯渇によりclosed_incomplete） | EXP-20260827-FLHOOK-01 | — | done（forward validation試行はEXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01として着手したが未達成） | claude_code |
| EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01 | gadget layerの教師投稿供給が枯渇し、forward validationが実施できなかった。供給回復確認を先行させた再試行が必要（→EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01で着手、供給未回復のためclosed_incomplete） | EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01 | — | done（EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01として着手済み。供給は依然未回復） | claude_code |
| EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01 | Run8と合わせて通算4回連続でgadget layerの教師投稿供給が確認できなかった。クエリ設計自体の見直しが必要（→EXP-20260827-GADGET-QUERY-REDESIGN-01で着手、partial_improvement） | EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01 | — | done（EXP-20260827-GADGET-QUERY-REDESIGN-01として着手・部分改善） | claude_code |
| EXP-20260827-GADGET-QUERY-REDESIGN-01 | 『比較』をAND必須語から外したround3クエリ設計が必要（→EXP-20260827-GADGET-QUERY-REDESIGN-ROUND3-01で着手、validated_improvement——初のgadget teacher候補確保に成功） | EXP-20260827-GADGET-QUERY-REDESIGN-01 | — | done（EXP-20260827-GADGET-QUERY-REDESIGN-ROUND3-01として完了） | claude_code |
| EXP-20260827-GADGET-QUERY-REDESIGN-ROUND3-01 | 新規gadget teacher候補（post_id 2092424287672311915）を確保できたが、Run10相当のforward validationはまだ実施していない（→EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01で着手・完了、partial_improvement） | EXP-20260827-GADGET-QUERY-REDESIGN-ROUND3-01 | — | done（EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01として完了） | claude_code |
| EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01 | 初のlive forward validationで3者一致（分離なし）という結果を得た。hook evaluatorの優位性を確証するには、structure/hookが分離するsourceでの追加live validationが必要（→EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01でStep A非開示guard付きで実施、分離を再現） | EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01 | — | done（EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01として完了） | claude_code |
| EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01 | hook evaluatorはreplay 3/3 + live 1/2（Run10=alignment true、Run11=alignment false・hook側がhuman final judgmentと一致）の支持を得た。structure/hook分離が起こる条件（source性質との相関）はまだ特定できておらず、Run10とRun11の違いを説明する追加live validationが必要（→EXP-20260828-QS-SHADOWMODE-RUN12-FLHOOK-LIVE-GUARDED-02で別sourceにて実施） | EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01 | — | done（EXP-20260828-QS-SHADOWMODE-RUN12-FLHOOK-LIVE-GUARDED-02として完了） | claude_code |
| EXP-20260828-QS-SHADOWMODE-RUN12-FLHOOK-LIVE-GUARDED-02 | 今回はstructure側がhuman判断を的中させ、hook側が外れた（Run11とは逆方向）。「hookがhuman判断を予測する」という単純な仮説は保留状態になり、hook/structureどちらが的中するかの条件を特定する必要がある（→EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01で評価窓自体の再設計として着手、ただしreplayで仮説不支持） | EXP-20260828-QS-SHADOWMODE-RUN12-FLHOOK-LIVE-GUARDED-02 | — | done（EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01として着手・replay完了） | claude_code |
| EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01 | hook_v2はRun12を改善できず、Run11をむしろ悪化させた。「窓拡張=改善」という前提は反証され、hookをstructureより強くする路線ではなく別の活用方法が必要（→EXP-20260828-METAGATE-DIVERGENCE-01でsplit自体をreview priority signalとして扱う路線へ転換して着手） | EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01 | — | done（EXP-20260828-METAGATE-DIVERGENCE-01として着手・replay完了） | claude_code |
| EXP-20260828-METAGATE-DIVERGENCE-01 | divergence検知の基本設計はreplayで期待どおり機能した。次はguarded liveでの実運用価値検証（Run14以降）が必要（→GOV-20260828-RUN14-PLUS-RESEARCH-POLICY-01でRun14以降の研究方針として明文化・優先順位付け） | EXP-20260828-METAGATE-DIVERGENCE-01 | — | done（GOV-20260828-RUN14-PLUS-RESEARCH-POLICY-01として方針明文化。Run14本体は未実施） | claude_code |
| GOV-20260828-RUN14-PLUS-RESEARCH-POLICY-01 | Run14（divergence meta-gateのguarded live forward validation）がまだ実施されていない。優先A（divergence live検証）・優先B（non-divergence安定確認）・優先C（teacher supply安定化）のうち、優先Aから着手するのが本筋（→GOV-20260828-ASYNC-ENRICHMENT-REDESIGN-01で学習モードのログ構造自体をさらに軽量化する再設計として並行着手。Run14本体はまだ） | EXP-20260828-METAGATE-DIVERGENCE-01 | gadget teacher supplyの確保（優先C次第で律速） | high（Run14本体は未実施のまま継続） | claude_code（要ユーザー承認、Run14実施の指示のため） |
| GOV-20260828-ASYNC-ENRICHMENT-REDESIGN-01 | Layer1〜3の実装は完了（minimal_run_log/enrichment_record/weekly_learning_review）。2026-08-29〜30の実運用でmainline run 10件がcompletedに到達し、実データでの週次集計も稼働した。運用中にATH-PRO5MK2×ジム用骨伝導×用途別使い分けテーマの複数回mainline再生成が判明（→GOV-20260830-POSTED-THEME-EXCLUSION-01で恒久対策を実装） | GOV-20260827-LEARNING-MODE-MAINLINE-SHADOW-SPLIT-01 | — | done（10 completed runs到達、GOV-20260830-POSTED-THEME-EXCLUSION-01として課題対応） | claude_code |
| **GOV-20260830-POSTED-THEME-EXCLUSION-01** | **registryへの新規entry自動追記の仕組み、fashion/intersection layer向けキーワード辞書の拡充、soft guard情報の人間レビュー画面への表示導線がいずれも未実装** | GOV-20260828-ASYNC-ENRICHMENT-REDESIGN-01 | — | **high（唯一の未完了follow-up）** | claude_code（要ユーザー承認、実装着手の指示のため） |
| **GOV-20260827-LEARNING-MODE-MAINLINE-SHADOW-SPLIT-01** | **Run11・Run12ともこの分割ルールの下で`mainline_status=completed_mainline`かつ`shadow_status=completed_shadow_optional`の両方を満たした。継続的な運用で軽量性が保たれるかは今後も確認が必要** | GOV-20260825-OPS-RESEARCH-SPLIT-01 | — | medium（継続監視、クローズしない） | claude_code |

**実質的に未着手のfollow-upは2件のみ**: EXP-20260821-TEACHER-REPRO-01（ユーザー起因のブロック）と、GOV-20260830-POSTED-THEME-EXCLUSION-01（唯一のオープンな技術課題。posted-theme guardの中核実装・検証は完了したが、registry自動追記・辞書拡充・表示導線はまだ）。他の30件は既に後続実験として着手・完了済み、または運用方針として継続監視中であり、lineageで辿れる。

---

## production guardrails currently active

現在の本番パイプラインで有効なガードレール（`guardrails_added`の集約）:

1. truncationした原文で欠落部分を推測補完しない（EXP-20260821-TEACHER-REPRO-01）
2. 自社投稿レジストリと照合しないまま候補を先生として採用しない（EXP-20260821-EXCL-01）
3. `render_comparison()`は必ず`age_angle`を`axis_intro`へ反映すること（EXP-20260821-GADGETAGE-01）
4. raw `required_fixes`を直接生成の入力として使わない。必ず正規化層を経由すること（EXP-20260821-FIXNORM-01）
5. Gate Aは安全性のみを判定し品質で判定しないこと。Gate Bはreject相当を返さないこと（EXP-20260823-GATESPLIT-01）
6. `QualityScoreResult.from_json()`は必ず`audit_mode`で正規化rubricを切り替えること。単一rubric固定にしない（EXP-20260825-TEACHERBUG-01）
7. `score_overall`/`quality_band`の算出元は`QualityScoreResult.from_json()`の1点に統一し、他所で再計算しない（EXP-20260824-SCORECONSIST-01）
8. quality_scoreプロンプトを変更する際は、必ずbefore/afterの実ライブ再監査で分散の変化を検証してから改善と呼ぶこと（EXP-20260825-QS-COMPRESSION-01）
9. quality_score圧縮是正はprompt/rubric微修正の反復では2連続で失敗した。3回目もprompt微修正のみで試みる前に、multi-draft evaluationの設計検討を優先すること（EXP-20260825-QS-NEXT-01）
10. Comparative Gate Bのscore変換にranking位置だけでなくtier強度（strong/medium/weak）を反映する改良を行うまで、本番shipping decision経路へ接続しないこと（EXP-20260825-QS-MULTIDRAFT-01）

## do_not_repeat summary

再利用禁止・注意事項の集約（`do_not_repeat`の集約）:

1. 末尾が省略記号で切れた原文をそのまま先生として採用しない
2. プロンプト修正だけで監査モデルの過剰要求を完全に制御できると想定しない
3. ブランド名・型番が実在しないまま生成へ渡す救済ロジックを作らない
4. 閾値を実測分布の検証なしに固定値のまま運用し続けない
5. 新しい`audit_mode`を追加する際、既存の正規化関数がそのまま流用できると仮定しない。軸名・配点の互換性を必ず確認する
6. この`_QUALITY_SCORE_SYSTEM_PROMPT`版（`QUALITY_SCORE_PROMPT_VERSION=v2_anchors_anticompression_2026-08-25`）を本番改善として扱わない
7. 数値アンカーを追加すれば分散が広がる、という前提を無条件に置かない
8. プロンプト文言の修正だけで1draft独立監査というアーキテクチャ制約を解決しようとしない
9. **『数値アンカーを外せば分散が改善する』という前提を置かない（EXP-20260825-QS-NEXT-01のvariant Aで反証済み。むしろ最も悪化した）**
10. **この`_QUALITY_SCORE_SYSTEM_PROMPT_VARIANT_A/B`を本番改善として扱わない**
11. **軸境界の説明を追加するだけで圧縮が直ると想定しない（variant Bで反証済み）**
12. **Comparative Gate Bのranking位置だけを見るv1のBorda変換を、そのまま本番採用しない（0対100のような過剰増幅を起こす。EXP-20260825-QS-MULTIDRAFT-01で判明）**
13. **n=2バッチのcomparative実験結果だけでarchitecture変更を「解決した」と断定しない（サンプル不足。n≥3での再現性確認が必要）**
14. **human final judgmentが未取得のまま、`human_final_top`をproxy値や運用ブランチの決定的選定規則の出力で埋めて代用しない。取れなかった場合は`null`のまま`closed_incomplete`として記録する（EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01で確立）**
15. **comparative Gate Bの結果がレポート・JSONに実際に永続化されているかを確認せず「欠損した」と早合点しない。人間レビューフローの中断とcomparative結果の記録欠損は別のfailure classである（EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01で確立）**

## open architecture issues

- **1draft独立監査（対応中、architecture実験で前進あり。gap over-amplificationはR2-2でオフライン解消、EXP-20260826-QS-SHADOWMODE-RUN3-01でlive再現も確認済み）**: Gate Bは元々同一候補の複数draftを横並びで比較する仕組みが無かった。EXP-20260825-QS-COMPRESSION-01・EXP-20260825-QS-NEXT-01の2実験で、prompt/rubric側の変数をどう変えても圧縮が解消しないことが確認され、EXP-20260825-QS-MULTIDRAFT-01でComparative Gate B v1を試験実装した結果、**差別化そのものは劇的に回復した**（zero-variance軸0/9）。ただし順位→スコア変換（v1 Borda）がモデルの穏やかな判断（tier: medium vs strong）を極端な数値（0対100）へ過剰増幅する新たな課題が判明。EXP-20260825-QS-SHADOWMODE-RUN1-01・EXP-20260826-QS-SHADOWMODE-RUN2-01（2回のshadow mode run）でこの過剰増幅が計4バッチ中3バッチで再現し、運用ブランチとcomparativeの推奨がmismatchする実例を各runで観測（Run1: fashion pair、Run2: gadget pair）。gadget layerの推奨方向自体は2回のrunで一致した。**EXP-20260826-QS-MAPPING-R2-2-01で`tier_bounded_v1`マッピングを実装し、judgment（誰が1位か）は変えずに変換層のみを差し替えた結果、top-1は4/4維持したまま平均spreadを85.0点→8.5点（約90%削減）に抑えることに成功した（オフライン再適用）。** その後**EXP-20260826-QS-SHADOWMODE-RUN3-01でlive run（新規Gate A→Gate B→comparative Gate B）でも同じ効果を確認**（gadget pair: raw gap100→mapped gap7、Run1と完全一致、gap_over_amplification true→false、combined retention 5/5=100%）。**運用ブランチの推奨とcomparative推奨が初めて一致（match）した。** 残る限界は3段階丸めによる精度不足（weak含みの大きな差とmedium/strongのみの穏やかな差が、最終スコアでは十分に区別されないケースがある）。**EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01でgadget layer初のhuman_judgment_mode=realデータ点（human_initial_top）を取得したところ、comparative推奨とmismatchした**（実人間はraw/mapped双方でstrong評価のgadget-shadow4-Cではなく、gadget-shadow4-Aを開示前に選好）。**EXP-20260826-QS-SHADOWMODE-RUN5-REALFINAL-01で、独立した別runとして初のフルサイクル（開示前初期判断→開示→最終判断）を完了させたところ、`recommendation_vs_human_initial_match`・`recommendation_vs_human_final_match`はいずれも`mismatch`となり、`did_comparative_recommendation_change_human_decision=false`だった（human_final_confidence_self_reportはhigh→mediumへ低下）。** 人間側の理由づけ（「冒頭数語で止める力」「比較軸の即時伝達」）はcomparative Gate Bの明示的な評価軸には含まれておらず、評価軸ギャップの可能性が実データで示唆された。**EXP-20260826-QS-SHADOWMODE-RUN6-REALHUMAN-01で独立した別runとしてn=2の再現確認を行い、Run5と完全に同型のmismatchパターン（comparative=構造/忠実度優位、human=冒頭フック優位、confidence high→medium）が再現した。** これを受け、**EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01でcomparative Gate Bに冒頭フック系4軸（opening_hook_strength/first_phrase_sharpness/timeline_stop_power/instant_comparison_clarity）を追加した`hook_augmented_v1`を実装・検証したが、hook軸を独立に評価させてもモデル自身の判断（legacy_axes_top_candidate_id）は変わらず、n=3でmismatchパターンがそのまま再現した。** 単純な評価軸追加では不十分であることが分かり、**EXP-20260827-FLHOOK-01で「hook軸を9軸評価から分離した独立判定器（first-line hook evaluator）」を設計・実装し、Run5/6/7の既存draftへreplay検証まで完了した**（冒頭8〜20文字のみを対象に、本文非開示で相対順位のみを取得する設計。`structure_top_candidate_id`と`hook_top_candidate_id`を併記し、comparative Gate B本体のtop-1・shipping decisionは上書きしない）。**replay結果はhook_top_candidate_idが3/3バッチすべてでhuman_initial_top・human_final_topの両方と一致し、structure_hook_alignmentも3/3バッチすべてfalseという、設計文書の理想条件を満たす結果だった。** **EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01で新規batchでのforward validationを試みたが、gadget layerの教師投稿供給が枯渇し（Run1〜7で7連続ヒットしていた既知先生が今回は出現せず）、Gate A以降の工程に進めなかった。** **EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01で、Run8を再オープンせず独立runとして供給回復確認を再試行したが、2回目も未回復のままだった（Run8・Run9合わせて通算4回連続で教師投稿0件）。** これはevaluator自体の性能に関する否定的データではなく、上流のsource探索段階の供給変動によるものであり、混同しないよう記録した。次は供給回復を待ってのforward validation再実施、および軽量な事前チェック運用の導入検討が必要
- **Gate A/Bの監査結果の非決定性（EXP-20260826-QS-SHADOWMODE-RUN3-01で改めて表面化）**: Run1/Run2で既に安全と判定され確立していたfashion側の定型締めパターン（`fashion-shadow3-B2`、「差がつくのは小物。X、Y、Zみたいな小さい部分で印象が整う」という既存の安全な締め方）が、Run3では同一理由（comparison構造の感想文化）で再度rejectされた。過去タスク（`production_selection_restart_2026-08-23`の`gadget-restart-A`等）でも同種の非決定性は観測済みだったが、今回は「既に安全と確認済みのパターン」が対象だった点が新しい。望む結果が出るまでdraftを再試行することは避けるべきとの判断からRun3では3回目のリトライを行わず、fashion pairはcomparative検証データが欠測したまま確定させた。原因（監査モデル側の非決定性か、プロンプト/文脈差か）は未調査。次は別タスクとしての原因調査が必要（未着手）
- **human final judgment取得フローの永続化・完了確認が未整備（EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01で発見、EXP-20260826-QS-SHADOWMODE-RUN5-REALFINAL-01以降で対策を運用適用済み）**: Run 4で、comparative Gate Bの結果は実際にはレポート・JSONへ永続化されていたにもかかわらず、human final judgment取得の直前で「comparative結果が欠損した」という誤った前提が一時的に生じかけた。実ファイルを確認して訂正したため実害はなかったが、Run 5・Run6・Run7では`comparative_snapshot_persisted=true`をfinal human step前に明示的に確認する手順を一貫して適用し、いずれもフルサイクルを問題なく完了できた（3run連続で確立した運用手順）。正式なrun log側の追跡フラグ実装（コードレベル）は依然未着手
- **comparative Gate Bの評価軸と実人間の重視点のギャップ（EXP-20260826-QS-SHADOWMODE-RUN5-REALFINAL-01で発見、Run6・Run7でn=3まで再現確認済み）**: real human final judgmentがcomparative推奨と3run連続でmismatchし、人間側の理由は一貫して「冒頭フックの強さ」「比較軸の即時伝達」だった。EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01でこの観点を明示的な評価軸として追加したが、モデル自身の判断は変わらなかった——単純な軸追加ではなく、評価プロセスそのもの（同一コール内での相対比較 vs 独立した第一印象評価）に起因する可能性が浮上した。**EXP-20260827-FLHOOK-01で、評価プロセスを分離する（冒頭のみを見せる独立判定器）実装を完了し、Run5/6/7へのreplayで3/3バッチが理想条件（structure top=案2型、hook top=案1型、human top=案1型）を満たすことを確認した。** これは仮説（評価プロセスの分離が原因）を支持する強いevidenceだが、n=3は既知ケースへのreplayであり、新規batchでのreal human full cycle検証（EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01・EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01の2runで試行するも、いずれも教師投稿供給枯渇により未達成）によるさらなる確認が必要（未着手）
- **gadget layerの教師投稿供給の不安定性（EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01で発見、EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01で継続確認、EXP-20260827-GADGET-QUERY-REDESIGN-01/ROUND3-01で対策完了・軽減）**: Run1〜7の全7回でgadget layerの既知先生（source_post_id=2086972244987900332、「イヤホン比較」）が安定的に再ヒットしていたが、Run8・Run9の通算4回の収集試行いずれでも出現せず、manual_review層の候補もすべて品質基準を満たさなかった。Round1/2でクエリ再設計を試み、「比較」をAND必須語に含めると即座に0件へ収束することを発見。**Round3で「比較」「実体験」をAND必須語から完全に外しaxis/scene語主軸の16クエリへ拡張した結果、初めて新規gadget teacher候補（post_id 2092424287672311915）を確保できた（`validated_improvement`）。** ただし4件中2件が広告投稿だったことから、Phase 2分類器の広告タグ検出限界という副次的な課題も判明した。次はこの新規teacherを使ったRun10相当のforward validationの実施が必要（未着手）
- **quality_scoreとteacher_reference_scoreの構造系軸の非対称性**（55点 vs 50点、概念的に非対応）。EXP-20260825-SCALECHECK-01で発見。intentional designとして明文化するかalignmentを取るか、方針未決定

---

## experiment lineage map

単一の直列チェーン（一部分岐あり）として辿れる:

```
EXP-20260821-TEACHER-REPRO-01（先生変換精度検証、Intersectionでblocked）
  └─ EXP-20260821-FASHION-HEADLINE-01（テンプレート修正）
       └─ EXP-20260821-EXCL-01（own-post exclusion）
            └─ EXP-20260821-GADGET-TIER-01（gadget二層化）
                 └─ EXP-20260821-GADGETAGE-01（age_angleバグ修正）
                      └─ EXP-20260821-FIXNORM-01（required_fixes正規化層）
                           └─ EXP-20260823-GATESPLIT-01（Gate A/B split）
                                ├─ EXP-20260823-SHIPTHRESH80-01（旧閾値の過剰ブロック、measurement_bug）
                                └─ EXP-20260823-THRESH-01（two-threshold redesign）
                                     └─ EXP-20260824-SCORECONSIST-01（Gate B score consistency fix）
                                          └─ EXP-20260825-TEACHERBUG-01（teacher rubric誤適用、measurement_bug）
                                               └─ EXP-20260825-TEACHERDIST-RERUN-01（teacher distribution再測定）
                                                    └─ EXP-20260825-SCALECHECK-01（モード間スケール比較）
                                                         └─ EXP-20260825-QS-COMPRESSION-01（quality_score圧縮是正、failed）
                                                              └─ EXP-20260825-QS-NEXT-01（quality_score圧縮是正 次実験、failed）
                                                                   └─ EXP-20260825-QS-MULTIDRAFT-01（Comparative Gate B v1試験実装、partial_improvement）
                                                                        ├─ EXP-20260825-QS-SHADOWMODE-RUN1-01（Phase D shadow mode Run 1、inconclusive_result）
                                                                        ├─ EXP-20260826-QS-SHADOWMODE-RUN2-01（Phase D shadow mode Run 2、inconclusive_result、sibling of RUN1）
                                                                        ├─ EXP-20260826-QS-MAPPING-R2-2-01（Comparative score mapping R2-2、validated_improvement、sibling of RUN1/RUN2）
                                                                        ├─ EXP-20260826-QS-SHADOWMODE-RUN3-01（Phase D shadow mode Run 3、partial_improvement、sibling of RUN1/RUN2/R2-2-MAPPING）
                                                                        ├─ EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01（Phase D shadow mode Run 4、gadget layer real human judgment、inconclusive_result（closed_incomplete）、sibling of RUN1/RUN2/R2-2-MAPPING/RUN3）
                                                                        ├─ EXP-20260826-QS-SHADOWMODE-RUN5-REALFINAL-01（Phase D shadow mode Run 5、gadget layer real human final judgment、初のフルサイクル完了、inconclusive_result、sibling of RUN1/RUN2/R2-2-MAPPING/RUN3/RUN4）
                                                                        ├─ EXP-20260826-QS-SHADOWMODE-RUN6-REALHUMAN-01（Phase D shadow mode Run 6、Run5 mismatchパターンのn=2再現確認、inconclusive_result、sibling of RUN1〜RUN5）
                                                                        └─ EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01（Phase D shadow mode Run 7、hook_augmented_v1によるmismatch改善検証、inconclusive_result、sibling of RUN1〜RUN6）
                                                                             └─ EXP-20260827-FLHOOK-01（first-line hook evaluator設計・実装・replay検証、partial_improvement）
                                                                                  ├─ EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01（Phase D shadow mode Run 8、forward validation試行、inconclusive_result（closed_incomplete）、gadget教師投稿供給枯渇のため未達成）
                                                                                  └─ EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01（Phase D shadow mode Run 9、供給回復確認・forward validation再試行、inconclusive_result（closed_incomplete）、sibling of RUN8、供給依然未回復）
                                                                                       └─ EXP-20260827-GADGET-QUERY-REDESIGN-01（Phase 1 gadgetクエリ再設計、partial_improvement）
                                                                                            └─ EXP-20260827-GADGET-QUERY-REDESIGN-ROUND3-01（Round3、axis/scene語主軸、validated_improvement——新規gadget teacher候補確保）
                                                                                                 ├─ EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01（初のlive forward validation、partial_improvement——structure/hook/human 3者一致、分離は非再現）
                                                                                                 ├─ EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01（Step A非開示guard付きlive forward validation、partial_improvement——structure≠hook、hook=human再現、sibling of RUN10）
                                                                                                 └─ EXP-20260828-QS-SHADOWMODE-RUN12-FLHOOK-LIVE-GUARDED-02（別sourceでのguarded live forward validation、inconclusive_result——structure=human的中、hook=humanパターンが初めて崩れる、sibling of RUN10/RUN11）
                                                                                                      └─ EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01（opening span evaluator/hook_v2再設計、inconclusive_result——replayでRun12無改善・Run11悪化、live未実施）
                                                                                                           └─ EXP-20260828-METAGATE-DIVERGENCE-01（structure/hook divergence meta判定、partial_improvement——replayで期待した3パターン全再現、divergenceをreview priority signalとして扱う路線へ転換）
                                                                                                                └─ GOV-20260828-RUN14-PLUS-RESEARCH-POLICY-01（Run14以降の研究方針、validated_improvement——divergence meta-gate実運用価値検証を主軸に据える方針を明文化）

GOV-20260825-POSTING-OS-REDEFINITION-01（プロジェクト再定義）
  └─ GOV-20260825-OPS-RESEARCH-SPLIT-01（運用/研究ブランチ分離計画）
       └─ GOV-20260827-LEARNING-MODE-MAINLINE-SHADOW-SPLIT-01（学習モードのL1本線/L2並走研究/L3後処理資産化 再分割）
            └─ GOV-20260828-ASYNC-ENRICHMENT-REDESIGN-01（投稿時最小ログ/投稿後非同期enrichment/週次研究集計の3層構造再設計）
                 └─ GOV-20260830-POSTED-THEME-EXCLUSION-01（投稿済みテーマのmainline恒久除外、theme_signatureベースのposted-theme guard実装）
```

「EXP-20260825-QS-COMPRESSION-01→EXP-20260825-QS-NEXT-01→EXP-20260825-QS-MULTIDRAFT-01→(RUN1, RUN2, R2-2, RUN3, RUN4, RUN5, RUN6, RUN7, FLHOOK-01, RUN8, RUN9, QUERY-REDESIGN)は何の延長線上にあるか」: Gate A/B分離 → 閾値再設計 → スコア整合性修正 → teacher分布再測定 → モード間スケール比較、という一連の測定精度改善の末に発見された分解能問題への対処であり、単独の思いつきではない。**同じ分解能問題への挑戦が2回連続で失敗し（prompt/rubric側の手段が出尽くし）、3回目でアーキテクチャレベルの転換(single-draft→comparative)を試したところ、初めて差別化そのものが回復した。4回目・5回目（shadow mode Run 1・Run 2）で、実際の本番batchに対してこのアーキテクチャを運用に影響を与えずに2回連続で並走させることに成功し、real mismatchの実例をそれぞれ観測した。6回目（R2-2）で、shadow modeが露呈させたgap over-amplificationという副作用そのものに対処し、judgment（誰が1位か）を変えずに変換層だけを差し替えることで、top-1を完全に維持しながらspreadを約90%削減した（オフライン再適用）。7回目（Run 3）で、このマッピングをlive run（新規Gate A→Gate B→comparative Gate B）に適用し、gadget layerでオフラインと完全に同じ効果（gap100→7）を再現、運用ブランチの推奨とcomparative推奨が初めて一致（match）した。同時に、fashion layerではGate Aの実際の非決定性（既に安全と確認済みのパターンの再reject）によりデータが欠測し、新たな別課題として切り出された。8回目（Run 4）で、初めてhuman_judgment_mode=proxyを離れ、gadget layerでrealなhuman_initial_topを取得したところ、comparative推奨とmismatchするデータ点が観測された。しかしcomparative推奨開示後のfinal judgment取得工程がセッション内で完了せず、`closed_incomplete`として正直にクローズした——comparative結果自体は永続化されていたにもかかわらず一時的に「欠損」と誤認されかけた経緯も含め、記録の正確性を優先した判断である。9回目（Run 5）で、Run 4の再オープンではなく独立した別runとして、初めてreal human judgmentのフルサイクル（開示前初期判断→comparative_snapshot_persisted確認→開示→最終判断）を完了させた。結果、comparative推奨は人間の最終選択を変えなかった（`did_comparative_recommendation_change_human_decision=false`）が、確信度は下げた（high→medium）。comparative推奨とhuman final judgmentはinitial/finalとも一貫してmismatchし、人間側の理由（冒頭フックの強さ）がcomparative Gate Bの明示的な評価軸に含まれていない可能性が示唆された。10回目（Run 6）で、独立した別runとしてこのmismatchパターンのn=2再現確認を行い、Run5と完全に同型の結果（comparative=構造/忠実度優位、human=冒頭フック優位、confidence high→medium）を得た。11回目（Run 7）で、この仮説（hook軸の欠如が原因）を直接検証するため、comparative Gate Bに冒頭フック系4軸を追加した`hook_augmented_v1`を実装したが、hook軸を独立に評価させてもモデル自身の判断は変わらず、n=3でmismatchパターンがそのまま再現した——単純な評価軸追加では不十分であるという否定的だが有用な知見が得られた。human_judgment_modeは3run連続でrealのフルサイクルに到達し、evidenceの蓄積は進んだが、mismatchの根本原因（評価プロセスの違いか、評価軸そのものの限界か）は依然未確定である。12回目（FLHOOK-01）で、この根本原因仮説を検証するための独立判定器を設計・実装し、Run5/6/7の既存draftへのreplay検証まで完了した——hook軸を9軸評価に混ぜるのではなく、冒頭句だけを見せる独立した判定器として評価プロセスそのものを分離した結果、3/3バッチでhook_top_candidate_idがreal human judgmentと一致し、structure_hook_alignmentも3/3バッチでfalseとなる、設計文書の理想条件を満たす結果が得られた（`partial_improvement`——replay自体は成功だが、既知3ケースへの再適用に留まり、新規batchでのreal human full cycle検証がまだのため）。13回目（Run 8）で、この結果を新規batchで前向き検証しようと試みたが、gadget layerの教師投稿供給がRun1〜7の7連続ヒットから一転して枯渇し、Gate A以降の工程に進めなかった。これはfirst-line hook evaluator自体の性能とは無関係な、上流のsource探索段階の供給変動によるものであり、`inconclusive_result`（`closed_incomplete`）として正直に記録した。14回目（Run 9）で、Run8を再オープンせず独立runとして供給回復確認を再試行したが、2回目の収集試行でも未回復のままだった（Run8・Run9合わせて通算4回連続で教師投稿0件）——これも同じく`inconclusive_result`（`closed_incomplete`）として記録し、manual_review低品質候補の採用やfashion layerへの目的外切替は行わなかった。15回目（GADGET-QUERY-REDESIGN-01）で、供給枯渇の根本対策としてPhase 1のgadgetクエリ自体を再設計した。対象語単独クエリからteacher-post構造語（比較/実体験/usage_scene/comparison_axis）を含む構成へ切り替え、2ラウンドのA/Bテストを実施した結果、「比較」をAND必須語に含めると母数の小さいこの話題では即座に0件へ収束すること、axis語単独クエリは安定してヒットし候補の質もニュース/愚痴からproduct関連へ改善することを確認したが、teacher採用閾値への到達はまだ果たせていない（`partial_improvement`）。tier段階の精緻化・fashion layerのGate A非決定性調査・first-line hook evaluatorの新規batch検証（round3クエリでの供給確保待ち）も残っているため、Phase E（promotion判定）への昇格はまだ時期尚早と判断されている。**

---

## failed_experiments / partial_improvements by root_cause_family

| root_cause_family | 該当実験 |
|---|---|
| prompt_anchoring | EXP-20260825-QS-COMPRESSION-01 |
| rubric_ambiguity | EXP-20260825-QS-COMPRESSION-01（他、EXP-20260825-TEACHERBUG-01・EXP-20260825-SCALECHECK-01でも支持軸として言及、ただしこの2件はfailed_experimentではない） |
| single_draft_absolute_scoring | EXP-20260825-QS-COMPRESSION-01、EXP-20260825-QS-NEXT-01、**EXP-20260825-QS-MULTIDRAFT-01（この実験でようやく前進）** |
| score_compression | EXP-20260825-QS-COMPRESSION-01、EXP-20260825-QS-NEXT-01、EXP-20260825-QS-MULTIDRAFT-01、EXP-20260825-QS-SHADOWMODE-RUN1-01、EXP-20260826-QS-SHADOWMODE-RUN2-01、EXP-20260826-QS-MAPPING-R2-2-01（**この実験で初めてvalidated_improvementに到達**）、EXP-20260826-QS-SHADOWMODE-RUN3-01（live runで同じ効果を再現・確認）、**EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01（mapped gapは9点でn=2閾値をわずかに上回ったが異常値ではない。score_compressionそのものより、real human alignmentの検証未完了が主論点）**（他、EXP-20260825-SCALECHECK-01で発見） |
| missing_artifact | **EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01（新設）**: comparative Gate Bの結果が一時的に「欠損」と誤認されかけたが、実際にはレポート・JSONに永続化されていた。誤認と実際の欠損を区別する重要性を示した |
| reporting_inconsistency | **EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01（新設）**: human_initial_top「取得済み」という前提が会話上の実状と食い違っていた（実際には未取得のまま指示されていた）。実データを確認しないまま記録を確定させることの危険性を示した |
| human_alignment_pending | EXP-20260826-QS-SHADOWMODE-RUN4-REALHUMAN-01: gadget layer初のreal human_initial_topがcomparative推奨とmismatchしたが、final judgment未収集のため結論保留。EXP-20260826-QS-SHADOWMODE-RUN5-REALFINAL-01: フルサイクル完了後もinitial/finalとも一貫してmismatchし、`did_comparative_recommendation_change_human_decision=false`。**EXP-20260826-QS-SHADOWMODE-RUN6-REALHUMAN-01（新設）**: 独立runでn=2再現確認、Run5と完全に同型のパターン。**EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01（新設）**: hook軸追加後もn=3で再現継続 |
| evaluation_axis_gap_candidate | EXP-20260826-QS-SHADOWMODE-RUN5-REALFINAL-01: real human final judgmentの理由づけ（冒頭フックの強さ・比較軸の即時伝達）が、comparative Gate Bの明示的な9軸には含まれていない観点だった。**EXP-20260826-QS-SHADOWMODE-RUN6-REALHUMAN-01（新設）**: n=2再現によりランダムなブレではなく系統的ギャップの候補として確度が上がった |
| structure_fidelity_bias_candidate | **EXP-20260826-QS-SHADOWMODE-RUN6-REALHUMAN-01（新設）**: comparative Gate Bがstructure/fidelity系軸に一貫して偏った判断を示す候補パターンとして命名。Run7で直接検証対象になった |
| structure_fidelity_bias | **EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01（新設）**: hook軸を独立に評価させてもモデルはstructure/fidelity優位の案を支持し続けた。RUN6のcandidate段階からより確度の高い分類へ格上げ |
| hook_axis_added_but_not_effective | **EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01（新設）**: hook系4軸を追加してもcomparativeモデル自身の総合判断（hook_augmented_top_candidate_id）はlegacy軸のみの判断から変化しなかった。単純な評価軸追加では不十分という否定的知見 |
| human_stop_power_preference | **EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01（新設）**: real humanは3run連続で「タイムライン上の止まりやすさ・冒頭の切れ味」を最終判断の決め手として一貫して言及した |
| comparative_human_alignment_gap | EXP-20260826-QS-SHADOWMODE-RUN7-HOOKAXIS-01: evaluation_axis_gap_candidateがn=3で確定的パターンに近づいたことを受けた上位分類。EXP-20260827-FLHOOK-01はこの分類の直接の後継として位置づけられるが、正式なroot_cause_familyタグとしては`first_line_hook_evaluator_candidate`を新設して引き継いだ |
| first_line_hook_evaluator_candidate | **EXP-20260827-FLHOOK-01（新設）**: comparative_human_alignment_gapへの具体的対策仮説（冒頭句だけを見せる独立判定器の導入）を表す分類。実装・replay検証済みで、3/3バッチが理想条件を満たしたが、新規batchでのreal human full cycle検証はまだ行っていない |
| opening_hook_vs_structure_split | EXP-20260827-FLHOOK-01: comparative Gate B本体（structure_top_candidate_id）とfirst-line hook evaluator（hook_top_candidate_id）を意図的に分離して観測する設計方針そのものを表す分類。両者の不一致自体を観測価値のあるデータとして扱う。EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01: この分離設計を新規batchで検証しようとしたrun。教師投稿供給枯渇により未達成のまま継続root_cause_familyとして引き継がれる。EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01: 初のlive runでは分離が再現せず3者一致（`structure_hook_alignment=true`）。EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01: Step A非開示guard付きの別sourceでは分離が再現（`structure_hook_alignment=false`）、hook側がhuman final judgmentと一致。**EXP-20260828-QS-SHADOWMODE-RUN12-FLHOOK-LIVE-GUARDED-02（新設）**: さらに別sourceでも分離が再現（`structure_hook_alignment=false`）したが、今回はstructure側がhuman final judgmentと一致し、Run11とは的中方向が逆転した |
| structure_hook_alignment_case | EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01: `structure_top_candidate_id`と`hook_top_candidate_id`がsourceによって一致することも分離することもある、という観測事実そのものを表す分類。Run10=一致（true）、EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01=分離（false、hook側がhuman final judgmentと一致）。**EXP-20260828-QS-SHADOWMODE-RUN12-FLHOOK-LIVE-GUARDED-02（新設）**: Run12も分離（false）だが、structure側がhuman final judgmentと一致——n=3で「分離時にどちらが的中するか」の方向性がsource依存で一定しないことが分かった。追加live runでの条件特定が必要 |
| human_stop_power_signal_extraction | EXP-20260827-FLHOOK-01: real humanが一貫して言及する「止まりやすさ」というシグナルを、本文全体評価に埋め込むのではなく専用シグナルとして抽出する設計課題を表す分類。EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01: 同分類を継続。**EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01（新設）**: 「冒頭の切れ」「論点が早い」という初速シグナルが、live runでも一貫してhuman判断の決め手として言及された |
| forward_validation_pending | EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01: first-line hook evaluatorのreplay成功後、新規batchでの前向き検証がまだ完了していない状態を表す分類。EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01: 供給回復確認を再試行するも未回復のため、この状態が2run連続で継続している。**Round3クエリ再設計以降、EXP-20260827-QS-SHADOWMODE-RUN10-FLHOOK-LIVE-01・EXP-20260827-QS-SHADOWMODE-RUN11-FLHOOK-LIVE-GUARDED-01の2runで解消済み** |
| teacher_supply_variability | EXP-20260827-QS-SHADOWMODE-RUN8-FLHOOK-LIVE-01: Run1〜7で7連続ヒットしていたgadget先生が、Run8で初めて出現しなかったという供給側の変動パターンを表す分類。first-line hook evaluatorの性能とは独立した論点として区別する。EXP-20260827-QS-SHADOWMODE-RUN9-FLHOOK-LIVE-RETRY-01: Run9でも供給未回復が確認され、単発の変動ではなく2run連続の傾向であることが分かった。**EXP-20260827-GADGET-QUERY-REDESIGN-01（新設）**: 供給問題への対策としてクエリ再設計に着手し、候補の質的改善は確認したがteacher採用閾値にはまだ届いていない |
| query_design_over_constrained | **EXP-20260827-GADGET-QUERY-REDESIGN-01（新設）**: 「比較」等の構造語を複数の具体語とAND結合すると、母数の小さいニッチな話題ではX API recent searchが即座に0件へ収束するという設計上の制約を表す分類。round3以降のクエリ設計で回避すべきパターンとして記録 |
| opening_span_underreach | **EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01（新設）**: hook_v1の冒頭8〜20文字固定窓が比較構造・結論の着地を取りこぼしている、という当初仮説を表す分類。hook_v2（opening span evaluator）で検証したが、replayでは仮説が支持されず、この分類自体が反証寄りのデータを持つ状態になった |
| comparison_lockin_window_misalignment | **EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01（新設）**: 比較軸・結論の着地を含むようspanを拡張しても、モデルの相対評価がその情報をhuman判断に近づく方向で使わなかった（Run12）という、span拡張と評価結果のズレを表す分類 |
| hook_vs_structure_scope_design_issue | EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01: opening spanを拡張するほどhook評価がstructure評価に近づく（Run11で観測）という、評価窓の設計そのものがhookとstructureの独立性を左右するという上位の設計課題を表す分類。hook_v1の狭い窓が意図せず独立シグナルの保持に貢献していた可能性を示唆する。**EXP-20260828-METAGATE-DIVERGENCE-01（新設扱いを継続）**: この設計課題への直接の対応として、hookをstructureに勝たせようとする路線を離れ、両者のsplit自体をreview priority signalとして扱う設計へ転換した |

`final_verdict=failed_experiment`はEXP-20260825-QS-COMPRESSION-01とEXP-20260825-QS-NEXT-01の2件のみで維持している（Run7も同種の「仮説通りの改善が出なかった」結果だったが、既存指標を悪化させたわけではないため`inconclusive_result`とし、`failed_experiment`の対象を安易に広げていない）。EXP-20260825-QS-COMPRESSION-01とEXP-20260825-QS-NEXT-01は両方とも`single_draft_absolute_scoring`と`score_compression`を共有しており、この2軸が2回連続で支持されたことが、3回目のEXP-20260825-QS-MULTIDRAFT-01（architecture転換、`partial_improvement`）につながった。以降、2回のshadow mode run（`inconclusive_result`）を経て、6回目のEXP-20260826-QS-MAPPING-R2-2-01で初めて`validated_improvement`に到達し、7回目のEXP-20260826-QS-SHADOWMODE-RUN3-01でそのvalidated_improvementがlive runでも再現することを確認した（`partial_improvement`——live確認自体は前進だが、human_judgment_mode=realとfashion側データが未取得のため）。8回目・9回目（Run4・Run5）でroot_cause_familyの重心は`score_compression`から`human_alignment_pending`へ移った——スコア変換層の技術的な精度問題は概ね解決し、残る課題はcomparative Gate Bの評価軸そのものが実人間の重視点（冒頭フック等）を捉えきれているかという、より上位の設計課題に移行している。10回目・11回目（Run6・Run7）で、このgapがn=2、n=3と再現性を積み重ね、`evaluation_axis_gap_candidate`→`structure_fidelity_bias`という確度の高い分類へ、また具体的な対策（hook軸追加）の効果検証という段階へ進んだ。**root_cause_familyが一連の実験にわたって`score_compression`→`human_alignment_pending`→`structure_fidelity_bias`/`comparative_human_alignment_gap`と段階的に遷移していることが、prompt/rubric微修正からarchitecture実験、score mapping層の精緻化・live検証、real human alignment検証、そして評価軸そのものの設計改良へという方針転換を各段階で正当化する根拠になった**——これがPDCA台帳を系譜として維持する狙いそのものである。

---

## governance updates

通常の仮説検証実験（`EXP-*`）とは別に、プロジェクト全体の設計原則を更新した`GOV-*`レコードもこの台帳で管理する。

### GOV-20260825-POSTING-OS-REDEFINITION-01: プロジェクト再定義（投稿運用OS）

- **category**: `governance`
- **status**: `completed_success`
- **operational_impact**: `guardrail_added`
- **内容**: このリポジトリを「投稿運用OS」として上位再定義した。L0（入力探索）〜L6（人間意思決定）の7層構造を定義し、L3（Safety Gate）・L5（PDCA/Governance）を固定資産寄り、**L4（Comparative Quality Evaluation）を現在の主研究対象**と明記した。9件の固定資産、R1〜R6の研究対象（quality_score圧縮是正・single-draft→multi-draft移行を含む）、運用ブランチ（L0→L1→L2→L3→L6）と研究ブランチ（L2→L4→L5）の分離を文書化した
- **既存実験との関係**: 既存16件の`EXP-*`実験の事実関係は一切改ざんしていない。特にEXP-20260825-QS-COMPRESSION-01→-NEXT-01→-MULTIDRAFT-01のlineageが、R1（quality_score圧縮是正）/R2（single-draft→multi-draft移行）という研究対象定義の直接的な根拠になっている
- **追加されたguardrail**: 「L3/L5は安易に変更しない」「L4は研究対象であり本番必須条件にしすぎない」「研究ブランチの失敗は運用ブランチの投稿継続を止める理由にしない」「single_draft_absolute_scoringを主戦場として扱わない（deprecating architecture）」
- **evidence_reports**: [project_redefinition_posting_os_2026-08-25.md](project_redefinition_posting_os_2026-08-25.md) / [.json](project_redefinition_posting_os_2026-08-25.json)

### GOV-20260825-OPS-RESEARCH-SPLIT-01: 運用ブランチ／研究ブランチ分離計画（parent: GOV-20260825-POSTING-OS-REDEFINITION-01）

- **category**: `governance`
- **status**: `completed_success`
- **operational_impact**: `guardrail_added`
- **内容**: 運用ブランチ（`L0→L1→L2→L3→L6`）と研究ブランチ（`L2→L4→L5`）の責務・KPI・promotion/rollback基準を固定した。研究トラックR2-1（`EXP-20260825-QS-MULTIDRAFT-01`）をcompleted/`partial_improvement`、R2-2（tier重み付き変換）をin_progress、R2-3（human agreement logging）をnot_startedとして位置づけた。comparative Gate Bの実験ロードマップをPhase A（運用安定化、既存実績で充足）〜E（promotion判定、未着手）の5段階で明文化した
- **既存実験との関係**: Phase A/B/Cは新規実装ではなく、既存のown-post exclusion運用フローと`EXP-20260825-QS-MULTIDRAFT-01`の実績を計画のフレームへ位置づけ直したもの。**Phase D（shadow mode運用）は着手済み・2 run完了**（`EXP-20260825-QS-SHADOWMODE-RUN1-01`、`EXP-20260826-QS-SHADOWMODE-RUN2-01`）。Phase E（promotion判定）は未着手（human_judgment_modeがproxyのまま、tier重み付き変換も未実装のため）
- **追加されたguardrail**: 「運用ブランチは研究ブランチの新機能に依存しない」「投稿継続を止めるのはGate A fail/candidate shortage/source failureのときだけ」「comparative Gate Bの本番採用はpromotion criteria（partial_improvement以上・2回以上のindependent batch再現・human reviewerの優位判断・no new safety regressions）を全て満たすまでrecommendation止まり」「rollback条件のいずれかに該当したら即research-only維持に戻す」
- **evidence_reports**: [operations_research_split_plan_2026-08-25.md](operations_research_split_plan_2026-08-25.md) / [.json](operations_research_split_plan_2026-08-25.json)

### GOV-20260827-LEARNING-MODE-MAINLINE-SHADOW-SPLIT-01: 学習モードのL1/L2/L3再分割（parent: GOV-20260825-OPS-RESEARCH-SPLIT-01）

- **category**: `governance`
- **status**: `completed_success`
- **operational_impact**: `guardrail_added`
- **背景**: Run 5〜11を通じてshadow mode 1回あたりの通行料（comparative Gate B完了待ち、first-line hook evaluator完了待ち、Step A/B厳密非開示プロトコル、PDCA詳細即時更新）が積み上がり、「学ぶために回す」という当初の軽量運用から離れていた
- **内容**: `GOV-20260825-OPS-RESEARCH-SPLIT-01`が定義した運用ブランチ／研究ブランチの分離を前提として引き継ぎ、学習モード内部をさらに**L1（本線: Phase1収集→own-post exclusion→最低限のteacher/source妥当性確認→draft生成→Gate A→human final judgment→投稿候補確定）／L2（並走研究: comparative Gate B・first-line hook evaluator・tier_bounded_v1 mapping・structure/hook/human一致判定、recommendation-only）／L3（後処理資産化: PDCA詳細更新・root_cause_family集計・CLAUDE.md参照追記等、翌営業日に回してよい）**へ再分割した。run判定を`mainline_status`（`completed_mainline`/`closed_incomplete_mainline`）と`shadow_status`（`completed_shadow_optional`/`closed_incomplete_shadow`）の2軸に分離し、**`completed_mainline`と`closed_incomplete_shadow`が同時に成立してよい**ことを明記した
- **既存実験との関係**: Run 8/9のsource supply issue、Run 10のStep A contamination remediationは遡及的に再分類していない——Run 10のremediationパターン（initial側のみnull化、final側は有効データとして残す）を、この新設計におけるL2の標準運用ルールとして一般化した
- **追加されたguardrail**: 「学習モード本線はGate A survivorsとhuman final judgmentが揃えばcompleted_mainlineとしてよく、comparative Gate B/first-line hook evaluatorの完了を待たない」「shadow_status側の欠損理由（comparative_result_missing等）は本線停止理由にしない」「run記録はmainline必須項目と研究optional blockを分離して記録する」「L3はその日の投稿候補確定を止める理由にせず、翌営業日に回してよい」
- **evidence_reports**: [learning_mode_mainline_shadow_split_2026-08-27.md](learning_mode_mainline_shadow_split_2026-08-27.md) / [.json](learning_mode_mainline_shadow_split_2026-08-27.json)

### GOV-20260828-RUN14-PLUS-RESEARCH-POLICY-01: Run14以降の研究方針（parent: EXP-20260828-METAGATE-DIVERGENCE-01）

- **category**: `governance`
- **status**: `completed_success`
- **operational_impact**: `guardrail_added`
- **内容**: Run10〜13で得た知見（Run10=3者一致だがStep A汚染／Run11=hook=human／Run12=structure=human／Run13=hook_v2は改善なし・悪化）を踏まえ、学習モード本線を軽量に保ちつつ、research/shadow側では`EXP-20260828-METAGATE-DIVERGENCE-01`（structure/hook divergence meta判定）の実運用価値検証を主軸に据える方針を明文化した。Run14以降の研究優先順位（A: divergence meta-gateのlive検証、B: non-divergenceケースの安定確認、C: teacher supply安定化を本線条件と分離）、hook evaluatorの位置づけ（hook_v1維持・hook_v2保留）、guarded live実行ルール、必須記録項目、final_verdictの扱いを定義した
- **既存実験との関係**: Run10〜13の既存記録・final_verdictは遡及的に変更していない。`GOV-20260827-LEARNING-MODE-MAINLINE-SHADOW-SPLIT-01`の本線/研究分離原則をそのまま引き継ぎ、研究側の主軸をhook優劣判定からdivergence検知へ更新するもの
- **追加されたguardrail**: 「学習モード本線の完了条件は研究系の未完了を理由に止めない」「Run14以降のguarded live runはstep_a_recommendation_hidden=true必須」「hook_v2は保留のままhook_v1のみをdivergence meta-gateの入力とする」「divergence meta-gateのlive検証の成功条件はsplitを高価値レビュー対象として拾えることであり、勝敗予測ではない」「teacher supply変動はdivergence検証の進捗と混同せず別issueとして扱う」
- **evidence_reports**: [run14_plus_policy_2026-08-28.md](run14_plus_policy_2026-08-28.md) / [.json](run14_plus_policy_2026-08-28.json)

### GOV-20260828-ASYNC-ENRICHMENT-REDESIGN-01: 投稿時最小ログ/投稿後非同期enrichment/週次研究集計の3層構造再設計（parent: GOV-20260827-LEARNING-MODE-MAINLINE-SHADOW-SPLIT-01）

- **category**: `governance`
- **status**: `completed_success`
- **operational_impact**: `guardrail_added`
- **内容**: `GOV-20260827-LEARNING-MODE-MAINLINE-SHADOW-SPLIT-01`が確立した本線/研究分離をさらに一歩進め、本線ログ自体を`minimal_run_log`（投稿時必須・軽量）へ最小化し、structure/hook/divergenceの研究情報は`enrichment_record`（投稿後・非同期・best-effort）として切り離した。`mainline_status`/`enrichment_status`/`weekly_aggregation_status`/`research_followup_required`の4状態を新設し、週次研究集計（Layer 3）の雛形文書を作成した。Run10〜13・`EXP-20260828-METAGATE-DIVERGENCE-01`を新モデルへどう位置づけるかを整理し、Run13・METAGATE-DIVERGENCE-01は「投稿run」ではなく「評価器・判定ロジックの研究開発資産」であるため新モデルのいずれにも該当しないことを明示した
- **既存実験との関係**: Run10〜13の既存記録・final_verdictは遡及的に変更していない。実データの新モデルへの移行（遡及変換）は行っていない（位置づけ整理のみ）
- **追加されたguardrail**: 「投稿時に必須なのはminimal_run_logの項目のみ」「enrichmentの失敗はmainline_statusの失敗理由にしない」「detailed MD/JSON reportは必要時または週次集計時に寄せ、本線都度必須から外す」「splitはfailureではなくenrichment価値の高いイベントとして扱う」「PDCAは各runの完全記述より再利用可能な知見の集積を優先する」
- **evidence_reports**: [learning_mode_async_enrichment_design_2026-08-28.md](learning_mode_async_enrichment_design_2026-08-28.md) / [.json](learning_mode_async_enrichment_design_2026-08-28.json)、週次雛形: [weekly_learning_review_template_2026-08-28.md](weekly_learning_review_template_2026-08-28.md) / [.json](weekly_learning_review_template_2026-08-28.json)
- **実装完了（追記）**: 設計・データモデル文書化に続き、Layer1〜3すべてを実装した。`scripts/minimal_run_log.py`（`build_minimal_run_log()`/`mark_mainline_failed()`/`mark_enrichment_status()`/`save_minimal_run_log()`）、`scripts/enrichment_record.py`（`build_enrichment_record()`——`evaluate_structure_hook_divergence()`の出力を再利用、外部AI呼び出しなし）、`scripts/weekly_learning_review.py`（`aggregate_weekly_learning_review()`/`render_weekly_learning_review_markdown()`/`mark_run_weekly_aggregation_included()`——いずれもnon-blocking）、`post_generation_pipeline.py`に`finalize_minimal_run_log()`/`run_async_enrichment_experiment()`を追加。**Run10〜12を再構成したデータで初回週次集計を実施**（総run数3、`mainline_completed`=3、`structure_hook_divergence`=2件、split時のstructure的中1件・hook的中1件、contamination=1件、fallback使用率33%）。Run13/METAGATE-DIVERGENCE-01は投稿runでないため対象外として明示的に除外した。functional testでenrichment失敗・週次集計マーキング失敗のいずれも`mainline_status`/`human_selected_top`を変更しないことを確認済み。初回サンプル: [weekly_learning_review_2026-08-28_initial.md](weekly_learning_review_2026-08-28_initial.md) / [.json](weekly_learning_review_2026-08-28_initial.json)
- **実運用開始・課題発見（追記）**: 2026-08-29〜30、gadget layer限定でmainline実運用を開始し、`mainline-run-2026-08-29-001`〜`007`の計7件（Run10〜12の再構成データと合わせて計10件）が`mainline_status=completed`に到達した。うち`mainline-run-2026-08-29-001`は実投稿まで完了した。運用中、gadget teacher supplyが同一RT投稿（ATH-PRO5MK2×ジム用骨伝導×用途別使い分けテーマ）を繰り返し拾ってきたため、**すでに実投稿済みの同一テーマが`source_post_id`違いでmainlineへ複数回再生成される**という欠陥が判明した。恒久対策は`GOV-20260830-POSTED-THEME-EXCLUSION-01`を参照

### GOV-20260830-POSTED-THEME-EXCLUSION-01: 投稿済みテーマのmainline恒久除外（parent: GOV-20260828-ASYNC-ENRICHMENT-REDESIGN-01）

- **category**: `governance`
- **status**: `completed_success`
- **operational_impact**: `guardrail_added`
- **内容**: 実投稿済みテーマ（ATH-PRO5MK2×ジム用骨伝導×用途別使い分け、`mainline-run-2026-08-29-001`で実投稿済み）が、source再利用・言い換え・微差分draftとしてmainlineへ再流入する問題への恒久対策を実装した。**`source_post_id`の完全一致だけでは不十分という前提に立ち、ルールベースのキーワード抽出による`theme_signature`（product/use_case/comparison_axis/contrast/conclusionの5次元）を主キーとするposted theme registryを新設した。** `scripts/topic_dedupe.py`（theme_signature抽出）、`scripts/posted_theme_registry.py`（`check_posted_theme_guard()`——exact_source_match/high_theme_similarity/related_but_not_blocking/noneの3段階判定）を新規実装し、`scripts/minimal_run_log.py`のMinimalRunLogへguard結果を格納する9項目（すべてOptional）を追加した
- **既存実験との関係**: 既存10 completed runsの`minimal_run_log`/`enrichment_record`/週次集計ファイルは無変更（読み取りのみ）。scorer（Gate A/structure/hook/divergence）のscoringロジックは一切変更していない——「欠陥の本体はscorerではなくposted-theme exclusionの欠如だった」という診断に基づく対策
- **backfill結果**: 既存`minimal_run_log_*.json`全件を走査し、実投稿済み（`published_at`/`post_url`/`published_draft_id`が揃っている）1件（`mainline-run-2026-08-29-001`）のみを正しくregistryへ登録した。他6 runsは未投稿のため正しくスキップされた
- **検証結果**: 6項目すべて合格。(1)近縁言い換え候補（別source_post_id、draft+source本文込み）が`high_theme_similarity`（overlap_ratio=0.92）でblock、(2)同一`source_post_id`が`exact_source_match`でblock、(3)(4)非投稿の新規テーマ（fashion、AirPods Pro×会議）はmainline通過、(5)`posted_theme_check`を渡しても`mainline_status`判定ロジックは不変、(6)既存ログは無変更のまま読み込み可能
- **重要な較正結果**: candidate判定にdraft本文のみを渡すと実測overlap_ratio=0.58で閾値0.6をわずかに下回った（source本文にのみ現れるキーワードを拾えないため）。draft本文+source本文の両方を渡すとoverlap_ratio=0.92まで上昇し正しくblockされた——運用ルールとして両方を渡すことを明記した
- **追加されたguardrail**: 「実投稿済みテーマはexact_source_match/high_theme_similarityでmainlineをblockし、route_to_research=Trueで研究側へ回す」「candidate判定は必ずdraft本文+source本文の両方を渡す」「posted-theme guardの結果はログに記録するが、mainline_status判定ロジック自体は変更しない」「cooldown_active単独ではblockしない。block判定の主体はtheme_signature照合のみ」
- **evidence_reports**: [posted_theme_exclusion_design_2026-08-30.md](posted_theme_exclusion_design_2026-08-30.md) / [.json](posted_theme_exclusion_design_2026-08-30.json)、初期registry: [posted_theme_registry_2026-08-30.json](posted_theme_registry_2026-08-30.json)

### 補足: Phase D shadow mode Run 1（`EXP-20260825-QS-SHADOWMODE-RUN1-01`）

実際の新規Phase1/Phase2出力（X API real収集）から得た2候補（fashion「白T＆デニム」、gadget「イヤホン比較」、いずれも既知先生の再ヒット）でGate A pass draft 4件を生成し、comparative Gate Bをshadow modeで並走させた。**運用ブランチのfinal shipping decisionには一切介入していない。** fashion pairで実際にmismatch（運用ブランチ推奨=fashion-shadow-B、comparative推奨=fashion-shadow-A）を観測し、軸別rationaleで客観的に説明できた。n=1 runのため一般化は保留（`inconclusive_result`）。詳細: [shadow_mode_run_2026-08-25.md](shadow_mode_run_2026-08-25.md) / [.json](shadow_mode_run_2026-08-25.json)

### 補足: Phase D shadow mode Run 2（`EXP-20260826-QS-SHADOWMODE-RUN2-01`）

2本目のindependent run。sourceはRun 1と同一の既知2先生が再ヒットしたが、draft自体はRun 1と異なる新規生成文を使用し、Gate A・Gate B・comparative Gate Bを全て改めて実ライブ実行した。今回はgadget pairでmismatch（運用ブランチ推奨=gadget-shadow2-A、comparative推奨=gadget-shadow2-B）を観測。**gadget layerの推奨方向自体はRun 1・Run 2で一致**（原文により忠実・実体験文脈を明示した案が両runで優位）。gap over-amplification（0対100等）は4バッチ中3バッチで再現し、高頻度の現象であることが追加確認された。ただし今回のgadget pairは3軸が「weak」評価を含み、Run1のfashion pair（medium/strongのみ）より実質的な差が大きいことも判明——**「0対100」という数値表示は一様ではなく、軸別tier分布を見て初めて実質的な差の大きさが分かる**。`human_judgment_mode=proxy`のまま2回連続だったため、`phase_e_readiness=partially_ready`を維持。詳細: [shadow_mode_run_2026-08-26.md](shadow_mode_run_2026-08-26.md) / [.json](shadow_mode_run_2026-08-26.json)

---

## commit / push

未実施。Phase 1クエリ・Gate A・二段閾値定数・shipping decisionロジック・teacher setは本タスクで変更していない。`scripts/`本体の実装改善もこのタスクでは行っていない（既存実装済みコードをPDCA台帳として記録しただけ）。既存実験の結論は改ざんしていない。自動投稿も行っていない。
