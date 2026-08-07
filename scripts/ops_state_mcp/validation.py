"""write前のスキーマ検証。

「書けると思っていたが実際には保存できない」不整合(2026-08-06に発覚したpost_log/notes、
metrics_snapshot/data_quality等)をwrite時点で検出するための最小実装。

post/statusまわりは既存の schemas/post_log.schema.json をそのまま契約として再利用する。
review/metricsまわりは対応するローカルschemaが無い(reviewsはmarket_grounded_review_template.md
がmarkdown上の型定義しか持たず、metrics_24hはSheets独自の列名でmetrics_snapshot.schema.json
とは field名が一致しない)ため、ここで最小限のenum検証を新規定義する。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMAS_DIR = _REPO_ROOT / "schemas"


def _load_schema(name: str) -> dict[str, Any]:
    with open(_SCHEMAS_DIR / name, encoding="utf-8") as f:
        return json.load(f)


_POST_LOG_SCHEMA = _load_schema("post_log.schema.json")

# market_grounded_review_template.md / templates/x_post_template.md 由来のenum
# (JSON schema化されていないため、ここで最小限のみ定義する。判定基準そのものは変更しない)
_STRENGTH_VALUES = {"強い", "同等", "弱い"}
_REVIEW_ACTION_VALUES = {"keep", "revise", "hold"}
_CONFIDENCE_VALUES = {"high", "medium", "low"}
_DATA_QUALITY_VALUES = {"ok", "partial", "auth_missing", "api_error", "url_unresolved", "manual"}
_METRICS_SOURCE_VALUES = {"manual_screenshot", "x_api"}


class ValidationError(ValueError):
    pass


def validate_post_draft(post: dict[str, Any]) -> None:
    """record_post_draft用: post_log.schema.jsonの必須項目・enum・patternをそのまま流用して検証する。

    posts シート固有の追加列(tweet_id/posted_url等)は対象外(空でよい)。
    """
    props = _POST_LOG_SCHEMA["properties"]
    # post_log.schema.jsonの必須項目のうち、posts行作成時点でも意味を持つものだけを検証する
    # (final_text/approved_byは未確定でよいためNoneを許容し、必須チェックからは除く)
    required_at_draft = [
        r for r in _POST_LOG_SCHEMA["required"]
        if r not in {"final_text", "approved_by"}
    ]
    missing = [r for r in required_at_draft if r not in post]
    if missing:
        raise ValidationError(f"必須フィールドが不足しています: {missing}")

    if post.get("mode") not in props["mode"]["enum"]:
        raise ValidationError(f"modeが不正です: {post.get('mode')}（許容値: {props['mode']['enum']}）")
    if post.get("format") not in props["format"]["enum"]:
        raise ValidationError(f"formatが不正です: {post.get('format')}（許容値: {props['format']['enum']}）")
    import re

    if not re.match(props["post_id"]["pattern"], str(post.get("post_id", ""))):
        raise ValidationError(
            f"post_idの形式が不正です: {post.get('post_id')}（期待パターン: {props['post_id']['pattern']}）"
        )


def validate_post_status(status: str) -> None:
    """set_post_status用: post_log.schema.jsonのstatus enumをそのまま流用して検証する。"""
    allowed = _POST_LOG_SCHEMA["properties"]["status"]["enum"]
    if status not in allowed:
        raise ValidationError(f"statusが不正です: {status}（許容値: {allowed}）")


def validate_review_result(review: dict[str, Any]) -> None:
    """record_review_result用: market_grounded_review_template.mdの型定義を最小限検証する。"""
    if "post_id" not in review or not review["post_id"]:
        raise ValidationError("post_idは必須です")
    if "reviewer" not in review or not review["reviewer"]:
        raise ValidationError("reviewerは必須です")

    for field in ("hook_assessment", "whole_post_assessment", "cta_fit_assessment"):
        value = review.get(field)
        if value is not None and value not in _STRENGTH_VALUES:
            raise ValidationError(f"{field}が不正です: {value}（許容値: {_STRENGTH_VALUES}）")

    axis_scores = review.get("axis_scores")
    if isinstance(axis_scores, dict):
        for axis, value in axis_scores.items():
            if value not in _STRENGTH_VALUES:
                raise ValidationError(f"axis_scores[{axis}]が不正です: {value}（許容値: {_STRENGTH_VALUES}）")

    action = review.get("action")
    if action is not None and action not in _REVIEW_ACTION_VALUES:
        raise ValidationError(f"actionが不正です: {action}（許容値: {_REVIEW_ACTION_VALUES}）")

    confidence = review.get("confidence")
    if confidence is not None and confidence not in _CONFIDENCE_VALUES:
        raise ValidationError(f"confidenceが不正です: {confidence}（許容値: {_CONFIDENCE_VALUES}）")


def validate_metrics_snapshot(data_quality: str, source: str) -> None:
    """record_metrics_snapshot用: data_quality/sourceのenumを検証する。"""
    if data_quality not in _DATA_QUALITY_VALUES:
        raise ValidationError(
            f"data_qualityが不正です: {data_quality}（許容値: {_DATA_QUALITY_VALUES}）"
        )
    if source not in _METRICS_SOURCE_VALUES:
        raise ValidationError(f"sourceが不正です: {source}（許容値: {_METRICS_SOURCE_VALUES}）")
