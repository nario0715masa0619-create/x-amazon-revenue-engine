"""post_outcome（投稿実績の「勝敗」判定・正本）のpure function層。

このリポジトリには「勝ち投稿」の定義がGate B quality_band（scripts/external_audit_schema.py、
投稿前・下書きが先生投稿並みかの予測）とtopic_performance_band（scripts/topic_group_state.py、
投稿後・post_analyticsからの書き込み専用フィールドで、どの判断ロジックからも読まれて
いなかった）の2系統に分裂しており、かつどちらも「勝敗が確定したかどうか」を単一の
正本として下流の意思決定（retry_budget/cooldown/候補フィルタ）へ接続していなかった
（GOV-20260901-INVESTIGATION-01調査より）。

**このモジュールのclassify_post_outcome()が、「勝ち投稿かどうか」を問われたときに
参照すべき唯一の正本である。** Gate B quality_band（TEACHER_FLOOR/SHIP_THRESHOLD/
STRONG_SHIP_THRESHOLD、scripts/external_audit_schema.py）は「投稿前の予測」役割の
まま一切変更していない。topic_performance_band（scripts/topic_group_state.py）は
「投稿後の生の実測値（impression_count）の要約」役割のまま維持し、削除・置換しない。
本モジュールはその上に「投稿は勝った/引き分けた/負けた/判定不能」という確定判断を
additiveに重ね、topic_group_state.record_post_outcome()経由でライフサイクル管理へ
配線する。

フェーズ1調査結果（詳細: ops/reports/post_outcome_design_2026-09-01.md）:
Amazonアフィリエイトのクリック・コンバージョン計測経路は、このリポジトリのどの
コードパスにも実装されていない（PA-API連携なし、トラッキングリンク/短縮URLなし、
Amazon Associatesレポート取込スクリプトなし、.env.exampleにAmazon系認証情報項目なし、
docs/policies/amazon-affiliate-policy.mdは表現・開示ルールのみで計測方針の記載なし）。
scripts/x_post_analytics.pyが取得するpost_analyticsはX API v2 tweets lookup由来の
public_metrics/non_public_metrics/organic_metrics/promoted_metricsのみで、
アフィリエイト成果にrelateする項目はゼロ。旧schemas/metrics_snapshot.schema.jsonには
link_clicks/conversions/revenue/epcフィールドが定義されているが、対応する
ops/logs/metrics_snapshots.csvは実データ1行（全項目0、2026-08-02のt0スナップショット）
のみで、CLAUDE.md実行ルール8により2026-08-07付けで凍結済み（正本はGoogle Sheets経由の
`ops-state` MCP）。現行の正本（scripts/ops_state_mcp/server.py `record_metrics_snapshot()`）
にはconversions/revenue/epcの受け皿すら存在しない（url_link_clicksのみ受け付けるが、
これはXの「リンクが押された回数」であり購入確定を意味しない）。
**結論: 現時点で実データとして使える指標はエンゲージメント系
（impressions/likes/replies/retweets/quotes/bookmarks）のみであり、
アフィリエイト成果（コンバージョン・収益）を含まない。**
そのため下記のaffiliate_metrics引数は「配線待ちの受け皿」であり、2026-09-01時点で
実際にこの引数を渡す呼び出し元はコードベース内に存在しない。

外部AI呼び出しは行わない。production scoring/Gate A/thresholdsには一切触れない。
Gate B quality_bandの判定ロジック（TEACHER_FLOOR/SHIP_THRESHOLD/STRONG_SHIP_THRESHOLD）
も変更しない。

設計文書: ops/reports/post_outcome_design_2026-09-01.md
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from topic_group_state import PERFORMANCE_BAND_THRESHOLDS

POST_OUTCOMES = ("win", "neutral", "loss", "insufficient_data")

# ============================================================================
# 閾値定数（すべて暫定値。最終決定は人間が行う。変更する場合はこのブロックのみ編集する）
# ============================================================================

# 最小サンプルインプレッション数。これを下回るrunは"win/neutral/loss"を判定せず
# insufficient_dataとする。
# 暫定値: topic_group_state.PERFORMANCE_BAND_THRESHOLDS["low"]（50）をそのまま流用
# （新しい数値を独自に設定しない）。
# 根拠: 現状唯一の実測データ（mainline-run-2026-08-29-001、impression_count=10）を、
# これまでのtopic_performance_bandロジックでは無条件に"low"（＝弱い実績）として
# 扱っていた。しかし10インプレッションは、統計的に「弱かった」と「まだ測定できて
# いない」を区別できないほど小さいサンプルである。この閾値により、その区別を
# 明示的に行う（GOV-20260901-INVESTIGATION-01調査で指摘された論点への対応）。
# 変更する場合: この定数の値のみを書き換える（他の計算式は自動的に追随する）。
MIN_SAMPLE_IMPRESSIONS_THRESHOLD = PERFORMANCE_BAND_THRESHOLDS["low"]

# "win"と判定するための最小インプレッション数（かつエンゲージメントが1件以上必要）。
# 暫定値: PERFORMANCE_BAND_THRESHOLDS["medium"]（200）をそのまま流用。
# 根拠: 既存のtopic_performance_band（"high"判定の下限）をそのまま引き継ぎ、
# 新たな数値を独自に設定しない。実運用データが蓄積されたら見直す。
WIN_IMPRESSION_THRESHOLD = PERFORMANCE_BAND_THRESHOLDS["medium"]

# エンゲージメント合計（like+reply+retweet+quote+bookmark）が0件のrunは、
# 最小サンプルを満たしていてもインプレッション数に関わらず"loss"に固定する。
# 根拠: 実測データ（impression_count=10、エンゲージメント全項目0）を踏まえた
# 安全側の追加ルール。インプレッション数だけを見る既存のtopic_performance_band
# ロジックでは「見られてはいるが誰にも反応されなかった」投稿を"neutral"や"win"に
# 誤分類しうるため、エンゲージメント0件を明示的な下限ガードとして追加した。
# この設計判断自体、人間の確認が必要（元のPERFORMANCE_BAND_THRESHOLDS設計には
# 無かったルールを新設しているため）。
ZERO_ENGAGEMENT_FORCES_LOSS = True

# アフィリエイト成果（コンバージョン等）が見つかった場合に最優先で参照するキー名。
# 2026-09-01時点のフェーズ1調査では、このリポジトリのどのコードパスにも
# アフィリエイトのクリック・コンバージョン計測は実装されていない（本ファイル冒頭の
# docstring参照）。そのため下記のaffiliate_metrics引数は現状どの呼び出し元からも
# 渡されない「配線待ちの受け皿」である。将来、計測経路が実装された場合は、ここに
# 掲げたキーが正の値を持てばエンゲージメント指標より優先してoutcomeを決定する
# 設計とする（優先順位: affiliate_metrics（存在する場合のみ）> エンゲージメント指標）。
AFFILIATE_CONVERSION_KEY = "conversions"

_ENGAGEMENT_METRIC_KEYS = ("like_count", "reply_count", "retweet_count", "quote_count", "bookmark_count")


class PostOutcomeError(ValueError):
    pass


@dataclass
class PostOutcomeResult:
    """classify_post_outcome()の戻り値。「勝ち投稿かどうか」を問われた場合の
    唯一の正本判定結果。"""

    outcome: str  # "win" | "neutral" | "loss" | "insufficient_data"
    reason: str
    impression_count: int | None
    engagement_total: int | None
    used_affiliate_override: bool = False


def _sum_engagement(public_metrics: dict[str, Any]) -> int:
    return sum(int(public_metrics.get(k) or 0) for k in _ENGAGEMENT_METRIC_KEYS)


def classify_post_outcome(
    public_metrics: dict[str, Any] | None,
    fetch_status: str | None = None,
    affiliate_metrics: dict[str, Any] | None = None,
) -> PostOutcomeResult:
    """投稿の実績値から「勝ち/引き分け/負け/判定不能」を判定する、唯一の正本関数。

    優先順位: affiliate_metricsが渡され、かつAFFILIATE_CONVERSION_KEYが正の値を
    持つ場合はそれを最優先しoutcome="win"とする（2026-09-01時点、この引数を実際に
    渡す呼び出し元はコードベース内に存在しない——フェーズ1調査でアフィリエイト
    計測経路が未実装と確認したため。将来の配線に備えた受け皿）。それ以外は、
    エンゲージメント指標（public_metrics）のみで判定する。

    public_metricsがNone、またはfetch_statusが実測失敗を示す場合は
    outcome="insufficient_data"とする（データが無い状態を安易に"loss"扱いしない）。
    impression_countがMIN_SAMPLE_IMPRESSIONS_THRESHOLD未満の場合も同様に
    insufficient_dataとする（極小サンプルを"loss"と誤判定しないため）。
    """
    if affiliate_metrics and affiliate_metrics.get(AFFILIATE_CONVERSION_KEY):
        try:
            if float(affiliate_metrics[AFFILIATE_CONVERSION_KEY]) > 0:
                return PostOutcomeResult(
                    outcome="win",
                    reason=f"{AFFILIATE_CONVERSION_KEY}>0のためアフィリエイト成果を最優先で採用",
                    impression_count=(public_metrics or {}).get("impression_count"),
                    engagement_total=_sum_engagement(public_metrics) if public_metrics else None,
                    used_affiliate_override=True,
                )
        except (TypeError, ValueError):
            pass  # 数値化できない値は無視してエンゲージメント判定にフォールバックする

    if fetch_status == "failed_non_blocking" or public_metrics is None:
        return PostOutcomeResult(
            outcome="insufficient_data",
            reason="post_analyticsが未取得（fetch_status=failed_non_blocking、またはpublic_metricsなし）",
            impression_count=None,
            engagement_total=None,
        )

    impression_count = public_metrics.get("impression_count")
    if impression_count is None:
        return PostOutcomeResult(
            outcome="insufficient_data",
            reason="impression_countが取得できていない",
            impression_count=None,
            engagement_total=None,
        )

    engagement_total = _sum_engagement(public_metrics)

    if impression_count < MIN_SAMPLE_IMPRESSIONS_THRESHOLD:
        return PostOutcomeResult(
            outcome="insufficient_data",
            reason=(
                f"impression_count={impression_count} が最小サンプル閾値"
                f"（{MIN_SAMPLE_IMPRESSIONS_THRESHOLD}）未満のため判定不能"
            ),
            impression_count=impression_count,
            engagement_total=engagement_total,
        )

    if ZERO_ENGAGEMENT_FORCES_LOSS and engagement_total == 0:
        return PostOutcomeResult(
            outcome="loss",
            reason=(
                f"impression_count={impression_count}は最小サンプルを満たすが、"
                "エンゲージメント（like/reply/retweet/quote/bookmark）が一件もない"
            ),
            impression_count=impression_count,
            engagement_total=engagement_total,
        )

    if impression_count >= WIN_IMPRESSION_THRESHOLD:
        return PostOutcomeResult(
            outcome="win",
            reason=(
                f"impression_count={impression_count} がwin閾値"
                f"（{WIN_IMPRESSION_THRESHOLD}）以上、かつエンゲージメントあり"
            ),
            impression_count=impression_count,
            engagement_total=engagement_total,
        )

    return PostOutcomeResult(
        outcome="neutral",
        reason=(
            f"impression_count={impression_count} は最小サンプル以上win閾値未満、"
            "かつエンゲージメントあり"
        ),
        impression_count=impression_count,
        engagement_total=engagement_total,
    )


def post_outcome_result_to_dict(result: PostOutcomeResult) -> dict[str, Any]:
    return asdict(result)
