# cross_mode_review_2026-08-02.md — 3モード横断レビュー

> 対象: [dryrun_2026-08-02_fashion-gadget_acquisition.md](dryrun_2026-08-02_fashion-gadget_acquisition.md)、[dryrun_2026-08-02_fashion-gadget_education.md](dryrun_2026-08-02_fashion-gadget_education.md)、[dryrun_2026-08-02_fashion-gadget_sales.md](dryrun_2026-08-02_fashion-gadget_sales.md)
> 参照: README.md、CLAUDE.md、`.claude/agents/`、`.claude/skills/`、`docs/roles/`、`docs/policies/`、`schemas/`、`templates/`
> 本レビューはレビューと提案のみ。ファイル修正・schema変更・hooks実装は行っていない。

---

## A. エグゼクティブサマリー

3モード（集客・教育・販売）のend-to-end dry runは、いずれも `researcher → marketer → copywriter → compliance-reviewer → logger` の引き継ぎを最後まで通すことができた。特に、1本目（集客）で見つかった「needs_revision後に再レビューが起動しない」という重大な欠陥は、`mode-orchestrator.md` / `x-copywriter.md` / `affiliate-compliance-reviewer.md` への修正後、2本目（教育）・3本目（販売）では期待どおりに動作した。これは設計の自己修復力を示す良い材料であり、担当分業と引き継ぎルールの骨格自体は機能していると評価できる。

モード分離についても、実際の出力に目的差が反映されていた。集客の初稿は「あるある共感」、教育の初稿は「特定商品への断定的な優劣付け」、販売の初稿は「disclosure・断定表現・根拠のない緊急性・CTA強度」という4観点にまたがる問題を意図的に含ませたが、reviewerはいずれも `docs/policies/` の該当ポリシーに基づいて正しく検出した。販売モードが最も多くの観点で差し戻されたことは、CLAUDE.mdが定める「販売モードは特に厳格」という設計意図が実際に機能していることの裏付けになっている。

一方で、今回の横断レビューで最も危険だと判断したのは **ログ運用に関するドキュメントと実際の検証済み挙動の食い違い** である。`.claude/agents/logger.md` と `docs/roles/logger.md` はいずれも、logger の責務・入力を「承認済み(approved)の投稿案」「affiliate-compliance-reviewerが承認した投稿案」とだけ記述している。しかし3本のdry run全てで、`needs_revision` や再提出中の行も `post_id` を伴ってログ化されており、これはschemaの `status` enum（`draft`/`needs_revision`/`rejected`/`approved`/`posted`/`archived`）や `ops/logs/post_log.jsonl` のサンプル行（`status: draft`）とも整合する設計意図のはずである。ドキュメントの文言だけを読んだ担当は「承認されるまでログに残さない」という誤った運用をしてしまう可能性があり、これは needs_revision発生率の分析（performance-analystが3回とも「見るべき観点」として挙げている）を含む監査性・分析性の根幹を崩しかねない。

次に危ないのは、差し戻し理由が構造化されていないことと、`disclosure_included` がboolean型で「開示はあるが弱い」を表現できないことの2点である。前者は3本のdry runを通じてperformance-analystが「needs_revision発生率と売り込み強度の関係」を分析すると繰り返し言及しているにもかかわらず、その分析を可能にする構造がテンプレートに存在しない。後者は販売モードのdry runで実際に露呈したケース（「#PR」のみの弱い開示）であり、コンプライアンス上最も重要な項目であるにもかかわらずログ上は「開示あり」としか見えない。

次に直すべきは、①loggerドキュメントの責務記述修正、②review_templateの判定理由の構造化、③disclosure_includedの拡張検討、の3点である。いずれも今回は実施せず、後続セクションで優先順位を示す。加えて、3本の試走で使った試走用ID（`p-20260802-002`〜`007`、ダミー`link_id`）は本番ログには存在しないが、実運用開始後に同じ命名規則で発行される本物のIDと見分けがつかなくなるリスクがあり、早めに命名規則を整理しておく価値がある。

総じて、担当分業・モード分離・レビュー運用という「骨格」は3モードで一貫して機能する設計になっている。詰まっているのは主にログ・スキーマ・テンプレートという「記録層」の詳細であり、これは初期骨格として妥当な状態だと判断する。

---

## B. 3モード比較表

