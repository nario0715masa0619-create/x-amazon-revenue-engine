"""first-line hook evaluator（EXP-20260827-FLHOOK-01）のpure function層。

comparative Gate B本体（legacy 9軸 + hook_augmented_v1）とは完全に独立した
research-onlyの補助判定器。draft全文ではなく冒頭のopening_textだけを比較対象にする。
本文全体・構造保持・must_keep・source fidelityはこの評価器に一切見せない設計であり、
その徹底のために「opening_textを切り出す関数」をI/Oを持たないpure functionとして
ここに分離する（client層はこの関数の出力だけをAPIへ渡す）。

このモジュール単体では外部APIを呼ばない。外部AI呼び出しはexternal_audit_client.pyの
audit_first_line_hook_multidraft()が担当し、pipeline層の導線はpost_generation_pipeline.py
のrun_first_line_hook_evaluator_experiment()/run_shadow_mode_first_line_hook_evaluator()が担当する。

設計文書: ops/reports/first_line_hook_evaluator_design_2026-08-27.md
"""

from __future__ import annotations

from typing import Any

# 冒頭抽出の基本方針: 8〜20文字を基本単位とし、句読点等の区切りが範囲内にあれば
# そこで区切る（フレーズの途中で切れることを避ける）。範囲内に区切りが無ければ
# hard_capまで区切りを探し、それでも無ければmax_charsで機械的に切る。
OPENING_MIN_CHARS = 8
OPENING_MAX_CHARS = 20
OPENING_HARD_CAP = 30
_BOUNDARY_CHARS = "。、！？!?\n"


def extract_opening(
    draft_text: str,
    min_chars: int = OPENING_MIN_CHARS,
    max_chars: int = OPENING_MAX_CHARS,
    hard_cap: int = OPENING_HARD_CAP,
) -> str:
    """draft_textから、first-line hook evaluatorの評価対象となるopening_textを切り出す。

    - min_chars以上max_chars以下の範囲に句読点等の区切りがあれば、そこまでを返す
    - 範囲内に区切りが無ければ、max_charsからhard_capまでの範囲でさらに区切りを探す
    - それでも見つからなければmax_charsで機械的に切る（区切り文字は含めない）
    - draft_textがmax_chars以下ならそのまま全体を返す
    """
    text = draft_text.strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    search_end = min(len(text), max_chars)
    for i in range(min_chars, search_end):
        if text[i] in _BOUNDARY_CHARS:
            return text[: i + 1]

    extended_end = min(len(text), hard_cap)
    for i in range(search_end, extended_end):
        if text[i] in _BOUNDARY_CHARS:
            return text[: i + 1]

    return text[:max_chars]


def format_candidates_for_prompt(drafts: list[dict[str, Any]]) -> tuple[list[dict[str, str]], dict[str, str]]:
    """drafts（[{"draft_id":..., "draft_text":..., "label":...(optional)}, ...]）から、
    opening_textのみを含むprompt向けcandidatesリストと、draft_id -> opening_textの
    対応表（candidate_openings、記録用）を作る。draft_text原文はこの関数の戻り値には
    含めない（本文非開示を徹底するため）。
    """
    if len(drafts) < 2:
        raise ValueError("first-line hook evaluatorは2件以上のdraftが必要です（比較対象が無いため）")

    candidates: list[dict[str, str]] = []
    candidate_openings: dict[str, str] = {}
    for d in drafts:
        draft_id = d["draft_id"]
        opening = extract_opening(d["draft_text"])
        candidate_openings[draft_id] = opening
        entry = {"candidate_id": draft_id, "opening_text": opening}
        if d.get("label"):
            entry["label"] = d["label"]
        candidates.append(entry)
    return candidates, candidate_openings


def normalize_axis_ranking(ranking: list[str], expected_draft_ids: list[str]) -> list[str]:
    """軸ごとのrankingが期待するdraft_id集合のタイなし完全順列であることを確認して返す。
    不正な場合はValueErrorを送出する（呼び出し側でスキーマ検証と重複してもよい安全側の関数）。
    """
    expected = set(expected_draft_ids)
    if set(ranking) != expected or len(ranking) != len(expected_draft_ids):
        raise ValueError(f"rankingが不正です（タイなしの完全な順列が必要）: {ranking} != {expected_draft_ids}")
    return list(ranking)


