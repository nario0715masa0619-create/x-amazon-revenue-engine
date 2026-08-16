# manual_review 人間確認用レビューシート（記入済み下書き）

- 対象: `outputs/x_api_phase2/manual_review.json`（Phase 2.1適用後、17件）
- 同文リツイートを1件として統合すると、実質**6件**の独立コンテンツに集約される
- **重要な位置づけ**: このシートの `genre_alignment_score` 等のスコアと `human_final_label` は
  **AIによる下書き提案**であり、最終判断ではない。[operating_policy_human_confirmation_2026-08-14.md](operating_policy_human_confirmation_2026-08-14.md)
  の「keep判定は自動採用しない」方針に従い、`human_final_label` 欄はユーザー確認前の**提案値**として記載する。
  そのまま採用せず、必ずユーザーが最終確認すること。
- URLは `post_id` から `https://x.com/i/web/status/{post_id}` 形式で構成（author_idが数値IDのみで
  ユーザー名を保持していないため、ユーザー名指定パスは構成不可）。

---

## GROUP 1

```
post_id: 2086931846655299620
url: https://x.com/i/web/status/2086931846655299620
query_source: ["40代 持ち物"]
text: 意外と盲点。男性の稼いだお金の多くは女性に流れていませんか？直接的なプレゼントやデート代だけではなく、車、服、持ち物１つ取っても、ジムに通う理由もキャリアアップの理由も最終的にはモテたいし、女性を意識していませんか？若い頃はそれもいいかもしれませんが、40代以降はお金と女性の効率を…

like_count: 31
reply_count: 5
repost_count: 0
impression_count: 433

current_classification: manual_review
classification_reasons: ['good_format_but_boundary_fit']

genre_alignment_score: low
fashion_signal: low（「服」「持ち物」は出費例の列挙として言及されるのみで、ファッション文脈ではない）
gadget_signal: low（言及なし）
intersection_strength: low
age_signal_strength: low（「40代」は一般論の導入としてのみ）
aesthetic_signal_strength: low
utility_signal_strength: low
structure_reusability: low（恋愛経済論のオピニオン構造。ジャンルの型として転用しづらい）
approach_reusability: medium（「意外と盲点。」という切り出しの逆張りフックは汎用的に学べる）
metrics_strength: medium（like31/reply5はこのバッチの中では相対的に高い）

human_final_label（AI下書き提案）: A. reject
keep_or_drop_reason: ジャンル交点が実質なく、恋愛/金銭論が主題。フック単体は汎用的だがジャンル固有の学びではない
duplication_note: 重複なし
reviewer_comment: 「意外と盲点。」の逆張り導入は、ジャンル非依存の一般的フック観察としてなら記録価値はあるが、本投稿自体を候補として残す必要はない
```

---

## GROUP 2

```
post_id: 2088401121748398502
url: https://x.com/i/web/status/2088401121748398502
query_source: ["40代 小物"]
text: フェミニンなベージュワンピースは辛口小物を足して、新鮮な表情に仕上げる！気温31℃｜8/15(土)【40代・50代の毎日コーデ】

like_count: 2
reply_count: 0
repost_count: 0
impression_count: 294

current_classification: manual_review
classification_reasons: ['good_format_but_boundary_fit']

genre_alignment_score: medium（ファッション文脈は強いが、ガジェット接点がゼロ）
fashion_signal: high（ワンピース／コーデ／小物／気温連動の着こなし提案）
gadget_signal: low（言及なし）
intersection_strength: low（服単独の話でガジェットとの接続がない）
age_signal_strength: medium（「40代・50代」を明示的に対象化）
aesthetic_signal_strength: medium（「新鮮な表情に仕上げる」は見え方改善の訴求だが辞書未一致）
utility_signal_strength: low
structure_reusability: high（「気温◯℃｜日付【40代・50代の毎日コーデ】」という定型フォーマットは再利用しやすい）
approach_reusability: medium（アイテム→ひと工夫→ベネフィットの順で分かりやすい）
metrics_strength: low（like2/impression294）

human_final_label（AI下書き提案）: B. observe
keep_or_drop_reason: ジャンル整合性・構造の型としては良質だが、ガジェット接点がなく反応も弱いため主教師候補にはまだ弱い。「毎日コーデ」形式の構造観察として保持する価値がある
duplication_note: 重複なし
reviewer_comment: 「気温◯℃｜日付」を毎回セットにするフォーマットは、季節性投稿の構造教師候補として今後の参考になる
```

---

## GROUP 3（白Tとデニム — RT版と原本版を1件に統合）