| | 集客 (acquisition) | 教育 (education) | 販売 (sales) |
|---|---|---|---|
| 目的 | 新規接触・プロフィール遷移・興味喚起 | 理解促進・比較・失敗回避・保存価値 | 意思決定支援・購入誘導 |
| 主KPI | `impressions` / `profile_visit_rate` | `save_rate` / `reply_rate` | `ctr` / `conversion` |
| CTA type | `profile_visit` | `save` | `link_click` |
| reviewerで起きた主な論点 | 販売色の強さ・断定表現（「絶対後悔しない神アイテム」等） | 特定商品への根拠のない優劣付け（「これが一番、他は微妙」） | disclosureの弱さ・断定表現・根拠のない緊急性・CTA強度（4観点同時） |
| logger/schema観点の論点 | `format`がフリーテキストで表記ゆれ（`single`）が発生 → 後にenum化して解消 | `format: thread`が初めて使われ、enumが集客以外でも機能することを確認 | `disclosure_included`のboolean限界が露呈、`link_id`ダミー運用に正式ルールなし |
| 確認できた強み | needs_revision判定自体は的確。1本目時点では再レビュー起動が未整備 | 1本目の再レビュー起動修正が実際に機能することを確認（needs_revision→再提出→再レビュー→approved） | 最も厳格な基準で複数観点の差し戻しが同時に機能。再レビューも正しく起動 |
| 見つかった詰まり | 再レビュー起動ルール未定義／`format`未enum化／`product`にsubtheme情報を残せない | 新規の詰まりなし（前回修正の検証が主目的） | `disclosure_included`のboolean限界／`link_id`ダミー命名未定義／判定理由が非構造化 |

---

## C. 課題の分類

### 1. 全モード共通課題

#### C-1. loggerの責務記述が「承認済みのみ」を前提にしており、実際の検証済み挙動と矛盾している
- **なぜ問題か**: `.claude/agents/logger.md`（責務: 「承認済み(approved)の投稿案を`ops/logs/post_log.jsonl`に追記する」、入力: 「affiliate-compliance-reviewer が承認した投稿案」）と `docs/roles/logger.md`（入力: 「affiliate-compliance-reviewerが承認した投稿案」）は、いずれもloggerが扱うのは承認済みの投稿だけであるかのように読める。加えて `affiliate-compliance-reviewer.md` の「他担当への引き継ぎ」も `approved` の場合のみloggerへの引き継ぎを明記しており、`needs_revision`/`rejected`時にどう記録するかが書かれていない。一方、3本のdry run全てで `needs_revision` 状態の行を `post_id` 付きでログ化しており、これは`status` schemaのenumやサンプル行（`status: draft`）の設計意図とも一致する
- **放置した場合の影響**: ドキュメントの文言のみに従う担当（人間・将来の自動化どちらも）が「承認前はログに残さなくてよい」と誤解し、needs_revision発生率の分析や監査証跡が欠落する
- **修正対象候補**: `.claude/agents/logger.md`、`docs/roles/logger.md`、`.claude/agents/affiliate-compliance-reviewer.md`（いずれもドキュメントの文言修正のみ、schema変更不要）
- **優先度**: High

#### C-2. 差し戻し理由が構造化されておらず、集計・分析ができない
- **なぜ問題か**: `templates/review_template.md`の「判定理由」は自由記述のみ。3本のdry runを通じてperformance-analystが「needs_revision発生率と売り込み強度の関係」（1本目・3本目で言及）を分析すると繰り返し想定しているが、それを可能にする構造化されたカテゴリ（disclosure / exaggeration / urgency / cta_strength 等）が存在しない
- **放置した場合の影響**: ログ・レビュー件数が増えるほど、どの失敗パターンが多いかを機械的に把握できず、手作業での再分類が必要になる。PDCAの「Check」フェーズの精度が頭打ちになる
- **修正対象候補**: `templates/review_template.md`（テンプレートへのタグ欄追加のみで足り、schema変更は必須ではない）
- **優先度**: High

#### C-3. 試走・ダミーで使ったIDが、本番IDと見分けがつかない
- **なぜ問題か**: 3本のdry runで使用した`post_id`（`p-20260802-002`〜`007`）は`ops/logs/post_log.jsonl`には存在しないが、命名規則（`p-YYYYMMDD-連番`）は本番と同一。3本目で使った`link_id`（`dummy-link-e2e-XXX`）も自己流の命名でしかなく正式ルール化されていない。実運用が同じ日付で始まった場合、loggerが発行する最初の本番`post_id`が偶然この試走で使ったIDと一致し、レポートとログの内容が食い違って見える可能性がある
- **放置した場合の影響**: 将来、試走記録と本番記録の混同・誤参照が起きる。特にレポートを検索して「このpost_idの結果は」と調べた際に、本番ログと試走レポートのどちらを見ているか分からなくなるリスクがある
- **修正対象候補**: `docs/roles/logger.md` または `.claude/agents/logger.md`（試走・ダミー時のID命名規則の追記。例: 試走時は`p-99999999-連番`のような明らかに実日付と衝突しない範囲を使う、または`dummy-`プレフィックスを正式ルール化する）
- **優先度**: Medium