def aggregate_overall_hook_ranking(
    axis_rankings: list[dict[str, Any]], draft_ids: list[str]
) -> list[str]:
    """複数軸のrankingから、簡易的な総合順位を集計するfallback関数。

    通常はモデル自身が返すoverall_hook_ranking（モデルが4軸+全体を踏まえて判断した順位）を
    正として使う。この関数は、モデルがoverall_hook_rankingを返さなかった場合や
    オフライン再集計が必要な場合のためのborda-count方式のfallbackとして提供する
    （numeric anchorではなく、順位の平均順位のみを使う）。
    """
    n = len(draft_ids)
    position_sum: dict[str, float] = {did: 0.0 for did in draft_ids}
    axis_count = 0
    for axis in axis_rankings:
        ranking = axis.get("ranking")
        if not ranking:
            continue
        axis_count += 1
        for pos, did in enumerate(ranking):
            if did in position_sum:
                position_sum[did] += pos
    if axis_count == 0:
        return list(draft_ids)
    avg_position = {did: position_sum[did] / axis_count for did in draft_ids}
    return sorted(draft_ids, key=lambda did: avg_position[did])


def determine_structure_hook_alignment(
    structure_top_candidate_id: str | None, hook_top_candidate_id: str | None
) -> bool | None:
    """structure系top（comparative Gate B本体）とhook系top（first-line hook evaluator）が
    一致するかを判定する。どちらかが未確定（None）の場合はNoneを返す（不一致=falseと混同しない）。
    """
    if structure_top_candidate_id is None or hook_top_candidate_id is None:
        return None
    return structure_top_candidate_id == hook_top_candidate_id


def build_alignment_summary(
    structure_top_candidate_id: str | None,
    hook_top_candidate_id: str | None,
    structure_reason_summary: str | None = None,
    hook_reason_summary: str | None = None,
) -> dict[str, Any]:
    """comparative Gate B本体とfirst-line hook evaluatorの結果を並記した比較用dictを組み立てる。
    このdictはrecommendation-onlyの記録用であり、shipping decisionには一切接続しない。
    """
    return {
        "structure_top_candidate_id": structure_top_candidate_id,
        "hook_top_candidate_id": hook_top_candidate_id,
        "structure_hook_alignment": determine_structure_hook_alignment(structure_top_candidate_id, hook_top_candidate_id),
        "structure_reason_summary": structure_reason_summary,
        "hook_reason_summary": hook_reason_summary,
    }


# ==============================================================================
# 2026-08-28 EXP-20260828-QS-SHADOWMODE-RUN13-HOOKWINDOW-REDESIGN-01。
#
# hook_v2 (opening span evaluator): hook_v1（冒頭8〜20文字固定）が、Run12で
# 「用途対比＋結論の締まり」が短い固定窓の外で立ち上がるケースを取りこぼした
# 疑いを受けて追加する研究用の再設計版。draft全体は依然として見せず、
# 「冒頭句」「比較軸が成立する位置まで」「結論/収束ニュアンスが現れる位置まで」の
# 3スパン候補から実際に評価対象とするスパンを1つ選び、選定理由とともに記録する。
# hook_v1（extract_opening/format_candidates_for_prompt）は変更しない。
# ==============================================================================
OPENING_SPAN_HARD_CAP = 80
_COMPARISON_MARKER_PATTERNS = (
    "より", "なら", "重視で", "優先なら", "は軽さ", "は音質",
)
_CONCLUSION_LANDING_KEYWORDS = (
    "が正解だった", "に落ち着いた", "に行き着いた", "気にならなくなった",
    "と感じた", "を選んだ", "にした", "まとめました", "が良かった",
    "がラクだと感じた", "使い分けている", "使い分けると",
)


def extract_first_sentence(draft_text: str, hard_cap: int = OPENING_SPAN_HARD_CAP) -> str:
    """draft_textの最初の1文（句点相当の区切りまで）を返す。区切りが無ければ
    hard_capまでで機械的に切る（draft_text自体がhard_cap以下ならそのまま返す）。"""
    text = draft_text.strip()
    if not text:
        return ""
    if len(text) <= hard_cap:
        for i, ch in enumerate(text):
            if ch in _BOUNDARY_CHARS:
                return text[: i + 1]
        return text
    for i in range(hard_cap):
        if text[i] in _BOUNDARY_CHARS:
            return text[: i + 1]
    return text[:hard_cap]


def detect_comparison_axis_span(
    draft_text: str, hard_cap: int = OPENING_SPAN_HARD_CAP
) -> tuple[bool, str | None]:
    """draft_text冒頭付近に比較軸（何と何を比べているか）が成立する位置を検出する。

    「A軸ならX、B軸ならY」のような対比マーカーが2回以上現れた場合を比較成立と見なし、
    2回目のマーカーを含む節の区切り（句読点）までをspanとして返す。検出できなければ
    (False, None)を返す（hard_gate等の安全判定ではなく、研究用ヒューリスティックである点に注意）。
    """
    text = draft_text.strip()
    if not text:
        return False, None
    search_text = text[:hard_cap]
    marker_positions = []
    for marker in _COMPARISON_MARKER_PATTERNS:
        idx = 0
        while True:
            pos = search_text.find(marker, idx)
            if pos == -1:
                break
            marker_positions.append(pos)
            idx = pos + len(marker)
    if len(marker_positions) < 2:
        return False, None
    marker_positions.sort()
    second_marker_pos = marker_positions[1]
    for i in range(second_marker_pos, min(len(text), hard_cap)):
        if text[i] in _BOUNDARY_CHARS:
            return True, text[: i + 1]
    return True, text[: min(len(text), hard_cap)]