```
post_id: 2086648865634357354（原本／統合対象: 2086675242861375993 [RT版]）
url: https://x.com/i/web/status/2086648865634357354
query_source: ["40代 小物"]
text: 【白Tとデニム】を40代が「端正＆ちょうどよくカジュアル」に着るシルエット＆小物を徹底解説！｜otona MUSE

like_count: 4（原本）／ 0（RT版）
reply_count: 0
repost_count: 1（両方）
impression_count: 791（原本）／ 0（RT版）

current_classification: manual_review
classification_reasons: ['good_format_but_boundary_fit']

genre_alignment_score: medium（ファッション文脈は強いが、ガジェット接点がゼロ）
fashion_signal: high（Tシャツ／デニム／シルエット／カジュアル／小物の組み合わせ提案）
gadget_signal: low（言及なし）
intersection_strength: low
age_signal_strength: medium（「40代」を主語に明示）
aesthetic_signal_strength: medium（「端正＆ちょうどよくカジュアル」は見え方の言語化だが辞書未一致語）
utility_signal_strength: low
structure_reusability: high（アイテム2点提示→着こなし解説という「徹底解説」型フォーマット）
approach_reusability: medium
metrics_strength: low（like4/impression791。RT版は実質0で重複ノイズに近い）

human_final_label（AI下書き提案）: B. observe
keep_or_drop_reason: Group 2と同系統（otona MUSE系ファッションメディア）。ガジェット接点がなく反応も弱いため主教師候補ではないが、「アイテム2点＋徹底解説」という構造は観察価値がある
duplication_note: 同一本文がRT形式（like0/impression0, post_id 2086675242861375993）でも1件出現。反応指標は原本側を採用し、RT版は統合済みとして扱う
reviewer_comment: Group 2と合わせ、otona MUSE系アカウントの「◯◯を40代が着るコツ」定型フォーマットが複数観測される。次サイクルの構造教師候補として同系統をまとめて観察する価値がある
```

---

## GROUP 4

```
post_id: 2088574653086531870
url: https://x.com/i/web/status/2088574653086531870
query_source: ["服 ガジェット"]
text: 恋愛・車・ゴルフ・酒・タバコ・ガジェット・時計・ブランド品興味ゼロで洋服もシーンだけど、整形と肌治療には数百万平気で払えるからこわい笑

like_count: 1
reply_count: 0
repost_count: 0
impression_count: 44

current_classification: manual_review
classification_reasons: ['possible_genre_fit_but_low_specificity']

genre_alignment_score: low（「ガジェット」「時計」「洋服」は"興味がない対象"として列挙されるのみで、ファッション/ガジェットを推す文脈ではない）
fashion_signal: low
gadget_signal: low
intersection_strength: low
age_signal_strength: low（40代の明示なし）
aesthetic_signal_strength: low
utility_signal_strength: low
structure_reusability: low
approach_reusability: low〜medium（「興味ゼロ」列挙→「実は◯◯には大金を払う」という対比落差フックはジャンル非依存で汎用的）
metrics_strength: low（like1/impression44）

human_final_label（AI下書き提案）: A. reject
keep_or_drop_reason: ファッション/ガジェットは否定文脈での言及にすぎず、ジャンル整合性が実質ない
duplication_note: 重複なし
reviewer_comment: 対比落差フックのみ一般的な参考になり得るが、投稿自体を残す理由はない
```

---

## GROUP 5（演劇ジャンキー — リツイート10重複を1件に統合）

```
post_id: 2088224895742226445（代表。他9件は同一文面のリツイート重複: 2088562192027361591 / 2088488326601093216 / 2088425934387044751 / 2088413049460076980 / 2088383577109193113 / 2088352874887815592 / 2088322955965354387 / 2088279276240138299 / 2088253023839825981）
url: https://x.com/i/web/status/2088224895742226445
query_source: ["服 ガジェット"]
text: めっちゃ楽しみにしていた舞台だけど正直ぜんぜん面白くなかった買いたい服やガジェットを我慢して高いチケット買ったのにめちゃくちゃガッカリした演劇なんてもう観るのやめようかな……実は30年以上年間最低70本は観てきた演劇ジャンキーレベルに…

like_count: 0（10件とも0）
reply_count: 0
repost_count: 0〜23（個体差あり、リツイート由来のためこの数値自体は当該アカウントの拡散状況を表さない）
impression_count: 0〜4（10件中で最大4）

current_classification: manual_review
classification_reasons: ['possible_genre_fit_but_low_specificity']

genre_alignment_score: low（「服やガジェットを我慢して」は演劇チケット優先の文脈で言及されるのみ）
fashion_signal: low
gadget_signal: low
intersection_strength: low
age_signal_strength: low（40代の明示なし）
aesthetic_signal_strength: low
utility_signal_strength: low
structure_reusability: low
approach_reusability: low（期待外れの落胆語り。ジャンル固有の学びなし）
metrics_strength: low（reply/like実質ゼロ。repost数はリツイート重複による見かけ上の値で参考にならない）

human_final_label（AI下書き提案）: A. reject
keep_or_drop_reason: ジャンル交点が実質なく、反応も実質ゼロ。10件重複はPhase 1のid単位dedupがリツイートの重複本文を除去できないことによるノイズ
duplication_note: 同一本文が異なるpost_idで10件出現（リツイート拡散によるもの）。次回、本文ハッシュベースの重複除去をPhase 1に追加検討する価値あり
reviewer_comment: 件数だけ見るとmanual_reviewの過半（17件中10件）を占めており、実際のレビュー負荷を大きく見誤らせる。今後の運用ではPhase 1側でのリツイート重複対策が優先度高い
```