#### C-4. `cta_type` がenum化されておらず、`format`と扱いが非対称
- **なぜ問題か**: `format`は1本目の詰まりを受けてenum化されたが、`cta_type`は`profile_visit` / `save` / `link_click`と3種類使われている現在もフリーテキストのまま。同じ表記ゆれリスクを抱える2つのフィールドの扱いが非対称になっている
- **放置した場合の影響**: 現時点では実害なし（3種類しか使われておらず表記ゆれは発生していない）。CTA種類が増えた場合に`format`と同じ問題が起きる可能性がある
- **修正対象候補**: `schemas/post_log.schema.json`
- **優先度**: Low（実害が出るまで保留可）

### 2. モード固有課題

#### C-5.（販売モード）`disclosure_included` がboolean型で「開示はあるが弱い」を表現できない
- **なぜ問題か**: 3本目のdry runで、案F初稿は「#PR」のみの弱い開示だったが、開示テキスト自体は存在するため`disclosure_included: true`にせざるを得なかった。販売モードは3モードの中で最もdisclosureが重要（`docs/policies/disclosure-policy.md`が「販売モード時の厳格さ」を明記）にもかかわらず、その核心部分の強弱をログが表現できない
- **放置した場合の影響**: 「開示ありの投稿」を集計しても、実際に十分な開示だったかは分からない。将来、開示の質に関する規約違反リスクを定量的に追跡できない
- **修正対象候補**: `schemas/post_log.schema.json`（boolean → enum、例: `none` / `weak` / `clear`）。判定基準は`affiliate-compliance-reviewer`が担う
- **優先度**: High（販売モード限定だが、コンプライアンスに直結するため重要度は高い）

#### C-6.（集客→教育→販売の接続）`campaign` / `angle` / `product` / 将来のsubthemeの責務分離が未確定
- **なぜ問題か**: 1本目のdry runで「集客投稿がどのサブテーマ由来かを追跡できない」という問題が指摘され、`campaign`フィールドに`subtheme:`プレフィックスを付ける運用ルールが提案されたが、2本目・3本目でも採用されないまま、`campaign`は単純な試走識別名（`trial-e2e-fashion-gadget`等）としてのみ使われ続けている。`product`は3本とも`null`のまま、`angle`が実質的にサブテーマ相当の情報を担っているが、これは正式な役割分担ではなく成り行きである
- **放置した場合の影響**: 「このカテゴリのこのサブテーマは、集客では反応が良いが販売では転換しない」といったファネル横断の分析ができない。README.mdが掲げる「X → 教育 → Amazon送客 → 成果計測」というビジネスモデルの核心（`docs/strategy/business-model.md`）を定量的に検証できないまま運用が進むリスクがある
- **修正対象候補**: `docs/roles/logger.md`（`campaign`のprefix運用ルールを正式化）、または`schemas/post_log.schema.json`への軽量フィールド追加の要否検討
- **優先度**: Medium-High（3回連続で提案止まりになっている点を重く見る）

### 3. まだ保留でよい課題

#### C-7. `mode_weights.yaml`更新の具体的な閾値が未定義
- **なぜ問題か**: `mode-orchestrator.md`・`docs/roles/orchestrator.md`は「`mode_weights.yaml`の変更は`weekly-pdca-review` skillの結果としてのみ行う」という権限の所在は明確にしたが、「何件・何週間分のデータがあれば変更してよいか」という定量的な閾値は定義していない
- **放置した場合の影響**: 現時点では実データが存在しないため実害なし。ダミー数値でのweekly-pdca-review検証でも「各モード2件では更新しない」という定性的判断は正しく機能した
- **修正対象候補**: `.claude/skills/weekly-pdca-review/SKILL.md`
- **優先度**: Low（実データが数週間分溜まってから閾値を検討すれば十分）

#### C-8. レポート間の「レビュー区分」表記ゆれ（1回目/2回目 vs 初回レビュー/再レビュー）
- **なぜ問題か**: `templates/review_template.md`には「初回レビュー / 再レビュー」というフィールドがあるが、2本目のレポートは見出しで「レビュー判定（1回目）」「レビュー判定（2回目・再レビュー）」という独自表記を使い、3本目は初めてテンプレートどおり「レビュー区分: 初回レビュー」と明記した
- **放置した場合の影響**: レポート同士の記述スタイルが微妙にずれるだけで、運用ルール自体には影響しない
- **修正対象候補**: 特になし（次回以降のレポート作成時に`templates/review_template.md`の用語に合わせるという運用上の注意で足りる）
- **優先度**: Low

---

## D. 次の改修バックログ（最大5件）

