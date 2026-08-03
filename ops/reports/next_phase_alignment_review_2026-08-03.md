# next_phase_alignment_review_2026-08-03.md — 次フェーズ整合レビュー

> 対象: README.md、CLAUDE.md、`.claude/agents/`、`.claude/skills/`、`docs/roles/`、`docs/policies/`、`docs/strategy/`、`templates/`、`schemas/`、[ops/reports/cross_mode_review_2026-08-02.md](cross_mode_review_2026-08-02.md)、3本のdry runレポート
> 本レビューはレビューと提案のみ。ファイル修正・schema変更・hooks実装は行っていない。

---

## A. エグゼクティブサマリー

3モードのdry run・横断レビュー・優先3件修正（logger記述矛盾／差し戻し理由タグ／disclosure基準）を経て、リポジトリの骨格（担当分業・モード分離・レビューの閉ループ）は安定している。今回、現物を再確認した範囲では、前回修正した箇所（logger / compliance-reviewer / x-copywriter まわり）に「承認済みのみ記録する」という古い前提が残っている箇所はなく、修正は各ドキュメントに漏れなく反映されていた。README・CLAUDE.mdの上位方針とも矛盾はない。

一方で、前回の修正自体が生んだ新しいギャップを1件見つけた。`templates/review_template.md`に追加した差し戻し理由タグ（`disclosure_weak`等）は、それを永続化する場所が`ops/logs/`にもschemaにも存在しない。`ops/logs/`には`post_log.jsonl` / `experiment_log.jsonl` / `metrics_snapshots.csv`の3つしかなく、いずれのschemaにもタグを格納するフィールドがない。`performance-analyst.md`の入力もこの3ファイルのままであり、前回の修正が目的としていた「差し戻し理由の集計・分析」は、記録の置き場がない状態では実現できない。これは前回の修正の効果を完成させるための直接的な続きであり、今回見つかった中で最も優先度が高い。

軽微なズレとしては、`growth-marketer.md`の引き継ぎテーブルに、CTA境界修正時に更新し忘れた「CTA方針」という旧表記が1箇所残っていた（同ファイル内の他の箇所は「CTAの種類」に統一済み）。実害は小さいが、1行で直せるため次に触る際に一緒に直す価値がある。また、`.claude/skills/sales-playbook/SKILL.md`のチェックポイントは、新しく整備したdisclosureの強弱基準・タグ体系を直接参照しておらず、playbookとpolicy/templateの間に軽い温度差がある。

次にどこから触るべきかは明確で、①差し戻し理由タグの永続化設計、②その基盤が固まった上でのdisclosure_includedのenum化判断、の2段構えが合理的である。逆に、`campaign`/`angle`/`subtheme`の責務分離やmode_weightsの閾値定義は、3回のレビューを通じて重要性は認識されているものの、まだ実データ・実運用の蓄積が乏しく、判断を急ぐ理由がない。hooksの導入はこれらの土台（特にタグの保存先とdisclosureの型）が固まってからにするのが安全である。

---

## B. 整合レビュー結果

### 問題なし

| 対象 | 確認内容 |
|---|---|
| README.md ⇔ CLAUDE.md | 担当/モードの定義、ログの扱い、優先順位（安全→記録→効果）はいずれも一貫。矛盾なし |
| `.claude/agents/logger.md` ⇔ `docs/roles/logger.md` ⇔ `.claude/agents/affiliate-compliance-reviewer.md` | 前回修正した「承認済みのみ記録」という誤解を招く表現は、grep確認の結果すべて解消済み。3ファイルとも「レビュー提出時点でpost_id発行、状態遷移を一貫記録」で統一されている |
| `schemas/post_log.schema.json` ⇔ 3本のdry run実例 | 使用した`format`値（`single_post`/`thread`）、`status`遷移、`post_id`命名規則はすべて現行schemaと整合。矛盾なし |
| 担当とモードの混同 | 3回のdry run・過去のレビューを通じて新たな混同は見つからなかった |
| `mode-orchestrator.md` ⇔ `docs/roles/orchestrator.md`（mode_weights権限） | `current_mode.yaml`はorchestrator権限、`mode_weights.yaml`はweekly-pdca-review経由のみという分離は両ファイルで一致 |

### 軽微なズレあり

