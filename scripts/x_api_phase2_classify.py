"""X API Phase 2 — 候補整理・観察分類スクリプト。

Phase 1（scripts/x_api_phase1_collect.py）が出力した
outputs/x_api_phase1/merged_deduped.json を読み込み、各投稿に観察用フィールドを付与し、
reject / observe / manual_review / pre_teacher_candidate の4分類に振り分ける。

この段階でやること: 整理・一次除外・観察分類まで。
やらないこと: 最終教師の自動決定、LLMによる意味判定、埋め込み・ベクトルDB等。

分類ロジックは分かりやすいif/elseベースのヒューリスティック（キーワード観察＋反応指標）であり、
厳密な意味理解ではない。confidenceフィールドで自動分類の確信度を明示する。

追加のAPI再取得は行わない（Phase 1の出力を読むだけ）。

使い方:
    python scripts/x_api_phase2_classify.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_INPUT_PATH = _REPO_ROOT / "outputs" / "x_api_phase1" / "merged_deduped.json"
_OUTPUT_DIR = _REPO_ROOT / "outputs" / "x_api_phase2"

# --------------------------------------------------------------------------
# キーワード観察辞書（厳密判定ではなく補助。プロジェクト内で変更しやすい形にしておく）
#
# 2026-08-15改訂: account genreは「40代ファッション×ガジェット」であり、
# これは新方針ではなく既存前提への回帰（詳細:
# ops/reports/x_exploration_genre_redefinition_2026-08-15.md）。
# 旧辞書（会議/商談/仕事/書けない/出ない等）は特定の事件型に偏っており、
# 「仕事」「会議」等の広い語の単独ヒットだけでtopic_fitを誤って持ち上げていた
# （false positive: 政治小説の「政策会議」「自分の仕事をしている」等が
# pre_teacher_candidateに誤って上がった実例あり）。
# 新辞書は「40代」「ファッション」「ガジェット」を中心に据え、
# 単独語ではなく複数軸の共起でtopic_fit/structure_fitを判定する。
#
# 2026-08-15追加改訂（Phase 2.1／manual_review圧縮）: 2語クエリ運用の実行結果で
# manual_reviewが28件に肥大化し、(a) 「◯選」「コツ」「着映え」等のジャンル整合的な
# 実用・比較・選別型が過小評価されて滞留、(b) 「40代」「持ち物」等の広い語だけの
# 偶然一致ノイズ（スポーツ/恋愛/政治等の無関係投稿）も同じmanual_reviewに滞留、
# という2種の課題が判明した。これを受け、(a)を拾うためDECISION/AESTHETIC/FASHION
# キーワードとSUPPORTIVE_MEDIA_STYLE_KEYWORDSを拡張し、(b)を弾くために
# NEGATIVE_FALSE_MATCH_KEYWORDSと「広い語のみ一致（weak_generic_only）」判定を追加した。
# Phase 1クエリ・4分類フレーム・出力ファイル構造は変更していない。
# --------------------------------------------------------------------------
AGE_KEYWORDS = ["40代", "アラフォー", "大人", "年相応", "若作り", "落ち着き", "清潔感", "品がある", "品のよさ"]
FASHION_KEYWORDS = [
    "ファッション", "服", "コーデ", "ジャケット", "セットアップ", "シャツ", "パンツ",
    "革靴", "スニーカー", "メガネ", "バッグ", "財布", "時計", "ベルト", "小物",
    "持ち物", "身につける", "見た目", "垢抜け", "ダサい", "ダサくない", "似合う", "大人っぽい",
    # Phase 2.1追加: ファッションメディア/コーデ紹介文脈を拾いやすくする
    "Tシャツ", "ワイドパンツ", "着こなし", "着回し", "アクセサリー", "日傘", "キャップ",
    "サングラス", "革小物", "名刺入れ", "ポーチ", "服装",
    # Phase 2.1追加（自己検証で発見した抜け漏れの補完）: 素材/シルエット/系統語が
    # 未収録だったため、genuine な fashion media 投稿が false_keyword_overlap で
    # 誤rejectされていた（例:「白Tとデニム...シルエット＆小物」）。
    "デニム", "シルエット", "カジュアル", "モノトーン",
]
# 2026-09-01削除（GOV-20260901-ENGAGEMENT-BASED-TEACHER-01）: GADGET_KEYWORDS
# （"ガジェット"/"イヤホン"/"スマホ"等、人間が事前列挙した商品カテゴリ語辞書）を廃止した。
# 「ネタは勝ち投稿から拾う（商品カテゴリを人間が先読みしない）」という設計方針への
# 違反であり、かつteacher判定は本来エンゲージメント実測値（いいね・リポスト等）で
# 行うという方針と食い違っていたため。以下の_compute_engagement_tier()に置き換える。
#
# GADGET_CORE_KEYWORDS（三層探索方針、下記）は辞書自体を削除せず、layer_primary
# （fashion/gadget/intersectionのルーティング）用のトピック関連性シグナルとして
# 引き続き使う。2026-09-01追加（GOV-20260901-GADGET-ONLY-REUSABLE-ENGAGEMENT-GATE-01）:
# 当初は"gadget_only_but_reusable"というpre_teacher_candidateへの直接昇格パスが
# GADGET_CORE_KEYWORDSのみ（gadget_signal_strength=="high"）で判定されており、
# エンゲージメント値を一切参照しない抜け道になっていた（impression_count=0の
# ATH-PRO5MK2×骨伝導RT等が昇格し続ける実例で確認）。この抜け道は当該昇格条件へ
# obs["observed_engagement_tier"]=="qualifying"を必須条件として追加することで
# 塞いだ（詳細は_classify()内の該当箇所コメント参照）。

AESTHETIC_KEYWORDS = [
    "ダサい", "ダサくない", "大人っぽい", "清潔感", "自然", "上品", "ミニマル",
    "邪魔しない", "馴染む", "品がある",
    # Phase 2.1追加: 見え方・印象の改善シグナル
    "着映え", "素敵", "上質", "垢抜け", "こなれる", "洗練", "似合う",
    "悪目立ちしない", "浮かない", "バランスがいい",
]
UTILITY_KEYWORDS = [
    "便利", "機能性", "実用性", "軽い", "薄い", "コンパクト", "持ち歩きやすい",
    "身軽", "収納", "快適",
]
DECISION_KEYWORDS = [
    "比較", "選び方", "おすすめ", "買ってよかった", "失敗しない", "向いてる",
    "合う", "正解", "40代なら", "大人なら",
    # Phase 2.1追加: ランキング/コツ/比較形式が過小評価されるのを防ぐ
    # （「選挙」等との誤爆を避けるため、裸の「選」は入れず「◯選」は_SENTAKU_PATTERNで別途拾う）
    "ベスト", "厳選", "コツ", "着映え", "素敵に見える",
    "これで十分", "合わせやすい", "使い分け", "似合う", "大人っぽく見える",
    "40代に似合う", "40代におすすめ", "名品", "定番", "愛用品",
    # Phase 2.1追加（自己検証で発見した抜け漏れの補完）:「テク」も
    # 比較・選別・ノウハウ形式のシグナルとして扱う。
    # 「トレンド」「ランキング」はPhase 2.3でBROAD_TREND_KEYWORDSへ移設し、
    # ジャンル支持語なしでは加点しないゲート付き扱いに変更した（下記参照）。
    "テク",
]
PROMOTIONAL_KEYWORDS = [
    "PR", "提供", "クーポン", "セール", "期間限定", "無料", "購入はこちら",
    "プロフから", "楽天", "Amazon", "URL", "リンクはこちら",
]
BAIT_KEYWORDS = ["保存必須", "絶対見て", "知らないと損", "フォローして", "RTして", "バズった", "万人に見てほしい"]

# Phase 2.1新設: ファッションメディア的な持ち物紹介文脈（observe/pre_teacher_candidateへの
# 引き上げ補助材料。topic_fit/approach_valueの補助にのみ使う）
SUPPORTIVE_MEDIA_STYLE_KEYWORDS = [
    "40代が着映える", "40代・50代が素敵に見える", "小物使い", "大人コーデ",
    "持ち物を減らす", "身軽に生きる", "服に合う", "見え方が変わる",
    "印象が変わる", "垢抜ける",
]

# Phase 2.1新設: 偶然一致ノイズ（スポーツ/恋愛/政治/雑談等）を検出するための負の辞書。
# これ単独ではreject確定にしない。「ジャンル固有語(specific_genre_signal_count)が
# ゼロ」と組み合わさった場合にのみnegative_dominantとして reject 側へ倒す。
NEGATIVE_FALSE_MATCH_KEYWORDS = [
    "野球", "サッカー", "バドミントン", "試合", "阪神", "巨人",
    "恋愛", "婚活", "年収", "サラリーマン", "芸能", "政治", "選挙",
    "炎上", "投資", "株", "AIスキル", "副業", "稼ぐ", "競馬",
]

# 「◯選」「5選」等のランキング表現を正規表現で拾う（裸の「選」はDECISION_KEYWORDSに
# 入れない。「選挙」等の無関係語との誤爆を避けるため）
_SENTAKU_PATTERN = re.compile(r"[0-9０-９]+選")

# false positive抑制ルール1/2: 「40代」「持ち物」「小物」は単独では genre 適合を
# 強く見積もらない（あまりに広い語のため）。これらを除いた「specific」語彙のみの
# ヒットで specific_genre_signal_count を数える。
_GENERIC_WEAK_WORDS = {"40代", "持ち物", "小物"}
FASHION_KEYWORDS_SPECIFIC = [kw for kw in FASHION_KEYWORDS if kw not in _GENERIC_WEAK_WORDS]
AGE_KEYWORDS_SPECIFIC = [kw for kw in AGE_KEYWORDS if kw not in _GENERIC_WEAK_WORDS]

# --------------------------------------------------------------------------
# Phase 2.2新設（2026-08-15）: 否定文脈 false positive 対策。
# manual_reviewの人間確認（ops/reports/manual_review_review_2026-08-15.md）で、
# 「服」「ガジェット」等のジャンル語が"興味がない/我慢した"という否定・拒否文脈で
# 使われているだけの投稿（例:「ガジェット・時計・ブランド品興味ゼロで」「服やガジェットを
# 我慢して」）が、語の出現だけでジャンル適合シグナルとして加点されてしまう問題が判明した。
# ジャンル語の近接（{0,15}文字以内・句読点をまたがない）に否定語がある場合のみ、
# その具体的な出現箇所だけをシグナルカウントから除外する（投稿全体を一律rejectにはしない。
# 他の位置に本物のジャンル適合シグナルがあれば、それは維持されたまま評価される）。
# 「ダサくない」等の審美改善・失敗回避フレーム（NEGATION_EXCEPTIONS）は対象外とする。
# --------------------------------------------------------------------------
NEGATION_KEYWORDS = [
    "興味ない", "興味がない", "興味ゼロ", "興味なし",
    "我慢した", "我慢してる", "我慢して",
    "買わない", "買ってない", "いらない", "要らない",
    "持たない", "持ってない", "避ける", "避けたい",
    "やめた", "やめてる", "使わない", "使ってない",
    "無理", "合わない", "似合わない", "欲しくない",
    "必要ない", "手を出さない", "関心ない",
]

# 否定語を含んでいても、審美改善・失敗回避の文脈（ジャンル適合シグナルとして正しく
# 扱うべきもの）はnegation override対象から除外する。
NEGATION_EXCEPTIONS = [
    "ダサくない", "浮かない", "悪目立ちしない", "安っぽく見えない", "野暮ったくならない",
    "子どもっぽくならない", "若作りに見えない", "服装を邪魔しない", "似合わないを避ける",
    "失敗しない", "痛く見えない", "生活感が出すぎない", "安く見えない", "チープに見えない",
]

_NEGATION_GENRE_TERMS = [
    "服", "ファッション", "洋服", "コーデ", "ガジェット", "小物", "持ち物",
    "時計", "バッグ", "財布", "イヤホン", "スマホ", "アクセサリー",
]
_NEGATION_GENRE_GROUP = "(?:" + "|".join(re.escape(t) for t in _NEGATION_GENRE_TERMS) + ")"
_NEGATION_TERM_GROUP = "(?:" + "|".join(re.escape(t) for t in NEGATION_KEYWORDS) + ")"
# ジャンル語→否定語、否定語→ジャンル語の両方向を、句読点をまたがない15文字以内の
# 近接共起でのみ拾う（過剰反応防止。文全体にわたる`.*`は使わない）。
NEGATION_PATTERNS = [
    re.compile(rf"{_NEGATION_GENRE_GROUP}[^。！？\n]{{0,15}}{_NEGATION_TERM_GROUP}"),
    re.compile(rf"{_NEGATION_TERM_GROUP}[^。！？\n]{{0,15}}{_NEGATION_GENRE_GROUP}"),
]


def _detect_negation_context(text: str) -> dict[str, Any]:
    """ジャンル語が否定文脈で使われている箇所を検出する（Phase 2.2）。

    戻り値:
        has_negative_genre_context: 否定文脈の一致があるか
        matched_negative_terms: 一致した否定語（重複除去）
        matched_exception_terms: 一致したNEGATION_EXCEPTIONS（審美改善フレーム）
        override_should_apply: シグナルカウントからの除外を適用すべきか
            （= 否定文脈の一致があり、かつそれが例外フレームで説明されない）
    """
    matched_exception_terms = [ex for ex in NEGATION_EXCEPTIONS if ex in text]

    matched_negative_terms: set[str] = set()
    for pattern in NEGATION_PATTERNS:
        for m in pattern.finditer(text):
            span_text = m.group(0)
            if any(ex in span_text for ex in NEGATION_EXCEPTIONS):
                continue
            for term in NEGATION_KEYWORDS:
                if term in span_text:
                    matched_negative_terms.add(term)

    has_negative_genre_context = len(matched_negative_terms) > 0
    return {
        "has_negative_genre_context": has_negative_genre_context,
        "matched_negative_terms": sorted(matched_negative_terms),
        "matched_exception_terms": matched_exception_terms,
        "override_should_apply": has_negative_genre_context,
    }


def _mask_negated_genre_context(text: str) -> str:
    """否定文脈で使われているジャンル語の出現箇所だけを全角スペースでマスクし、
    以降のジャンル辞書カウント（fashion/gadget/age/aesthetic/utility/decision/
    supportive_media）から除外するためのテキストを返す。文字数は変えないため、
    他の位置ベース処理（is_thin_content等）には影響しない。
    NEGATION_EXCEPTIONSに該当する範囲はマスクしない（審美改善フレームを守る）。
    """
    exception_spans: list[tuple[int, int]] = []
    for ex in NEGATION_EXCEPTIONS:
        start = 0
        while True:
            idx = text.find(ex, start)
            if idx == -1:
                break
            exception_spans.append((idx, idx + len(ex)))
            start = idx + 1

    def _overlaps_exception(s: int, e: int) -> bool:
        return any(s < ex_e and e > ex_s for ex_s, ex_e in exception_spans)

    masked = list(text)
    for pattern in NEGATION_PATTERNS:
        for m in pattern.finditer(text):
            s, e = m.span()
            if _overlaps_exception(s, e):
                continue
            for i in range(s, e):
                masked[i] = "　"
    return "".join(masked)


# --------------------------------------------------------------------------
# Phase 2.3新設（2026-08-16）: トレンド系 false positive 対策。
# 「家電の売れ筋×異世界小説×pixiv話題×最新スマホ周辺×ベビー＆メンズトレンド」のような
# 雑多カテゴリ列挙・集約bot投稿が、「トレンド」「ランキング」等の広い語だけで
# observeまで持ち上がる問題が確認された（詳細: Phase 2.2報告の「検証で発見した副作用」）。
# BROAD_TREND_KEYWORDSは単独では加点せず、STRONG_GENRE_SUPPORT_KEYWORDSとの共起、
# またはTREND_EXCEPTIONSへの一致がある場合のみ有効なシグナルとして扱う。
# --------------------------------------------------------------------------
BROAD_TREND_KEYWORDS = [
    "トレンド", "売れ筋", "話題", "まとめ", "最新", "人気", "注目",
    "ランキング", "バズ", "急上昇", "一覧",
]

STRONG_GENRE_SUPPORT_KEYWORDS = [
    "40代", "アラフォー", "大人", "小物", "持ち物", "バッグ", "財布", "時計",
    "イヤホン", "メガネ", "アクセサリー", "Tシャツ", "ワイドパンツ", "コーデ",
    "着こなし", "着映え", "見え方", "似合う", "服に合う", "小物使い",
    "素敵に見える", "垢抜け", "ミニマル", "身軽", "持ち歩きやすい",
]

TREND_AGGREGATOR_KEYWORDS = [
    "売れ筋", "話題まとめ", "今が分かる", "まとめ速報", "注目まとめ", "人気まとめ",
    "総合", "一気見", "速報まとめ", "ニュースまとめ", "ランキング速報", "一覧まとめ",
    "今週の話題", "話題の記事", "今日の注目", "いま話題",
]

MULTI_CATEGORY_NOISE_KEYWORDS = [
    "家電", "異世界", "小説", "pixiv", "ベビー", "芸能", "アニメ", "漫画",
    "ゲーム", "グルメ", "旅行", "恋愛", "投資", "株", "AI", "副業",
    "スポーツ", "受験", "子育て", "医療", "ドラマ", "映画", "コスメ",
]

TREND_EXCEPTIONS = [
    "小物トレンド", "トレンド感", "小物でトレンド感", "40代トレンド", "40代に似合うトレンド",
    "服に合う", "着映え", "40代人気スナップ", "素敵に見える小物", "小物使い",
    "40代コーデ", "大人コーデ", "名品小物", "40代の持ち物",
]

# 「A×B×C」のような3セグメント以上の×連結（集約bot特有の羅列パターン）。
# 「Tシャツ×ワイドパンツ」のような単発の2語ペアリングは×が1個のみのため対象外。
_MULTI_X_SEPARATOR_PATTERN = re.compile(r"(?:[^×\n]{1,20}×){2,}[^×\n]{1,20}")


def _detect_trend_false_positive(text: str) -> dict[str, Any]:
    """トレンド系broad keywordのfalse positiveを検出する（Phase 2.3）。

    戻り値:
        has_broad_trend_signal: BROAD_TREND_KEYWORDSに一致があるか
        has_strong_genre_support: STRONG_GENRE_SUPPORT_KEYWORDSに一致があるか
        has_trend_exception: TREND_EXCEPTIONSに一致があるか（保護対象）
        has_aggregator_pattern: 集約bot/総合まとめ特有のパターンがあるか
        multi_category_noise_count: MULTI_CATEGORY_NOISE_KEYWORDSの一致数
        should_downrank_trend_signal: トレンド語の加点を無効化すべきか
            （= broad trendはあるが、genre supportもexceptionもない）
        matched_trend_exceptions: 一致したTREND_EXCEPTIONS
    """
    matched_trend_exceptions = [ex for ex in TREND_EXCEPTIONS if ex in text]
    has_trend_exception = len(matched_trend_exceptions) > 0
    has_broad_trend_signal = _count_hits(text, BROAD_TREND_KEYWORDS) > 0
    has_strong_genre_support = _count_hits(text, STRONG_GENRE_SUPPORT_KEYWORDS) > 0
    has_aggregator_pattern = (
        _count_hits(text, TREND_AGGREGATOR_KEYWORDS) > 0 or bool(_MULTI_X_SEPARATOR_PATTERN.search(text))
    )
    multi_category_noise_count = _count_hits(text, MULTI_CATEGORY_NOISE_KEYWORDS)

    should_downrank_trend_signal = (
        has_broad_trend_signal and not has_strong_genre_support and not has_trend_exception
    )

    return {
        "has_broad_trend_signal": has_broad_trend_signal,
        "has_strong_genre_support": has_strong_genre_support,
        "has_trend_exception": has_trend_exception,
        "has_aggregator_pattern": has_aggregator_pattern,
        "multi_category_noise_count": multi_category_noise_count,
        "should_downrank_trend_signal": should_downrank_trend_signal,
        "matched_trend_exceptions": matched_trend_exceptions,
    }


# 旧・事件型キーワード。削除はしないが legacy_observation_only 扱いとし、
# topic_fit / structure_fit / pre_teacher_candidate 判定には一切使わない。
OLD_EVENT_THEME_KEYWORDS_LEGACY = [
    "会議", "商談", "仕事", "書けない", "出ない", "渡した瞬間", "試し書き",
    "気まずい", "露呈", "インク", "ペン", "ホッチキス", "付箋",
]

# 創作・非対象ノイズの補助判定（小説・連載投稿をpre_teacher_candidateへ誤って
# 上げないためのfalse positive抑制）。
CREATIVE_WRITING_KEYWORDS = [
    "第1章", "第2章", "第3章", "第4章", "第5章", "小説", "物語", "創作",
    "登場人物", "連載", "プロローグ", "エピローグ",
]
_CHAPTER_PATTERN = re.compile(r"第[0-9０-９一二三四五六七八九十]+章")

# 参考: 汎用の実用・個人性・箇条書き判定用（新旧共通で使う一般語彙）
GENERAL_THEORY_KEYWORDS = ["大事なのは", "結局", "まずは", "本質は", "成功する人は"]
PERSONAL_KEYWORDS = ["今日", "自分", "私", "僕", "さっき", "たら", "だった"]

_LISTICLE_PATTERN = re.compile(r"(^|\n)\s*(・|[0-9１-９]+[.．)）])")


def _count_hits(text: str, keywords: list[str]) -> int:
    return sum(1 for kw in keywords if kw in text)


# ============================================================================
# 2026-09-01新設（GOV-20260901-ENGAGEMENT-BASED-TEACHER-01）: GADGET_KEYWORDS
# （商品カテゴリの事前列挙辞書）の代わりに、収集投稿の実測エンゲージメント値から
# 「サンプル不足で判定不能」「該当なし」「teacher候補として妥当」の3値を判定する。
# scripts/post_outcome.py（自分の投稿の勝敗判定）と同じ思想（極小サンプルを弱い実績と
# 誤判定しない）を踏襲するが、対象母集団が異なる（post_outcome.pyは自社の投稿、
# こちらは外部から収集した投稿）ため、値はimportせずこのファイル内で独立に定義する。
# 以下2定数はすべて暫定値であり、最終決定は人間が行う。変更する場合はこの2定数の
# みを書き換えればよい。
# ============================================================================

# これ未満のimpression_countは母数不足として"insufficient_data"（判定不能）とする。
# 暫定値: 50。根拠: 現行merged_deduped.json（2026-08-31収集、144件）の実測分布で
# impression_countの中央値は26、p75は134であり、50は「一定数の目に触れたと言える」
# 下限としてpost_outcome.MIN_SAMPLE_IMPRESSIONS_THRESHOLD（同じく50、
# PERFORMANCE_BAND_THRESHOLDS["low"]由来）と揃えた。この値の妥当性は要人間確認。
TEACHER_MIN_SAMPLE_IMPRESSIONS = 50

# like_count+repost_count+quote_count+bookmark_count+reply_countの合計がこれ以上で
# "qualifying"（teacher候補として妥当）とする。暫定値: 5。根拠: 同分布でエンゲージメント
# 合計のp75は3・p90は9であり、5はその中間かつ「反応が明確にある」水準として設定した。
# この閾値でシミュレーションした結果、144件中18件（12.5%）がqualifying、94件（65%）が
# insufficient_data、32件（22%）がlow（サンプルは足りるが反応が弱い）となった
# （旧GADGET_KEYWORDSベースの判定と比べて、実際に運用してみないと歩留まりの
# 妥当性は分からない。人間の確認が必要）。
TEACHER_ENGAGEMENT_QUALIFYING_THRESHOLD = 5

_ENGAGEMENT_METRIC_KEYS = ("like_count", "repost_count", "quote_count", "bookmark_count", "reply_count")


def _compute_engagement_tier(post: dict) -> str:
    """収集投稿1件の実測エンゲージメント値から"insufficient_data"/"low"/"qualifying"を
    判定する。impression_countが無い、またはTEACHER_MIN_SAMPLE_IMPRESSIONS未満の場合は
    "insufficient_data"とし、エンゲージメント合計が閾値未満の"低反応"（＝実際に見られた
    上で反応が弱かった）と区別する（極小サンプルを弱い実績と誤判定しないため）。
    """
    impression_count = post.get("impression_count")
    if impression_count is None or impression_count < TEACHER_MIN_SAMPLE_IMPRESSIONS:
        return "insufficient_data"
    engagement_total = sum(int(post.get(k) or 0) for k in _ENGAGEMENT_METRIC_KEYS)
    if engagement_total >= TEACHER_ENGAGEMENT_QUALIFYING_THRESHOLD:
        return "qualifying"
    return "low"


# --------------------------------------------------------------------------
# 三層探索方針（2026-08-16）: 「交点投稿を最優先で探す」から「ファッション/ガジェット/交点の
# 三層をそれぞれ独立に観察し、交点は見つかれば格上げするボーナス枠とする」へ切替。
# 詳細方針: ops/reports/three_layer_exploration_policy_2026-08-16.md
#
# これまでの反復探索バッチ（ops/reports/next_batch_exploration_2026-08-16.md）で、
# 「40代ファッション×ガジェット」の交点候補（fashion_gadget_intersection_detected）は
# 数バッチに渡って新規発見がゼロだった一方、ガジェット単体の良質投稿（イヤホン比較等）が
# 交点条件（topic_fit=="high"、軸3つ以上の共起）を満たせずobserve止まりになる
# 「ガジェット単体止まり」問題が繰り返し確認された。三層方針はこれを解消するための
# 探索・分類の再設計であり、既存のfalse positive対策（negation/trend/aggregator等）は
# 一切変更しない。
# --------------------------------------------------------------------------
FASHION_CORE_KEYWORDS = [
    "40代", "メンズ", "大人", "小物", "バッグ", "財布", "服", "コーデ", "着こなし",
    "着映え", "清潔感", "上質", "垢抜け", "定番", "スナップ", "デニム", "白T",
    "ワイドパンツ", "ジャケット", "鞄",
]
# false positive抑制: 「40代」「小物」等の_GENERIC_WEAK_WORDSは単独では強いシグナルと
# 見積もらない（既存のFASHION_KEYWORDS_SPECIFICと同じ考え方）。強度計算にはこちらを使う。
FASHION_CORE_KEYWORDS_SPECIFIC = [kw for kw in FASHION_CORE_KEYWORDS if kw not in _GENERIC_WEAK_WORDS]
GADGET_CORE_KEYWORDS = [
    "イヤホン", "モバイルバッテリー", "充電器", "ガジェット", "スマホ周辺", "ケーブル",
    "軽量", "完全防水", "骨伝導", "ワイヤレス", "USB-C", "充電", "持ち歩き機器",
]
# 2026-09-01改訂（GOV-20260901-GADGET-ONLY-REUSABLE-ENGAGEMENT-GATE-01）:
# GADGET_CORE_KEYWORDSの役割を「トピック関連性シグナルのみ」に明確化する。
# ＝この投稿が「40代ファッション×ガジェット」ジャンルのgadget側に該当しそうか、
# という話題適合の判定にのみ使ってよい。「この投稿をteacher候補（pre_teacher_candidate）
# に昇格させてよいか」の可否判定には使わない——昇格の可否は必ず
# obs["observed_engagement_tier"]（_compute_engagement_tier()の結果）で決まる。
# この分離により、GADGET_CORE_KEYWORDSに一致するがエンゲージメント実測が
# insufficient_data/lowの投稿（例: impression_count=0のRT）が、話題適合のみを
# 理由にteacher候補へ昇格することはない（_classify()の"gadget_only_but_reusable"
# 昇格条件を参照）。
INTERSECTION_BRIDGE_KEYWORDS = [
    "持ち歩き", "邪魔しない", "服に合う", "見た目を壊さない", "身につけやすい",
    "バッグに入る", "軽い", "疲れにくい", "街歩き", "旅行より日常", "収納しやすい",
    "ミニマル", "荷物を減らす", "日傘", "実用品", "機能性", "所有感",
]
FASHION_ONLY_SUPPORT_KEYWORDS = [
    "似合う", "大人っぽい", "上品", "品がある", "着映え", "洗練", "引き算", "定番", "スタイリング",
]
GADGET_ONLY_SUPPORT_KEYWORDS = [
    "音質", "接続", "ノイキャン", "防水", "充電持ち", "バッテリー持ち", "使いやすい", "比較", "実機", "実体験",
]
# 「A + B（+ C）」の共起で交点性を強く認めるパターン。各グループはOR、グループ間はAND。
INTERSECTION_STRONG_PATTERNS: list[list[list[str]]] = [
    [["バッグ", "鞄"], ["モバイルバッテリー", "充電器", "ケーブル"]],
    [["服", "小物", "バッグ", "コーデ"], ["イヤホン", "ガジェット"]],
    [["40代"], ["バッグ", "小物"], ["機能性", "実用品"]],
    [["着映え"], ["小物"], ["収納しやすい", "持ち歩き"]],
    [["街歩き"], ["軽い", "バッグ"], ["実用品"]],
]


def _matches_intersection_pattern(text: str) -> bool:
    return any(all(any(kw in text for kw in group) for group in pattern) for pattern in INTERSECTION_STRONG_PATTERNS)


def _strength_level(hits: int, medium_at: int = 1, high_at: int = 3) -> str:
    if hits >= high_at:
        return "high"
    if hits >= medium_at:
        return "medium"
    return "low"


_LAYER_STRENGTH_RANK = {"low": 0, "medium": 1, "high": 2}


def _compute_layer_signals(genre_text: str, age_hits: int) -> dict[str, Any]:
    """ファッション/ガジェット/交点の三層シグナルを独立に計算する（三層探索方針）。"""
    fashion_core_hits = _count_hits(genre_text, FASHION_CORE_KEYWORDS_SPECIFIC)
    fashion_support_hits = _count_hits(genre_text, FASHION_ONLY_SUPPORT_KEYWORDS)
    fashion_total = fashion_core_hits + fashion_support_hits
    fashion_signal_strength = _strength_level(fashion_total)

    gadget_core_hits = _count_hits(genre_text, GADGET_CORE_KEYWORDS)
    gadget_support_hits = _count_hits(genre_text, GADGET_ONLY_SUPPORT_KEYWORDS)
    gadget_total = gadget_core_hits + gadget_support_hits
    gadget_signal_strength = _strength_level(gadget_total)

    age_signal_strength = _strength_level(age_hits, medium_at=1, high_at=2)

    bridge_hits = _count_hits(genre_text, INTERSECTION_BRIDGE_KEYWORDS)
    pattern_match = _matches_intersection_pattern(genre_text)
    both_present = fashion_signal_strength != "low" and gadget_signal_strength != "low"
    if both_present and (pattern_match or bridge_hits >= 2):
        intersection_signal_strength = "high"
    elif both_present and bridge_hits >= 1:
        intersection_signal_strength = "medium"
    elif pattern_match:
        intersection_signal_strength = "medium"
    else:
        intersection_signal_strength = "low"

    fashion_rank = _LAYER_STRENGTH_RANK[fashion_signal_strength]
    gadget_rank = _LAYER_STRENGTH_RANK[gadget_signal_strength]

    layer_reasons: list[str] = []
    if fashion_total > 0:
        layer_reasons.append("fashion_signal_detected")
    if gadget_total > 0:
        layer_reasons.append("gadget_signal_detected")
    if intersection_signal_strength != "low":
        layer_reasons.append("intersection_signal_detected")
    if age_signal_strength != "low":
        layer_reasons.append("fashion_candidate_with_age_anchor" if fashion_rank >= gadget_rank else "gadget_candidate_with_real_use_context")
    if bridge_hits > 0 and intersection_signal_strength != "high":
        layer_reasons.append("bridge_signal_present_but_incomplete")

    if intersection_signal_strength == "high":
        layer_primary = "intersection"
        layer_secondary = "fashion" if fashion_rank >= gadget_rank else "gadget"
        layer_confidence = "high"
    elif fashion_rank == 0 and gadget_rank == 0:
        layer_primary = "unclear"
        layer_secondary = "none"
        layer_confidence = "low"
    elif fashion_rank > gadget_rank:
        layer_primary = "fashion"
        layer_secondary = "intersection" if intersection_signal_strength != "low" else ("gadget" if gadget_rank > 0 else "none")
        layer_confidence = fashion_signal_strength
    elif gadget_rank > fashion_rank:
        layer_primary = "gadget"
        layer_secondary = "intersection" if intersection_signal_strength != "low" else ("fashion" if fashion_rank > 0 else "none")
        layer_confidence = gadget_signal_strength
    else:
        # fashion_rank == gadget_rank > 0（同点）。アカウント軸がファッション先頭のためfashionを優先。
        layer_primary = "fashion"
        layer_secondary = "gadget"
        layer_confidence = fashion_signal_strength

    return {
        "fashion_signal_strength": fashion_signal_strength,
        "gadget_signal_strength": gadget_signal_strength,
        "intersection_signal_strength": intersection_signal_strength,
        "age_signal_strength": age_signal_strength,
        "layer_primary": layer_primary,
        "layer_secondary": layer_secondary,
        "layer_confidence": layer_confidence,
        "layer_reasons": layer_reasons,
    }


def _load_input() -> list[dict]:
    if not _INPUT_PATH.exists():
        print(f"エラー: 入力ファイルが見つかりません: {_INPUT_PATH}", file=sys.stderr)
        print("先に scripts/x_api_phase1_collect.py を実行してください。", file=sys.stderr)
        sys.exit(1)
    return json.loads(_INPUT_PATH.read_text(encoding="utf-8"))


def _observe(post: dict) -> dict[str, Any]:
    """1投稿を観察し、observed_*フィールドを返す（40代ファッション×ガジェット前提のヒューリスティック）。"""
    text = post.get("text") or ""
    # Phase 2.2: 否定文脈（「ガジェット...興味ゼロ」等）で使われているジャンル語だけを
    # マスクしたテキスト。ジャンル辞書のカウントにのみ使い、文字数ベースの判定
    # （is_thin_content等）や宣伝/煽り/個人性等の判定には元のtextを使う。
    genre_text = _mask_negated_genre_context(text)

    age_hits = _count_hits(genre_text, AGE_KEYWORDS)
    fashion_hits = _count_hits(genre_text, FASHION_KEYWORDS)
    # 2026-09-01変更: GADGET_KEYWORDS（キーワード共起）ではなく、実測エンゲージメント値
    # （_compute_engagement_tier()）でgadget軸の充足を判定する。
    engagement_tier = _compute_engagement_tier(post)
    gadget_hits = 1 if engagement_tier == "qualifying" else 0
    aesthetic_hits = _count_hits(genre_text, AESTHETIC_KEYWORDS)
    utility_hits = _count_hits(genre_text, UTILITY_KEYWORDS)
    # Phase 2.3: BROAD_TREND_KEYWORDS（トレンド/ランキング等）は単独では加点せず、
    # STRONG_GENRE_SUPPORT_KEYWORDSとの共起かTREND_EXCEPTIONS該当がある場合のみ、
    # decision_hits相当のシグナルとして加算する（集約bot投稿の誤加点を防ぐ）。
    trend_ctx = _detect_trend_false_positive(genre_text)
    effective_trend_hits = (
        0 if trend_ctx["should_downrank_trend_signal"] else _count_hits(genre_text, BROAD_TREND_KEYWORDS)
    )
    decision_hits = _count_hits(genre_text, DECISION_KEYWORDS) + effective_trend_hits
    aggregator_dominant = (
        trend_ctx["has_aggregator_pattern"] or trend_ctx["multi_category_noise_count"] >= 3
    ) and not trend_ctx["has_trend_exception"]
    promo_hits = _count_hits(text, PROMOTIONAL_KEYWORDS)
    bait_hits = _count_hits(text, BAIT_KEYWORDS)
    theory_hits = _count_hits(text, GENERAL_THEORY_KEYWORDS)
    personal_hits = _count_hits(text, PERSONAL_KEYWORDS)
    creative_writing_hits = _count_hits(text, CREATIVE_WRITING_KEYWORDS) + (
        1 if _CHAPTER_PATTERN.search(text) else 0
    )

    def level(hits: int, medium_at: int = 1, high_at: int = 2) -> str:
        if hits >= high_at:
            return "high"
        if hits >= medium_at:
            return "medium"
        return "low"

    promotionalness = level(promo_hits)
    engagement_bait = "high" if bait_hits > 0 else "low"
    usefulness = level(decision_hits + (1 if utility_hits > 0 else 0))
    personalness = level(personal_hits, medium_at=1, high_at=2)
    is_likely_creative_writing = creative_writing_hits > 0

    # specificity: 文字数と数字・固有名詞らしさの粗い代理指標
    has_digit = bool(re.search(r"\d", text))
    specificity = "high" if (len(text) >= 40 and has_digit) else ("medium" if len(text) >= 20 else "low")

    # 極端に短い、または実質URLのみの投稿は observed_manual_review_reason 以前に
    # topic_fit/structure_fitを持ち上げない（false positive抑制ルール4）。
    text_without_url = re.sub(r"https?://\S+", "", text).strip()
    is_thin_content = len(text_without_url) < 8

    has_age = age_hits > 0
    has_fashion = fashion_hits > 0
    has_gadget = gadget_hits > 0
    has_aesthetic = aesthetic_hits > 0
    has_utility = utility_hits > 0

    # Phase 2.1: false positive抑制ルール1/2/3/4
    # 「40代」「持ち物」「小物」等の広い語のみのヒット（specific_genre_signal_countが0）は
    # genre適合を強く見積もらない。さらに、それがスポーツ/恋愛/政治等の話題と併存する場合は
    # 偶然一致ノイズ（negative_dominant）として扱う。
    supportive_media_hits = _count_hits(genre_text, SUPPORTIVE_MEDIA_STYLE_KEYWORDS)
    negative_hits = _count_hits(text, NEGATIVE_FALSE_MATCH_KEYWORDS)
    negation_ctx = _detect_negation_context(text)
    specific_genre_signal_count = (
        _count_hits(genre_text, FASHION_KEYWORDS_SPECIFIC)
        + _count_hits(genre_text, AGE_KEYWORDS_SPECIFIC)
        + gadget_hits
        + aesthetic_hits
        + utility_hits
        + decision_hits
        + supportive_media_hits
    )
    weak_generic_only = specific_genre_signal_count == 0 and (has_age or has_fashion)
    negative_dominant = negative_hits >= 2 and specific_genre_signal_count == 0

    # topic_fit: 単独語ヒットでは上げず、複数軸の共起を必須にする（false positive抑制ルール2/6）
    topic_pairs_hit = sum(
        [
            has_age and has_fashion,
            has_fashion and has_gadget,
            has_gadget and has_aesthetic,
            has_fashion and has_utility,
            (has_fashion or has_gadget) and (has_aesthetic or has_age),
        ]
    )
    axis_count = sum([has_age, has_fashion, has_gadget, has_aesthetic, has_utility])
    if is_thin_content or weak_generic_only or negative_dominant or aggregator_dominant:
        topic_fit = "low"
    elif topic_pairs_hit > 0 and axis_count >= 3:
        topic_fit = "high"
    elif topic_pairs_hit > 0:
        topic_fit = "medium"
    else:
        topic_fit = "low"

    # structure_fit: 「持ち物/身につけるものが中心」「見た目と機能の両立」「40代/大人視点」
    # 「比較・選別・更新理由」「実体験」の各要素がどれだけそろうか
    structure_components = sum(
        [
            has_fashion or has_gadget,
            has_aesthetic and has_utility,
            has_age,
            decision_hits > 0,
            personal_hits >= 1,
        ]
    )
    if is_thin_content or weak_generic_only or negative_dominant or aggregator_dominant:
        structure_fit = "low"
    elif structure_components >= 4:
        structure_fit = "high"
    elif structure_components >= 2:
        structure_fit = "medium"
    else:
        structure_fit = "low"

    # format: 粗い外形分類
    if _LISTICLE_PATTERN.search(text):
        observed_format = "listicle"
    elif decision_hits > 0 and theory_hits == 0:
        observed_format = "comparison" if decision_hits >= 2 else "advisory"
    elif personal_hits >= 2:
        observed_format = "story"
    elif len(text) < 15:
        observed_format = "news_reaction"
    else:
        observed_format = "unclear"

    # angle: 主な訴求角度
    if promo_hits > 0:
        observed_angle = "benefit" if decision_hits == 0 else "explanation"
    elif bait_hits > 0:
        observed_angle = "warning"
    elif personal_hits >= 2:
        observed_angle = "confession"
    elif decision_hits > 0:
        observed_angle = "explanation"
    elif theory_hits > 0:
        observed_angle = "identity"
    else:
        observed_angle = "unclear"

    # tone: 文体温度
    exclamation_count = text.count("!") + text.count("！")
    if promotionalness == "high":
        observed_tone = "promotional"
    elif bait_hits > 0 or exclamation_count >= 2:
        observed_tone = "sensational"
    elif personal_hits >= 2:
        observed_tone = "reflective"
    elif theory_hits > 0:
        observed_tone = "assertive"
    elif len(text) < 15:
        observed_tone = "neutral"
    else:
        observed_tone = "calm"

    # approach_value: 勝ち方の部品観察価値（ジャンル適合とは独立に評価してよい）
    approach_signals = sum(
        [
            decision_hits > 0,
            usefulness in ("medium", "high"),
            has_aesthetic and has_utility,
            has_age and has_aesthetic,
        ]
    )
    approach_value = "high" if approach_signals >= 3 else ("medium" if approach_signals >= 2 else "low")
    if aggregator_dominant:
        # Phase 2.3: 集約bot/雑多カテゴリ列挙は、他の軸が偶然揃っても観察価値なしとする
        approach_value = "low"

    # 三層探索方針: ファッション/ガジェット/交点シグナルを独立に計算する。
    # aggregator_dominant（集約bot等）の場合は三層いずれも意味を持たないためunclearに倒す。
    if aggregator_dominant or is_thin_content:
        layer_signals = {
            "fashion_signal_strength": "low",
            "gadget_signal_strength": "low",
            "intersection_signal_strength": "low",
            "age_signal_strength": "low",
            "layer_primary": "unclear",
            "layer_secondary": "none",
            "layer_confidence": "low",
            "layer_reasons": [],
        }
    else:
        layer_signals = _compute_layer_signals(genre_text, age_hits)

    return {
        "observed_format": observed_format,
        "observed_angle": observed_angle,
        "observed_tone": observed_tone,
        "observed_usefulness": usefulness,
        "observed_specificity": specificity,
        "observed_personalness": personalness,
        "observed_promotionalness": promotionalness,
        "observed_engagement_bait": engagement_bait,
        "observed_engagement_tier": engagement_tier,
        "observed_topic_fit": topic_fit,
        "observed_structure_fit": structure_fit,
        "observed_approach_value": approach_value,
        **layer_signals,
        "_is_likely_creative_writing": is_likely_creative_writing,  # 内部フラグ（CSV/JSON出力の観察フィールドには含めない）
        "_is_thin_content": is_thin_content,
    }


def _classify(post: dict, obs: dict) -> tuple[str, list[str], str, str | None]:
    """観察結果からclassification / classification_reasons / confidence / manual_review理由を決める。

    4分類の解釈（維持）:
        reject: ジャンル外/宣伝強/観察価値低/ノイズ強
        observe: 勝ち方の部品観察価値はあるが、ジャンル交点または構造適合が弱い
        manual_review: 自動判定だけでは決めきれない、惜しい候補
        pre_teacher_candidate: 40代ファッション×ガジェット前提でtopic/structure/approachが揃う候補
    """
    reasons: list[str] = []
    text = post.get("text") or ""
    is_creative = obs["_is_likely_creative_writing"]
    is_thin = obs["_is_thin_content"]

    # Phase 2.1: reject理由の分解に使う補助シグナル（_observeと同じ定義をここでも算出）。
    # obsのpublicフィールドを増やさない方針のため、text から直接再計算する
    # （_classifyは元々AGE_KEYWORDS等をtextから直接数えている既存の書き方に合わせる）。
    # Phase 2.2: ジャンル辞書のカウントは、否定文脈で使われている箇所をマスクした
    # genre_text に対して行う（NEGATIVE_FALSE_MATCH_KEYWORDSは別概念のためtextのまま）。
    genre_text = _mask_negated_genre_context(text)
    negation_ctx = _detect_negation_context(text)
    # 否定文脈語があるがexceptionで説明されない（＝未解決の曖昧さが残る）状態。
    # 三層探索方針の追加救済パスは、この場合はmanual_reviewの否定文脈ハンドリングに委ねる。
    negation_unresolved = bool(negation_ctx["matched_negative_terms"]) and not negation_ctx["matched_exception_terms"]
    negative_hits = _count_hits(text, NEGATIVE_FALSE_MATCH_KEYWORDS)
    # 2026-09-01変更: gadget軸はGADGET_KEYWORDSではなくobs["observed_engagement_tier"]
    # （_observe()で算出済み）を参照する。
    specific_genre_signal_count = (
        _count_hits(genre_text, FASHION_KEYWORDS_SPECIFIC)
        + _count_hits(genre_text, AGE_KEYWORDS_SPECIFIC)
        + (1 if obs["observed_engagement_tier"] == "qualifying" else 0)
        + _count_hits(genre_text, AESTHETIC_KEYWORDS)
        + _count_hits(genre_text, UTILITY_KEYWORDS)
        + _count_hits(genre_text, DECISION_KEYWORDS)
        + _count_hits(genre_text, SUPPORTIVE_MEDIA_STYLE_KEYWORDS)
    )
    weak_generic_only = specific_genre_signal_count == 0 and (
        _count_hits(genre_text, AGE_KEYWORDS) > 0 or _count_hits(genre_text, FASHION_KEYWORDS) > 0
    )
    negative_dominant = negative_hits >= 2 and specific_genre_signal_count == 0

    # Phase 2.3: トレンド系broad keywordのfalse positive対策（_observeと同じ定義）。
    trend_ctx = _detect_trend_false_positive(genre_text)
    aggregator_dominant = (
        trend_ctx["has_aggregator_pattern"] or trend_ctx["multi_category_noise_count"] >= 3
    ) and not trend_ctx["has_trend_exception"]

    # --- reject 判定 ---
    if obs["observed_promotionalness"] == "high":
        reasons.append("promotional_signal_strong（宣伝・購入誘導が強い）")
    if obs["observed_engagement_bait"] == "high":
        reasons.append("bait_signal_strong（露骨な保存/フォロー/RT誘導）")
    if len(text) < 10 or is_thin:
        reasons.append("content_too_thin（判断材料が乏しい、またはURLのみ）")
    low_all = (
        obs["observed_topic_fit"] == "low"
        and obs["observed_structure_fit"] == "low"
        and obs["observed_approach_value"] == "low"
    )
    if low_all:
        # Phase 2.3: 集約bot/雑多カテゴリ列挙/broad trendのみが理由になっている場合、
        # まずそれを明示する（トレンド系のfalse positiveを可視化する）。
        if aggregator_dominant:
            if trend_ctx["has_aggregator_pattern"]:
                reasons.append(
                    "trend_aggregator_pattern_detected（集約bot/総合まとめ/雑多カテゴリ列挙のパターンを検出）"
                )
            if trend_ctx["multi_category_noise_count"] >= 3:
                reasons.append(
                    "multi_category_noise_dominant（ジャンル外カテゴリが多数併存しジャンル整合性を壊している）"
                )
        elif trend_ctx["should_downrank_trend_signal"]:
            reasons.append(
                "trend_signal_is_broad_only（『トレンド』『ランキング』等はあるがジャンル支持語が伴っていない）"
            )
        # Phase 2.2: 否定文脈のジャンル語がシグナル除外の原因になっている場合、
        # まずそれを明示する（false_keyword_overlap等の一般理由に加えて記録する）。
        if negation_ctx["override_should_apply"]:
            reasons.append(
                "negative_genre_context_detected（否定文脈のジャンル語を除外: "
                + "/".join(negation_ctx["matched_negative_terms"])
                + "）"
            )
        # Phase 2.1: genre_fit_low を「広い語のみの偶然一致」「別テーマ支配」「純粋にジャンル外」の
        # 3種に分解し、manual_reviewへ流れていた偶然一致ノイズをここでrejectへ落とす。
        if negative_dominant:
            reasons.append(
                "negative_topic_dominant（スポーツ/恋愛/政治等、別テーマが支配的でジャンル固有シグナルが伴っていない）"
            )
        elif weak_generic_only:
            reasons.append(
                "false_keyword_overlap（『40代』『持ち物』等の広い語のみが一致し、ジャンル固有語が伴っていない）"
            )
        else:
            reasons.append("genre_fit_low（40代ファッション×ガジェットとの交点・観察価値ともに乏しい）")
    if is_creative and low_all:
        reasons.append("likely_creative_writing（創作/小説と思われ、かつジャンル適合も低い）")

    reject_triggered = (
        obs["observed_promotionalness"] == "high"
        or obs["observed_engagement_bait"] == "high"
        or len(text) < 10
        or is_thin
        or low_all
        or negative_dominant
        or aggregator_dominant
    )

    if reject_triggered:
        confidence = "high" if (obs["observed_promotionalness"] == "high" or len(text) < 10 or is_thin) else "medium"
        return "reject", reasons, confidence, None

    # --- pre_teacher_candidate 判定（ただし創作らしさが強い場合は manual_review へ降格） ---
    # Phase 2.1: topic_fitはhigh（軸3つ以上の共起）を必須にし、DECISION_KEYWORDS拡張による
    # pre_teacher_candidateの乱発を防ぐ。medium程度のジャンル適合はobserveへ寄せる。
    topic_ok = obs["observed_topic_fit"] == "high"
    structure_ok = obs["observed_structure_fit"] in ("high", "medium")
    approach_ok = obs["observed_approach_value"] in ("high", "medium")

    if topic_ok and structure_ok and approach_ok:
        if is_creative:
            reasons.append(
                "likely_creative_writing（第◯章/小説/物語等の語を検出。"
                "topic/structure/approachは揃うが創作の可能性が高いためmanual_reviewへ降格）"
            )
            return "manual_review", reasons, "low", reasons[-1]

        candidate_reasons = []
        if obs["observed_topic_fit"] != "low" and _count_hits(genre_text, AGE_KEYWORDS) > 0 and _count_hits(genre_text, FASHION_KEYWORDS) > 0:
            candidate_reasons.append("age_and_fashion_signal_detected")
        if _count_hits(genre_text, FASHION_KEYWORDS) > 0 and obs["observed_engagement_tier"] == "qualifying":
            candidate_reasons.append("fashion_gadget_intersection_detected（gadget側はエンゲージメント実測で判定）")
        if _count_hits(genre_text, AESTHETIC_KEYWORDS) > 0 and _count_hits(genre_text, UTILITY_KEYWORDS) > 0:
            candidate_reasons.append("aesthetic_and_utility_both_present")
        if _count_hits(genre_text, DECISION_KEYWORDS) > 0:
            candidate_reasons.append("comparison_or_selection_structure_detected")
        if not candidate_reasons:
            candidate_reasons.append("ownership_or_carry_signal_detected")

        reasons.extend(candidate_reasons)
        confidence = "high" if (obs["observed_topic_fit"] == "high" and obs["observed_structure_fit"] == "high") else "medium"
        return "pre_teacher_candidate", reasons, confidence, None

    # --- 三層探索方針: fashion/gadget単独でも高信頼度なら pre_teacher_candidate 化する ---
    # 既存のtopic_fit=="high"ゲート（軸3つ以上の共起、実質的に交点向け）を満たさない場合でも、
    # ガジェット単体の良質投稿（例:「イヤホン比較【40代の実体験】」）が交点条件を満たせず
    # observe止まりになる「ガジェット単体止まり」問題（ops/reports/next_batch_exploration_2026-08-16.md）
    # に対応するため、fashion/gadget単独の高信頼度シグナル+構造/アプローチ再利用価値がある場合は
    # 候補化を許可する。交点候補が最優先である点は変えず、あくまで追加の候補化パスとする。
    if (
        not is_creative
        and not negation_unresolved
        and obs["observed_structure_fit"] in ("high", "medium")
        and obs["observed_approach_value"] != "low"
    ):
        if obs["layer_primary"] == "fashion" and obs["fashion_signal_strength"] == "high":
            reasons.append("fashion_only_but_reusable（ファッション単独だが構造・アプローチ再利用価値が高い）")
            return "pre_teacher_candidate", reasons, "medium", None
        # 2026-09-01変更（GOV-20260901-GADGET-ONLY-REUSABLE-ENGAGEMENT-GATE-01）:
        # gadget_signal_strength（GADGET_CORE_KEYWORDS由来）はトピック関連性の
        # シグナルとして引き続き必須条件に使うが、これだけではteacher候補への
        # 昇格を許可しない。obs["observed_engagement_tier"]=="qualifying"
        # （実測エンゲージメントが閾値を満たす）も必須とする。insufficient_data/low
        # の場合はここでは昇格させず、以降のobserve/manual_review判定に委ねる
        # （既知のATH-PRO5MK2×骨伝導RT等、impression_count=0の投稿がキーワード
        # 一致のみでteacher候補になり続ける抜け道を塞ぐ）。
        if (
            obs["layer_primary"] == "gadget"
            and obs["gadget_signal_strength"] == "high"
            and obs["observed_engagement_tier"] == "qualifying"
        ):
            reasons.append(
                "gadget_only_but_reusable（ガジェット単独だが構造・アプローチ再利用価値が高く、"
                "エンゲージメント実測もqualifying）"
            )
            return "pre_teacher_candidate", reasons, "medium", None

    # --- observe 判定 ---
    # 三層探索方針: 交点シグナルはあるが上記のpre_teacher_candidateゲートに届かない場合、
    # 「交点候補未満だが観察価値あり」として明示する。
    if (
        obs["observed_topic_fit"] != "low"
        and obs["layer_primary"] == "intersection"
        and obs["intersection_signal_strength"] != "low"
    ):
        reasons.append("intersection_candidate_but_weak_metrics（交点シグナルはあるが反応指標/観察価値が弱く主候補には未達）")
        return "observe", reasons, "medium", None
    # Phase 2.1: 「◯選」「コツ」「着映え」「小物使い」等のジャンル整合的な実用・比較・
    # 選別・見え方改善型を、manual_reviewに落とさずここで拾い上げる。
    has_selection_format = _count_hits(genre_text, DECISION_KEYWORDS) > 0 or bool(_SENTAKU_PATTERN.search(genre_text))
    has_supportive_media = _count_hits(genre_text, SUPPORTIVE_MEDIA_STYLE_KEYWORDS) > 0
    has_aesthetic_signal = _count_hits(genre_text, AESTHETIC_KEYWORDS) > 0

    if obs["observed_topic_fit"] != "low" and has_selection_format:
        # Phase 2.3: 「◯選」「コツ」等の一致がトレンド語（トレンド/ランキング等）由来の場合、
        # TREND_EXCEPTIONS保護によるものであることを明示する。
        if trend_ctx["has_trend_exception"]:
            reasons.append(
                "trend_exception_preserved（『"
                + "/".join(trend_ctx["matched_trend_exceptions"])
                + "』等でジャンル文脈保護）"
            )
        reasons.append("list_or_selection_structure_detected（比較・選別・◯選・コツ形式が観察できる）")
        return "observe", reasons, "medium", None
    if obs["observed_topic_fit"] != "low" and has_supportive_media:
        reasons.append("supportive_media_style_detected（ファッションメディア的な持ち物紹介文脈）")
        return "observe", reasons, "medium", None
    if (
        obs["observed_topic_fit"] != "low"
        and trend_ctx["has_broad_trend_signal"]
        and trend_ctx["has_strong_genre_support"]
        and not trend_ctx["should_downrank_trend_signal"]
    ):
        reasons.append("genre_supported_trend_signal（ジャンル支持語と共起するトレンド語を観察価値ありと判断）")
        return "observe", reasons, "medium", None
    if obs["observed_topic_fit"] == "high" and obs["observed_approach_value"] == "low":
        reasons.append("strong_genre_signal_but_low_metrics（ジャンル適合は強いが観察価値・反応指標がまだ弱い）")
        return "observe", reasons, "medium", None
    if obs["observed_topic_fit"] != "low" and has_aesthetic_signal:
        # Phase 2.2: 審美シグナルがNEGATION_EXCEPTIONS（ダサくない等の失敗回避フレーム）由来なら
        # より具体的な理由コードにする。
        if negation_ctx["matched_exception_terms"]:
            reasons.append(
                "style_improvement_frame_detected（『"
                + "/".join(negation_ctx["matched_exception_terms"])
                + "』等の失敗回避・審美改善フレームとして扱う）"
            )
        else:
            reasons.append("aesthetic_improvement_signal_detected（見え方・印象の改善シグナルがある）")
        return "observe", reasons, "medium", None
    if obs["observed_structure_fit"] == "low" and obs["observed_approach_value"] != "low":
        reasons.append("strong_approach_but_not_enough_structure（構造適合は弱いが勝ち方の部品観察に使える）")
        return "observe", reasons, "medium", None
    if obs["observed_usefulness"] in ("medium", "high"):
        reasons.append("useful_fashion_format_detected（実用情報として観察価値がある）")
        return "observe", reasons, "medium", None

    # 三層探索方針: 上記の既存分岐で拾えなかったが、fashion/gadgetいずれかの単独シグナルが
    # highある場合の追加救済。しきい値はmediumではなくhighに限定する
    # （「バッグ」等FASHION_CORE1語だけでmedium判定になり、強盗事件ニュース等の
    # 既知false positiveがmanual_reviewの人間確認から素通りしてobserveへ漏れる自己検証結果を
    # 確認したため）。また、否定文脈が未解決（matched_negative_termsありexceptionなし）の場合は
    # ここで確定させず、既存のmanual_reviewの否定文脈ハンドリングに委ねる。
    if not negation_unresolved:
        if obs["layer_primary"] == "fashion" and obs["fashion_signal_strength"] == "high":
            reasons.append("fashion_signal_detected（ファッション単独の観察価値）")
            return "observe", reasons, "medium", None
        if obs["layer_primary"] == "gadget" and obs["gadget_signal_strength"] == "high":
            reasons.append("gadget_signal_detected（ガジェット単独の観察価値）")
            return "observe", reasons, "medium", None

    # --- manual_review（上記のいずれにも明確に該当しない・信号が競合） ---
    # Phase 2.1: 汎用すぎた strong_post_but_boundary_case を、ファッション/ガジェット
    # どちらの軸が弱いかが分かる理由へ分解する。
    manual_reason_parts = []
    # Phase 2.3: トレンド語が境界的にジャンルと共存している場合、まずそれを記録する
    # （TREND_EXCEPTIONS保護対象なら既にobserve/pre_teacher_candidateへ抜けているはずなのでここには来ない）。
    if trend_ctx["has_broad_trend_signal"] and not trend_ctx["has_trend_exception"]:
        if trend_ctx["has_strong_genre_support"]:
            manual_reason_parts.append(
                "broad_trend_with_partial_genre_support（トレンド語とジャンル支持語は共存するが自動確定には不十分）"
            )
        else:
            manual_reason_parts.append(
                "trend_signal_present_but_boundary_fit（トレンド語はあるがジャンル支持が弱く境界的）"
            )
    # Phase 2.2: 否定文脈語が検出された場合、まずそれを記録する（例外フレームか否かで理由を分ける）。
    if negation_ctx["matched_negative_terms"] and not negation_ctx["matched_exception_terms"]:
        manual_reason_parts.append(
            "mixed_negation_and_genre_signals（否定文脈語を検出: "
            + "/".join(negation_ctx["matched_negative_terms"])
            + "。他の箇所のジャンル適合と併存するため自動確定できない）"
        )
    elif negation_ctx["matched_exception_terms"]:
        manual_reason_parts.append(
            "negative_phrase_but_possible_style_context（『"
            + "/".join(negation_ctx["matched_exception_terms"])
            + "』等、審美改善フレームの可能性があるため自動確定しない）"
        )
    # 2026-09-01変更: GADGET_KEYWORDSではなくobs["observed_engagement_tier"]で判定する。
    has_gadget_signal = obs["observed_engagement_tier"] == "qualifying"
    has_fashion_or_age_signal = (
        _count_hits(genre_text, FASHION_KEYWORDS_SPECIFIC) > 0 or _count_hits(genre_text, AGE_KEYWORDS_SPECIFIC) > 0
    )
    if obs["observed_topic_fit"] == "medium" and obs["observed_structure_fit"] == "medium":
        manual_reason_parts.append(
            "good_format_but_boundary_fit（形式・構造は一定そろうが、ジャンル適合が中程度で自動確定できない）"
        )
    elif has_fashion_or_age_signal and not has_gadget_signal:
        manual_reason_parts.append(
            "fashion_signal_without_gadget_connection（ファッション/年齢シグナルはあるがガジェット接点が弱い）"
        )
    elif has_gadget_signal and not has_fashion_or_age_signal:
        manual_reason_parts.append(
            "gadget_signal_without_style_connection（ガジェットシグナルはあるがスタイル/見え方接点が弱い）"
        )
    elif obs["observed_topic_fit"] == "medium" and obs["observed_structure_fit"] == "low":
        manual_reason_parts.append("possible_genre_fit_but_low_specificity（ジャンル適合の可能性はあるが具体性が弱い）")
    # 三層探索方針: 橋渡し語はあるが交点として確定しきれない場合を明示する。
    if "bridge_signal_present_but_incomplete" in obs["layer_reasons"] and obs["intersection_signal_strength"] != "low":
        manual_reason_parts.append("bridge_signal_present_but_incomplete（橋渡し語はあるが交点として確定しきれない）")
    if obs["observed_promotionalness"] == "medium":
        manual_reason_parts.append("mixed_signals_need_human_review（宣伝性の強さを自動判定しきれない）")
    if is_creative:
        manual_reason_parts.append("likely_creative_writing")
    if not manual_reason_parts:
        manual_reason_parts.append("medium_fit_needs_human_judgment（自動分類の閾値付近で人間判断が必要）")

    manual_review_reason = "; ".join(manual_reason_parts)
    reasons.append(manual_review_reason)
    return "manual_review", reasons, "low", manual_review_reason


def _build_public_metrics(post: dict) -> dict:
    """Phase 1のフラット形式（like_count等が直下）からpublic_metricsのネスト辞書を組み立てる。"""
    return {
        "like_count": post.get("like_count"),
        "reply_count": post.get("reply_count"),
        "repost_count": post.get("repost_count"),
        "quote_count": post.get("quote_count"),
        "impression_count": post.get("impression_count"),
        "bookmark_count": post.get("bookmark_count"),
    }


_CSV_COLUMNS = [
    "post_id",
    "created_at",
    "author_id",
    "lang",
    "text",
    "like_count",
    "reply_count",
    "repost_count",
    "quote_count",
    "impression_count",
    "bookmark_count",
    "query_source",
    "classification",
    "confidence",
    "observed_format",
    "observed_angle",
    "observed_tone",
    "observed_usefulness",
    "observed_specificity",
    "observed_personalness",
    "observed_promotionalness",
    "observed_engagement_bait",
    "observed_engagement_tier",
    "observed_topic_fit",
    "observed_structure_fit",
    "observed_approach_value",
    "fashion_signal_strength",
    "gadget_signal_strength",
    "intersection_signal_strength",
    "age_signal_strength",
    "layer_primary",
    "layer_secondary",
    "layer_confidence",
    "layer_reasons",
    "classification_reasons",
]


def _write_csv(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for r in records:
            metrics = r["public_metrics"]
            row = {
                "post_id": r["post_id"],
                "created_at": r["created_at"],
                "author_id": r["author_id"],
                "lang": r["lang"],
                "text": r["text"],
                "like_count": metrics.get("like_count"),
                "reply_count": metrics.get("reply_count"),
                "repost_count": metrics.get("repost_count"),
                "quote_count": metrics.get("quote_count"),
                "impression_count": metrics.get("impression_count"),
                "bookmark_count": metrics.get("bookmark_count"),
                "query_source": ";".join(r.get("query_source") or []),
                "classification": r["classification"],
                "confidence": r["confidence"],
                "layer_reasons": " | ".join(r.get("layer_reasons") or []),
                "classification_reasons": " | ".join(r["classification_reasons"]),
            }
            for k in (
                "observed_format",
                "observed_angle",
                "observed_tone",
                "observed_usefulness",
                "observed_specificity",
                "observed_personalness",
                "observed_promotionalness",
                "observed_engagement_bait",
                "observed_topic_fit",
                "observed_structure_fit",
                "observed_approach_value",
                "fashion_signal_strength",
                "gadget_signal_strength",
                "intersection_signal_strength",
                "age_signal_strength",
                "layer_primary",
                "layer_secondary",
                "layer_confidence",
            ):
                row[k] = r[k]
            writer.writerow(row)


def main() -> None:
    posts = _load_input()
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    classified: list[dict] = []
    for post in posts:
        obs = _observe(post)
        classification, reasons, confidence, manual_reason = _classify(post, obs)
        public_obs = {k: v for k, v in obs.items() if not k.startswith("_")}  # 内部フラグ(_is_*)は出力に含めない

        record = {
            "post_id": post.get("id"),
            "text": post.get("text"),
            "author_id": post.get("author_id"),
            "created_at": post.get("created_at"),
            "lang": post.get("lang"),
            "public_metrics": _build_public_metrics(post),
            "query_source": post.get("query_source"),
            "classification": classification,
            "classification_reasons": reasons,
            "confidence": confidence,
            **public_obs,
            "observed_manual_review_reason": manual_reason,
        }
        classified.append(record)

    by_class: dict[str, list[dict]] = {"reject": [], "observe": [], "manual_review": [], "pre_teacher_candidate": []}
    for r in classified:
        by_class[r["classification"]].append(r)

    (_OUTPUT_DIR / "classified_all.json").write_text(
        json.dumps(classified, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_csv(_OUTPUT_DIR / "classified_all.csv", classified)

    for name in ("reject", "observe", "manual_review", "pre_teacher_candidate"):
        (_OUTPUT_DIR / f"{name}.json").write_text(
            json.dumps(by_class[name], ensure_ascii=False, indent=2), encoding="utf-8"
        )
    _write_csv(_OUTPUT_DIR / "pre_teacher_candidates.csv", by_class["pre_teacher_candidate"])

    confidence_dist = Counter(r["confidence"] for r in classified)
    multi_query_count = sum(1 for r in classified if len(r.get("query_source") or []) > 1)
    reject_reason_counter = Counter(
        reason for r in by_class["reject"] for reason in r["classification_reasons"]
    )
    pre_teacher_reason_counter = Counter(
        reason for r in by_class["pre_teacher_candidate"] for reason in r["classification_reasons"]
    )

    # 三層探索方針: layer_primaryの分布と、4分類×layer_primaryのクロス集計を記録する。
    layer_primary_dist = Counter(r["layer_primary"] for r in classified)
    layer_by_classification: dict[str, dict[str, int]] = {}
    for cls_name in ("reject", "observe", "manual_review", "pre_teacher_candidate"):
        layer_by_classification[cls_name] = dict(Counter(r["layer_primary"] for r in by_class[cls_name]))

    run_summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "input_count": len(posts),
        "reject_count": len(by_class["reject"]),
        "observe_count": len(by_class["observe"]),
        "manual_review_count": len(by_class["manual_review"]),
        "pre_teacher_candidate_count": len(by_class["pre_teacher_candidate"]),
        "confidence_distribution": dict(confidence_dist),
        "multi_query_hit_count": multi_query_count,
        "top_reject_reasons": reject_reason_counter.most_common(5),
        "top_pre_teacher_candidate_reasons": pre_teacher_reason_counter.most_common(5),
        "layer_primary_distribution": dict(layer_primary_dist),
        "layer_primary_by_classification": layer_by_classification,
        "status": "success",
    }
    (_OUTPUT_DIR / "run_summary.json").write_text(
        json.dumps(run_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"入力件数: {len(posts)}")
    print(f"reject: {len(by_class['reject'])}")
    print(f"observe: {len(by_class['observe'])}")
    print(f"manual_review: {len(by_class['manual_review'])}")
    print(f"pre_teacher_candidate: {len(by_class['pre_teacher_candidate'])}")
    print(f"保存先: {_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