### D-1. loggerドキュメントの責務記述修正
- **目的**: C-1を解消し、「承認前でもneeds_revision等はログ化する」という実際の検証済み挙動をドキュメントに正しく反映する
- **触るファイル群**: `.claude/agents/logger.md`、`docs/roles/logger.md`、`.claude/agents/affiliate-compliance-reviewer.md`
- **期待される効果**: ドキュメントと実運用の一致。needs_revision発生率分析の前提が明文化される
- **実装前に決めるべきこと**: 「いつの時点でpost_idを発行するか」（copywriterが投稿案を確定した時点か、compliance-reviewerに提出した時点か）を明確にする必要がある。3本のdry runでは実質「レビュー提出時点」で発行しているが、これも明文化されていない

### D-2. review_templateの判定理由を構造化
- **目的**: C-2を解消し、差し戻し理由の集計・分析を可能にする
- **触るファイル群**: `templates/review_template.md`（必要なら`docs/roles/compliance.md`にも軽く反映）
- **期待される効果**: performance-analystが「needs_revision発生率と売り込み強度の関係」を実際に分析できるようになる
- **実装前に決めるべきこと**: タグの語彙（`disclosure` / `exaggeration` / `urgency` / `cta_strength` / `comparison_basis` 等）を確定する。3本目のdry runで実際に使った4分類がそのまま初期セットの候補になる

### D-3. `disclosure_included` の拡張検討
- **目的**: C-5を解消し、「開示はあるが弱い」を機械的に区別できるようにする
- **触るファイル群**: `schemas/post_log.schema.json`、`docs/policies/disclosure-policy.md`（判定基準の明記）
- **期待される効果**: 販売モードのコンプライアンスリスクを定量的に追跡できる
- **実装前に決めるべきこと**: `weak`/`clear`の判定基準をaffiliate-compliance-reviewerがどう線引きするかを`disclosure-policy.md`に先に明文化する必要がある（基準なしにenumだけ増やしても判定がぶれる）

### D-4. `campaign`/`angle`/`product`/subthemeの責務整理
- **目的**: C-6を解消し、ファネル横断（集客→教育→販売）の分析を可能にする
- **触るファイル群**: `docs/roles/logger.md`（最小案: `campaign`のprefix運用ルール化）、または`schemas/post_log.schema.json`（拡張案: 専用フィールド追加）
- **期待される効果**: 「どのサブテーマが集客で強く、どのサブテーマが販売で転換するか」を横断的に分析できる。`docs/strategy/business-model.md`が掲げるファネル全体のPDCAが実際に回せるようになる
- **実装前に決めるべきこと**: 「軽量運用（campaignにprefixを付けるだけ）」と「schema拡張（専用フィールド追加）」のどちらを取るかを判断する必要がある。3回連続で保留されている経緯を踏まえ、次回は判断を先送りしないことが望ましい

### D-5. 試走/ダミー識別子の命名規則の正式化
- **目的**: C-3を解消し、試走由来のIDと本番IDの混同を防ぐ
- **触るファイル群**: `docs/roles/logger.md`または`.claude/agents/logger.md`
- **期待される効果**: 実運用開始後も、過去の試走レポートと本番ログを安全に併存させられる
- **実装前に決めるべきこと**: 試走用`post_id`の採番方法（日付を実在しない範囲にする／プレフィックスを変える等）をどちらにするか決める

---

## E. 今すぐ直すべきもの / 後回しでよいもの

### 今すぐ直すべきもの

- **D-1: loggerドキュメントの責務記述修正** — ドキュメントの文言修正のみでschema変更を伴わず、最も安く、かつC-1（今回最も危険と判断した論点）を解消できる
- **D-2: review_templateの判定理由の構造化** — テンプレートファイルの変更のみでschema変更を伴わない。performance-analystが3回のdry runで繰り返し前提にしている分析を可能にする
- **D-5: 試走/ダミー識別子の命名規則の正式化** — ドキュメントへの追記のみ。実運用開始前に決めておかないと後から遡って直しにくい

### まだ後回しでよいもの

- **D-3: `disclosure_included`の拡張** — schema変更を伴い、判定基準の先行整備も必要なため、単独では着手しない。D-1・D-2が先に片付いてから着手するのが自然
- **D-4: `campaign`/`angle`/`product`/subthemeの責務整理** — 3回連続で保留されてきた論点であり重要度は高いが、「軽量運用か schema拡張か」の判断に時間がかかるため、他の詰まりが片付いてから改めて着手する
- **C-4: `cta_type`のenum化** — 現状表記ゆれが発生しておらず、実害が出てから対応で十分
- **C-7: `mode_weights.yaml`更新の閾値定義** — 実データが数週間分溜まってから検討すれば足りる
- **C-8: レポート間の用語ゆれ** — 運用上の注意点として次回以降のレポート作成時に揃えれば十分。ファイル修正は不要

---

## 推奨ファイル名

`ops/reports/cross_mode_review_2026-08-02.md`（本ファイルの実際の保存名と一致）