| 対象 | 見つかった内容 | 放置可否 | 修正対象候補 |
|---|---|---|---|
| `.claude/agents/growth-marketer.md`（他担当への引き継ぎ表） | 「x-copywriter \| 施策設計書一式(目的・訴求角度・**CTA方針**・想定モード)」の1行だけ旧表記が残存。同ファイルの責務・出力欄はすでに「CTAの種類」に統一済み | 実害小。次に同ファイルを触る際に直せば十分 | `.claude/agents/growth-marketer.md`（1行） |
| `.claude/skills/sales-playbook/SKILL.md`のチェックポイント | 「開示欄が本文内に明確に含まれているか」という記述はあるが、`disclosure-policy.md`の弱い/十分の基準や`review_template.md`の`disclosure_weak`/`disclosure_missing`タグへの参照がない | 実害小。playbookは人間向けの要点整理であり、詳細基準はpolicy/templateに委ねる設計自体は妥当。ただし参照リンクがあると親切 | `.claude/skills/sales-playbook/SKILL.md`（任意） |
| `templates/x_post_template.md`の「レビュー状況」欄 | 「未提出 / レビュー中 / needs_revision / approved / rejected」の5値がある一方、`schema`の`status`は`draft`/`needs_revision`/`rejected`/`approved`/`posted`/`archived`の6値。「未提出」はpost_id発行前（ログ対象外）の段階を指すためschemaに現れず、「レビュー中」が`draft`に対応する、という対応関係が暗黙的で明記されていない | 実害小。運用は3本のdry runで問題なく回っている | 任意（テンプレートに一言補足する程度で足りる） |

### 要修正

| 対象 | 見つかった内容 | 放置した場合の影響 | 修正対象候補 |
|---|---|---|---|
| 差し戻し理由タグの永続化先が存在しない | `templates/review_template.md`に追加した8種のタグ（`disclosure_missing`等）を格納するフィールドが、`schemas/`にも`ops/logs/`にも存在しない。`performance-analyst.md`の入力は`post_log.jsonl` / `metrics_snapshots.csv` / `experiment_log.jsonl`のままで、タグを分析対象にできない | 前回の修正の目的（差し戻し理由の集計・分析を可能にする）が未完成のまま放置される。レビューのたびにタグを記入しても、どこにも蓄積されず分析に使えない「書くだけのタグ」になる | 新規ログ（例: `ops/logs/review_log.jsonl` + `schemas/review_log.schema.json`）の追加、または`post_log.schema.json`への軽量フィールド追加のいずれかを検討 |

---

## C. 次期改善候補バックログ（最大7件）

### C-1. 差し戻し理由タグの永続化設計
- **なぜ必要か**: 前回追加したタグ体系を実際に分析可能にするための、直接の続き。放置すると前回の修正効果が発揮されない
- **触る想定のファイル群**: `schemas/`（新規`review_log.schema.json`、または`post_log.schema.json`拡張）、`ops/logs/`（新規ファイルの要否）、`.claude/agents/logger.md`、`.claude/agents/performance-analyst.md`
- **優先度**: High
- **今やるべきか**: **今やるべき**（設計判断のみでも先に決めておく価値が高い）

### C-2. `disclosure_included` のenum化（boolean → `none`/`weak`/`clear`等）
- **なぜ必要か**: 判定基準（弱い/十分の目安）は`disclosure-policy.md`にすでに明文化済みで、schema拡張の判断材料は揃っている
- **触る想定のファイル群**: `schemas/post_log.schema.json`、`docs/policies/disclosure-policy.md`（enum値との対応明記）、`.claude/agents/affiliate-compliance-reviewer.md`
- **優先度**: High
- **今やるべきか**: 保留でよいが、C-1の直後に着手するのが自然（判定基準は既に固まっているため着手コストは低い）

### C-3. `campaign` / `angle` / `product` / 将来の`subtheme`の責務分離
- **なぜ必要か**: 3本のdry run全てで提案されながら3回連続で保留されている。ファネル横断（集客→教育→販売）の分析ができないままでは、README/business-model.mdが掲げる「X→教育→Amazon送客→成果計測」の検証ができない
- **触る想定のファイル群**: `docs/roles/logger.md`（軽量案: campaignのprefix運用ルール化）、または`schemas/post_log.schema.json`（拡張案: 専用フィールド追加）
- **優先度**: Medium-High
- **今やるべきか**: 保留でよい。ただし「軽量運用か schema拡張か」の判断だけは次回そろそろ下すべき（4回目の先送りは避けたい）

### C-4. `cta_type` のenum化
- **なぜ必要か**: `format`と同様の表記ゆれリスクを理論上抱えるが、現状`profile_visit`/`save`/`link_click`の3種類のみで実害は出ていない
- **触る想定のファイル群**: `schemas/post_log.schema.json`
- **優先度**: Low
- **今やるべきか**: 保留でよい（CTA種類が増えてから対応で十分）

