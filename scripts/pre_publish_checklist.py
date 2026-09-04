"""下書きがGate A/B/shipping decisionを通過した後、minimal_run_logへ正式記録する
前に必ず通す事前チェック（2026-09-04新設）。

背景: mainline-run-2026-09-04-010（メンズ-大人-服__おすすめ）で、下書きに実店舗名
7件を含む状態のまま記録しようとしたところ、コンプライアンス該当性確認・店舗の
営業状況確認のいずれも自動化されておらず、人間の指摘を受けて後追いで実施する
結果になった。これを構造的に防ぐため、2つの機械的チェック（コンプライアンス
該当性判定・固有名詞の事実確認フラグ）を、記録フロー（build_minimal_run_log()）の
必須の前段ステップとして追加する。

このモジュールが行うのは「判定とフラグ立て」のみ。実際のaffiliate-compliance-reviewer
レビュー実施・web検索による事実確認の実施は、フラグを見た呼び出し側（人間、または
このタスクを実行するClaudeCode自身）の責務であり、本モジュールは行わない
（自動でのweb検索は明示的にこのモジュールの責務外とする、という要件どおり）。

Gate A/thresholds/shipping decisionには一切触れない（これらの判定が終わった後段の
確認ステップとして独立に追加する）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from x_api_phase2_classify import (
    FASHION_CORE_KEYWORDS,
    GADGET_CORE_KEYWORDS,
    _GENERIC_WEAK_WORDS,
)

# ============================================================================
# チェックA: コンプライアンス該当性判定
# ============================================================================
# funnel-definition.mdの販売(sales)モード定義「具体的な商品提案と明確なCTAで、
# Amazon商品ページへの遷移と購入を後押しする」「開示を伴った商品紹介」を機械的な
# シグナルへ落とし込んだもの。CLAUDE.md実行ルール1・affiliate-compliance-reviewer.md
# が定める必須レビューゲートは販売モード投稿が対象であり、これらのシグナルが
# 無ければ現時点では該当しない（2026-09-04時点、このパイプラインはAmazon
# アフィリエイトリンク統合機能を実装していないため、通常は該当しない見込み。
# 将来リンク統合が実装された場合に備え、シグナル検出自体は用意しておく）。

AMAZON_LINK_PATTERNS = (
    r"amazon\.co\.jp",
    r"amzn\.to",
    r"amazon\.com",
)

PURCHASE_CTA_KEYWORDS = (
    "購入はこちら", "こちらから購入", "Amazonで購入", "Amazonでチェック",
    "アソシエイト", "#PR", "#ad", "商品ページ", "リンクはこちら", "チェックはこちら",
)


def check_compliance_applicability(draft_text: str) -> dict[str, Any]:
    """下書き本文にAmazon商品への言及・購入CTA・アフィリエイトリンクが含まれるかを
    機械的に判定する。該当する場合はaffiliate-compliance-reviewerレビュー必須の
    フラグを立てる（レビュー自体の自動実行は行わない）。該当しない場合も、判定結果と
    根拠を必ず返す（無評価のまま素通りさせない）。
    """
    matched_link_patterns = [
        p for p in AMAZON_LINK_PATTERNS if re.search(p, draft_text, re.IGNORECASE)
    ]
    matched_cta_keywords = [k for k in PURCHASE_CTA_KEYWORDS if k in draft_text]
    required = bool(matched_link_patterns or matched_cta_keywords)

    reasons: list[str] = []
    if matched_link_patterns:
        reasons.append(f"Amazonリンクのパターンを検出: {matched_link_patterns}")
    if matched_cta_keywords:
        reasons.append(f"購入CTAに相当するキーワードを検出: {matched_cta_keywords}")
    if not required:
        reasons.append(
            "Amazon商品への言及・購入CTA・アフィリエイトリンクは検出されなかった"
            "（funnel-definition.mdの販売モード定義に非該当と判定）"
        )

    return {
        "compliance_review_required": required,
        "reasons": reasons,
    }


# ============================================================================
# チェックB: 固有名詞の事実確認フラグ
# ============================================================================
# 「簡易な固有名詞抽出パターン」（片仮名の連続3文字以上、および英字ブランド名らしき
# トークン）で候補を検出する。既存のFASHION_CORE_KEYWORDS/GADGET_CORE_KEYWORDSは
# ジャンル判定用の一般的な話題語（例:「デニム」「白T」）であり店舗名・企業名等の
# 固有名詞そのものではないため、事実確認フラグの対象からは除外する
# （除外しないと、話題語がすべて「要事実確認」に誤検出され、本来確認すべき店舗名
# 等のシグナルが埋もれてしまうため）。

# 漢字＋片仮名混在の連続（例:「伊勢丹メンズ館」）も拾えるよう、ひらがなを含まない
# 漢字/片仮名の連続を候補としたうえで、片仮名を1文字も含まない連続（「個人的」
# 「結局全部」等の一般的な漢字熟語）は除外する（片仮名が入っていることを、
# 一般語ではなく固有名詞らしさの弱いシグナルとして使う）。
_KANJI_KATAKANA_RUN_PATTERN = re.compile(r"[一-龯ァ-ヶー・]{3,}")
_LATIN_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z&]{1,}")
_KATAKANA_CHARS = set(chr(c) for c in range(0x30A1, 0x30FB))

_GENERIC_TOPIC_TERMS = set(FASHION_CORE_KEYWORDS) | set(GADGET_CORE_KEYWORDS) | set(_GENERIC_WEAK_WORDS)
# 「チェック」「ポイント」等、この genre の下書きに頻出する一般的な片仮名語で、
# それ自体は固有名詞（店舗名・企業名等）ではないもの。事実確認フラグのノイズに
# なりやすいため個別に除外する。
_GENERIC_KATAKANA_NOUNS = {"チェック", "ポイント", "アイテム", "スタイル"}
# アパレルの一般的な品目カテゴリ名（特定の店舗・企業・製品名ではなく、服の種類を
# 指す一般名詞）。実在確認（営業状況等）が不要な語のため、固有名詞候補から除外する。
# 完全な網羅は目指さない——「簡易な固有名詞抽出パターン」という要件どおり、
# 頻出する主要な品目語を中心に列挙する（未網羅の品目語が誤って候補に残ることは
# あり得るが、実害は「人間が一目で無視できる誤検出が増える」程度に留まる）。
_GENERIC_APPAREL_CATEGORY_NOUNS = {
    "シャツ", "パンツ", "ジャケット", "コート", "ニット", "セーター", "カーディガン",
    "スニーカー", "ブーツ", "サンダル", "ローファー", "ワンピース", "スカート",
    "ベルト", "マフラー", "ストール", "キャップ", "パーカー", "ダウン", "軍パン",
    "バランス", "イメージ", "パターン",
}


def extract_proper_noun_candidates(draft_text: str) -> list[str]:
    """下書き本文から、実在の店舗名・企業名・製品名らしき固有名詞候補を抽出する
    （簡易ヒューリスティック。完全な固有名詞抽出器ではない——検出漏れ・過検出の
    双方があり得るため、あくまで「要確認フラグを立てるための一次スクリーニング」
    として使う）。
    """
    candidates: set[str] = set()
    exclude = _GENERIC_TOPIC_TERMS | _GENERIC_KATAKANA_NOUNS | _GENERIC_APPAREL_CATEGORY_NOUNS

    for m in _KANJI_KATAKANA_RUN_PATTERN.finditer(draft_text):
        token = m.group().strip("・")
        if len(token) < 3 or token in exclude:
            continue
        if not any(c in _KATAKANA_CHARS for c in token):
            continue  # 片仮名を一切含まない漢字熟語（一般語である可能性が高い）は除外
        candidates.add(token)

    for m in _LATIN_TOKEN_PATTERN.finditer(draft_text):
        token = m.group()
        if len(token) >= 2 and token not in exclude:
            candidates.add(token)

    return sorted(candidates)


def check_factual_verification_flag(draft_text: str) -> dict[str, Any]:
    """固有名詞候補が1件以上検出された場合、「事実確認（営業状況・現行性等）が
    必要」というフラグを立てる。web検索の実施自体はこの関数の責務ではない
    （呼び出し側が別途実施し、factual_verification_resultとして記録する）。
    """
    candidates = extract_proper_noun_candidates(draft_text)
    required = len(candidates) >= 1

    reasons: list[str] = []
    if required:
        reasons.append(f"固有名詞候補{len(candidates)}件を検出: {candidates}")
    else:
        reasons.append("固有名詞候補は検出されなかった")

    return {
        "factual_verification_required": required,
        "detected_proper_nouns": candidates,
        "reasons": reasons,
    }


# ============================================================================
# 統合エントリポイント
# ============================================================================


def run_pre_publish_checklist(draft_text: str) -> dict[str, Any]:
    """チェックA・チェックBをまとめて実行し、minimal_run_log記録前に必要な
    フラグ・根拠一式を返す。web検索・実際のレビュー実施は行わない（判定とフラグ
    立てのみ）。
    """
    compliance = check_compliance_applicability(draft_text)
    factual = check_factual_verification_flag(draft_text)
    return {
        "compliance_review_required": compliance["compliance_review_required"],
        "compliance_review_reasons": compliance["reasons"],
        "factual_verification_required": factual["factual_verification_required"],
        "factual_verification_detected_proper_nouns": factual["detected_proper_nouns"],
        "factual_verification_reasons": factual["reasons"],
    }


class PrePublishChecklistError(ValueError):
    pass


def validate_checklist_before_recording(
    checklist_result: dict[str, Any],
    compliance_review_result: str | None,
    factual_verification_result: str | None,
) -> None:
    """checklist_resultでフラグが立っているのに、対応する結果
    （compliance_review_result/factual_verification_result）が未記入（None・
    空文字）のまま記録しようとした場合、PrePublishChecklistErrorを送出して
    ブロックする。「フラグは立てたが確認は後回しにされたまま記録される」という、
    mainline-run-2026-09-04-010で実際に起きた見落としを構造的に防ぐための関門。
    """
    if checklist_result.get("compliance_review_required") and not compliance_review_result:
        raise PrePublishChecklistError(
            "compliance_review_required=Trueですが、compliance_review_resultが未記入です。"
            "affiliate-compliance-reviewerのレビュー結果を記録してから再度実行してください。"
        )
    if checklist_result.get("factual_verification_required") and not factual_verification_result:
        raise PrePublishChecklistError(
            "factual_verification_required=Trueですが、factual_verification_resultが未記入です。"
            "web検索等による固有名詞の事実確認結果を記録してから再度実行してください。"
        )