def detect_conclusion_landing_span(
    draft_text: str, search_window: int = OPENING_SPAN_HARD_CAP
) -> tuple[bool, str | None]:
    """draft_text冒頭付近（search_window文字以内）に結論/収束ニュアンス
    （「〜が正解だった」「〜に落ち着いた」等）が現れる位置を検出する。
    見つかればその節の区切りまでをspanとして返す。検出できなければ(False, None)。
    """
    text = draft_text.strip()
    if not text:
        return False, None
    search_text = text[:search_window]
    earliest_end = None
    for kw in _CONCLUSION_LANDING_KEYWORDS:
        pos = search_text.find(kw)
        if pos == -1:
            continue
        end = pos + len(kw)
        if earliest_end is None or end < earliest_end:
            earliest_end = end
    if earliest_end is None:
        return False, None
    for i in range(earliest_end, min(len(text), search_window)):
        if text[i] in _BOUNDARY_CHARS:
            return True, text[: i + 1]
    return True, text[:earliest_end]


def select_opening_span(
    draft_text: str, hard_cap: int = OPENING_SPAN_HARD_CAP
) -> dict[str, Any]:
    """hook_v2が実際に評価対象とするopening spanを1つ選び、選定理由・検出フラグ・
    3スパン候補すべてを併記して返す（透明性のため候補も保持する）。

    選定優先順位: 結論/収束ニュアンスが検出できればそれを最優先（比較の立ち上がりから
    着地までの全体像を最も広く捉えられるため）。次に比較軸成立スパン。いずれも
    検出できなければ「冒頭1文」、それも冒頭句と変わらなければ冒頭句（hook_v1と同じ
    extract_opening）にフォールバックする。すべてhard_capで打ち切る。
    """
    opening_phrase = extract_opening(draft_text)
    first_sentence = extract_first_sentence(draft_text, hard_cap=hard_cap)
    comparison_detected, comparison_span = detect_comparison_axis_span(draft_text, hard_cap=hard_cap)
    conclusion_detected, conclusion_span = detect_conclusion_landing_span(draft_text, search_window=hard_cap)

    if conclusion_detected and conclusion_span is not None:
        effective_span = conclusion_span[:hard_cap]
        selection_reason = "conclusion_landing_span_detected"
    elif comparison_detected and comparison_span is not None:
        effective_span = comparison_span[:hard_cap]
        selection_reason = "comparison_axis_lockin_span_detected"
    elif len(first_sentence) > len(opening_phrase):
        effective_span = first_sentence[:hard_cap]
        selection_reason = "first_sentence_fallback"
    else:
        effective_span = opening_phrase
        selection_reason = "opening_phrase_fallback"

    return {
        "effective_span": effective_span,
        "selection_reason": selection_reason,
        "comparison_axis_detected": comparison_detected,
        "conclusion_landing_detected": conclusion_detected,
        "candidate_spans": {
            "opening_phrase": opening_phrase,
            "first_sentence": first_sentence,
            "comparison_axis_span": comparison_span,
            "conclusion_landing_span": conclusion_span,
        },
    }