### C-5. `link_id` のダミー命名ルールの正式化
- **なぜ必要か**: 3本目のdry runで`dummy-link-e2e-XXX`という自己流の命名を使ったが、正式ルール化されていない。本番リンク運用が始まる前に決めておきたい
- **触る想定のファイル群**: `docs/roles/logger.md`または`.claude/agents/logger.md`
- **優先度**: Medium
- **今やるべきか**: 保留でよいが、本番投稿自動化に着手する前には必須

### C-6. `mode_weights.yaml` 更新の閾値定義
- **なぜ必要か**: 権限の所在（weekly-pdca-review経由のみ）は明確だが、「何件・何週間分あれば更新してよいか」の定量的な閾値がない
- **触る想定のファイル群**: `.claude/skills/weekly-pdca-review/SKILL.md`
- **優先度**: Low
- **今やるべきか**: 保留でよい（実データが数週間分溜まってから検討すれば十分）

### C-7. 軽微な用語統一（`growth-marketer.md`の「CTA方針」表記、skillsのタグ参照）
- **なぜ必要か**: Bで見つかった軽微なズレの解消。実害は小さいがコストも小さい
- **触る想定のファイル群**: `.claude/agents/growth-marketer.md`、`.claude/skills/sales-playbook/SKILL.md`
- **優先度**: Low
- **今やるべきか**: 今やってもよい（1行修正レベルで、次に何かのついでに直せば十分。単独で緊急対応する必要はない）

---

## D. hooks導入前チェックリスト

hooksは「決まったルールを機械的に強制する」ものであり、ルール自体が未確定な項目に対して先にhooksを書くと、ルール変更のたびにhooksも書き直すことになる。以下は、hooks着手前に固めておくべき前提条件のチェックリスト。

- [ ] **差し戻し理由タグの保存先（schema/ログ）が確定している** — **未確定**（C-1）。hooksで「needs_revisionなら最低1タグ必須」を検証する仕組みを作る前に、まずどこに保存するかを決める必要がある
- [ ] **`disclosure_included`の型（boolean継続 or enum化）が確定している** — **未確定**（C-2）。型を変えるたびにhooksのバリデーションロジックも変わるため、型を先に決める
- [ ] **disclosureの弱い/十分の判定基準が複数件のレビューで安定運用されている** — **未検証**。`disclosure-policy.md`に基準は明文化したが、実際に検証したのは3本目のdry runの1ケースのみ。hooksで自動チェックを組む前に、もう数件のレビューで基準がぶれないか確認したい
- [ ] **`format`のenum語彙が安定している** — **確定済み**。1本目で見つかった問題を受けて`single_post`/`thread`/`reply`/`quote`/`image_post`/`poll`に確定し、2本目・3本目でも安定して使えている。hooks化の候補として最も準備が整っている
- [ ] **`cta_type`のenum語彙が安定している** — **未確定**（C-4）。3種類のみの使用実績しかなく、hooksでenum検証を組むのは時期尚早
- [ ] **`posted`状態への遷移条件・実行者が定義されている** — **未定義**。「誰が・いつ・何を確認して`status`を`posted`に変えるか」がどのドキュメントにも書かれていない。CLAUDE.mdの方針（本番投稿自動化はまだ行わない）により緊急ではないが、hooksで状態遷移を検証する場合はここを先に決めないと`posted`のバリデーションが書けない
- [ ] **`campaign`/`angle`/`subtheme`の責務が確定している** — **未確定**（C-3）。命名規則自体が固まっていないため、hooksでの検証はまだ書けない
- [ ] **`mode_weights`更新の閾値が定義されている** — **未定義**（C-6）。hooksで自動更新のガードを作る場合、閾値がないと「いつ更新してよいか」を機械的に判定できない

**未確定なのでhooksで固めない方がよい項目**: 差し戻し理由タグの保存先、`disclosure_included`の型、`cta_type`のenum、`posted`状態への遷移条件、`campaign`/`subtheme`の責務、`mode_weights`更新閾値。
**hooks化の準備が整っている項目**: `format`のenum検証。

---

## E. 今すぐやるべき次の1手

1. **差し戻し理由タグの永続化設計を決めて反映する**（C-1）。前回の修正（差し戻し理由の構造化）の効果を完成させる直接の続きであり、今回見つかった中で唯一「要修正」に分類した論点。新規ログファイルを追加するか、`post_log.schema.json`を拡張するかの判断が必要
2. **その次に、`disclosure_included`のenum化に着手する**（C-2）。判定基準（弱い/十分の目安）はすでに`disclosure-policy.md`に明文化済みで、判断材料が揃っている。C-1の直後に着手すれば、schema変更をまとめて1回で行える

---

## 推奨ファイル名

`ops/reports/next_phase_alignment_review_2026-08-03.md`（本ファイルの実際の保存名と一致）