---

## GROUP 6（コミケ雨対策 — RT版と原本版を1件に統合）

```
post_id: 2088447735968268525（原本／統合対象: 2088457137307431121 [RT版]）
url: https://x.com/i/web/status/2088447735968268525
query_source: ["服 ガジェット"]
text: コミケのにわか雨対策は、化学繊維の服と完全防水のガジェットに限る。

like_count: 2（原本）／ 0（RT版）
reply_count: 0
repost_count: 1（両方）
impression_count: 137（原本）／ 1（RT版）

current_classification: manual_review
classification_reasons: ['possible_genre_fit_but_low_specificity']

genre_alignment_score: medium（「服」と「ガジェット」が同一文内で実用目的により明確に結び付いている、本バッチ中で唯一の真の交点投稿）
fashion_signal: medium（「化学繊維の服」という素材・機能軸での言及）
gadget_signal: medium（「完全防水のガジェット」）
intersection_strength: high（服とガジェットを同一の実用シーン（雨対策）でセットで語る構造。本バッチ中でここだけ）
age_signal_strength: low（40代の明示なし。コミケという場自体は40代限定の文脈ではない）
aesthetic_signal_strength: low
utility_signal_strength: high（防水・素材という実用機能の話）
structure_reusability: high（「状況（雨対策）→服の解決策＋ガジェットの解決策」という二段構えのテンプレートは、そのまま『40代ファッション×ガジェット』の投稿型に転用しやすい）
approach_reusability: medium
metrics_strength: low（like2/impression137。RT版は実質0で重複ノイズに近い）

human_final_label（AI下書き提案）: B. observe
keep_or_drop_reason: 40代軸が欠けるため主教師候補にはできないが、ファッション×ガジェットの「同一投稿内での実用的交点」という構造そのものは本バッチで最も参考になる。次回、年齢軸を足した類型のクエリ探索価値あり
duplication_note: 同一本文がRT形式（like0/impression1, post_id 2088457137307431121）でも1件出現。反応指標は原本側を採用
reviewer_comment: 「状況＋服の解決策＋ガジェットの解決策」というテンプレートは辞書のSUPPORTIVE_MEDIA_STYLE_KEYWORDSやDECISION_KEYWORDSにはまだ反映されていない新パターン。次回の辞書改修で「〇〇対策は、Aの服とBのガジェットに限る」的な二段構え表現を拾えるようにする余地がある（今回は指示範囲外のため未実施）
```

---

## レビュー後の集計

| 項目 | 件数 |
|---|---|
| reject（提案） | 3（Group 1, 4, 5） |
| observe（提案） | 3（Group 2, 3, 6） |
| pre_teacher_candidate_keep（提案） | 0 |
| note_only（提案） | 0（該当なし。フック単体の汎用パターンはreviewer_commentに残すに留めた） |
| 実績弱で保留になった件数 | 3（Group 2, 3, 6はいずれもmetrics_strength=low） |
| 実績は弱いが型として残した件数 | 3（同上。observe扱いで型のみ保持） |
| 明確に辞書へ追加したい語彙/パターン | 「気温◯℃｜日付」形式の季節連動コーデ投稿の定型パターン（Group 2, 3）／「状況＋服の解決策＋ガジェットの解決策」の二段構え表現（Group 6） |
| 明確にfalse positiveと判定したパターン | 「服」「ガジェット」「持ち物」等が“興味がない/我慢した”という**否定文脈**で使われるケース（Group 1, 4, 5）。現辞書は肯定/否定を区別しないため、今後の改修候補 |

## 所感（この段階での結論）

- 17件のmanual_reviewは、リツイート重複統合後は**実質6件**まで圧縮される。うち**pre_teacher_candidate_keepに値する投稿は0件**（40代×ファッション×ガジェットの交点が明確かつ構造再利用性が高いものは無かった）。
- 最も構造的に価値があったのはGroup 6（コミケ雨対策）で、ファッション×ガジェットの実用的交点という本ジャンルの核に近い型だが、40代軸が欠けており今回はobserve止まりが妥当と判断した。
- Group 1・4・5に共通する新しいfalse positiveパターン（否定文脈でのジャンル語出現）を発見した。今回のNEGATIVE_FALSE_MATCH_KEYWORDSの枠組みでは拾いきれておらず、次回の辞書改修候補として記録した（**今回は未実施**）。
- 上記の`human_final_label`はすべて**AIによる下書き提案**であり、正式な採否判断はユーザー確認後に確定する。