def format_candidates_for_prompt_v2(
    drafts: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    """hook_v2用: drafts（[{"draft_id":..., "draft_text":..., "label":...(optional)}, ...]）から、
    select_opening_span()で選んだeffective_spanのみを含むprompt向けcandidatesリストと、
    draft_id -> span選定メタデータ（記録・比較用、hook_v1のcandidate_openingsに相当）を作る。
    draft_text原文はこの関数の戻り値には含めない（本文非開示を徹底するため）。
    """
    if len(drafts) < 2:
        raise ValueError("opening span evaluatorは2件以上のdraftが必要です（比較対象が無いため）")

    candidates: list[dict[str, str]] = []
    span_meta: dict[str, dict[str, Any]] = {}
    for d in drafts:
        draft_id = d["draft_id"]
        span_info = select_opening_span(d["draft_text"])
        span_meta[draft_id] = span_info
        entry = {"candidate_id": draft_id, "opening_span": span_info["effective_span"]}
        if d.get("label"):
            entry["label"] = d["label"]
        candidates.append(entry)
    return candidates, span_meta


def determine_hook_v1_vs_hook_v2_alignment(
    hook_v1_top_candidate_id: str | None, hook_v2_top_candidate_id: str | None
) -> bool | None:
    """hook_v1とhook_v2のtop candidateが一致するかを判定する。どちらかが未確定ならNone。"""
    if hook_v1_top_candidate_id is None or hook_v2_top_candidate_id is None:
        return None
    return hook_v1_top_candidate_id == hook_v2_top_candidate_id


def evaluation_result_to_dict(result: Any) -> dict[str, Any]:
    """FirstLineHookEvaluationResult（external_audit_schema.py）をJSON化しやすいdictへ変換する
    補助関数。dataclassをそのままjson.dumpできない呼び出し元向けの薄いヘルパー。
    """
    return {
        "batch_id": result.batch_id,
        "draft_ids": result.draft_ids,
        "rubric_version": result.rubric_version,
        "candidate_openings": result.candidate_openings,
        "axis_rankings": [
            {"axis_name": a.axis_name, "ranking": a.ranking, "reason": a.reason} for a in result.axis_rankings
        ],
        "axis_reasons": result.axis_reasons,
        "overall_hook_ranking": result.overall_hook_ranking,
        "hook_top_candidate_id": result.hook_top_candidate_id,
        "hook_summary_reason": result.hook_summary_reason,
        "audited_by": result.audited_by,
        "structure_top_candidate_id": result.structure_top_candidate_id,
        "structure_hook_alignment": result.structure_hook_alignment,
        "structure_reason_summary": result.structure_reason_summary,
        "hook_reason_summary": result.hook_reason_summary,
    }


# ==============================================================================
# 2026-08-28 EXP-20260828-METAGATE-DIVERGENCE-01。
#
# meta divergence判定用の補助関数。hook evaluatorを「structureに勝つ／負ける」
# 判定器として使うのではなく、structureとhookのsplitそのものを検知するための
# 入力（hook_v1内部のaxis合意度）を計算する。hook_v2は本実験の入力に採用しない
# （Run13で優位性が確認できなかったため、divergence判定はhook_v1を前提にする）。
# ==============================================================================
def compute_hook_v1_axis_consensus(
    axis_rankings: list[dict[str, Any]], hook_top_candidate_id: str | None
) -> float:
    """hook_v1の軸別ranking（[{"axis_name":..., "ranking":[...], "reason":...}, ...]）のうち、
    何割の軸が1位としてhook_top_candidate_idを選んでいるかを返す（0.0〜1.0）。

    overall_hook_ranking（モデルが総合判断した順位）はaxis単純平均ではないため、
    軸別に割れているのに総合順位だけが一方へ寄るケースがあり得る。この関数はその
    「軸内部の合意度」を可視化するための、hook_v1の出力に対する追加分析であり、
    hook_v1自体の判定ロジックは一切変更しない。
    """
    if not axis_rankings or hook_top_candidate_id is None:
        return 0.0
    agree = 0
    total = 0
    for axis in axis_rankings:
        ranking = axis.get("ranking")
        if not ranking:
            continue
        total += 1
        if ranking[0] == hook_top_candidate_id:
            agree += 1
    if total == 0:
        return 0.0
    return agree / total


def evaluation_result_v2_to_dict(result: Any) -> dict[str, Any]:
    """OpeningSpanHookEvaluationResult（hook_v2、external_audit_schema.py）を
    JSON化しやすいdictへ変換する補助関数。evaluation_result_to_dict()のhook_v2版。
    """
    return {
        "batch_id": result.batch_id,
        "draft_ids": result.draft_ids,
        "rubric_version": result.rubric_version,
        "evaluated_opening_span_by_candidate": result.evaluated_opening_span_by_candidate,
        "opening_span_selection_reason_by_candidate": result.opening_span_selection_reason_by_candidate,
        "comparison_axis_detected_by_candidate": result.comparison_axis_detected_by_candidate,
        "conclusion_landing_detected_by_candidate": result.conclusion_landing_detected_by_candidate,
        "axis_rankings": [
            {"axis_name": a.axis_name, "ranking": a.ranking, "reason": a.reason} for a in result.axis_rankings
        ],
        "axis_reasons": result.axis_reasons,
        "hook_v2_overall_ranking": result.hook_v2_overall_ranking,
        "hook_v2_top_candidate_id": result.hook_v2_top_candidate_id,
        "hook_v2_summary_reason": result.hook_v2_summary_reason,
        "audited_by": result.audited_by,
        "structure_top_candidate_id": result.structure_top_candidate_id,
        "structure_vs_hook_v2_alignment": result.structure_vs_hook_v2_alignment,
        "hook_v1_top_candidate_id": result.hook_v1_top_candidate_id,
        "hook_v1_vs_hook_v2_alignment": result.hook_v1_vs_hook_v2_alignment,
        "structure_reason_summary": result.structure_reason_summary,
        "hook_v1_reason_summary": result.hook_v1_reason_summary,
    }
