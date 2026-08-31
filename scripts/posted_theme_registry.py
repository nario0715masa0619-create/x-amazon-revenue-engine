"""posted_theme_registry（投稿済みテーマ除外の恒久対策）のpure function層。

実投稿済み（`published_at`/`post_url`/`published_draft_id`が揃っている）mainline runから、
mainline再流入防止用の軽量インデックスを構築・照合する。**source_post_idの完全一致だけでは
不十分**という前提に立ち、`topic_dedupe.py`が生成する`theme_signature`をmainline再利用判定の
主キーとして使う。

投稿済みテーマの再流入をblockすることが目的であり、research/shadow/replayでの再検証は
禁止しない——blockされた候補は`route_to_research=True`として研究側へ回せる。

外部API呼び出しは一切行わない。production scoring/Gate A/thresholds/shipping decisionには
一切触れない。

設計文書: ops/reports/posted_theme_exclusion_design_2026-08-30.md
"""

from __future__ import annotations

import glob
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from topic_dedupe import build_theme_profile, theme_component_overlap_ratio

# --------------------------------------------------------------------------
# 判定閾値（初期値、conservative側に設定。設計メモに明記のうえ定数化）
# --------------------------------------------------------------------------
HIGH_SIMILARITY_THRESHOLD = 0.6  # この値以上のoverlap_ratioならhigh_theme_similarity
RELATED_THRESHOLD = 0.3  # この値以上ならrelated_but_not_blocking（block未満）
TOPIC_GROUP_COOLDOWN_DAYS = 21  # 同一topic_groupの実投稿後、この日数はmainline候補から外す（初期値）

MATCH_TYPES = ("none", "exact_source_match", "high_theme_similarity", "related_but_not_blocking")
EXCLUSION_SCOPES = ("mainline_block", "warning_only")


class PostedThemeRegistryError(ValueError):
    pass


@dataclass
class PostedThemeEntry:
    """posted theme registryの1レコード。実投稿済みrun 1件に対応する。"""

    run_id: str
    published_at: str | None
    post_url: str | None
    published_draft_id: str | None
    source_post_id: str | None
    target_layer: str | None
    theme_signature: str
    theme_key_terms: dict[str, list[str]]
    topic_group: str
    exclusion_scope: str = "mainline_block"
    cooldown_active: bool = True
    notes: str | None = None


def build_posted_theme_entry_from_minimal_run_log(
    minimal_run_log: dict[str, Any],
    draft_texts_by_id: dict[str, str],
    source_full_text: str | None = None,
    notes: str | None = None,
) -> PostedThemeEntry | None:
    """minimal_run_log（辞書、scripts/minimal_run_log.pyの出力）1件から、実投稿済み
    （published_at/post_url/published_draft_idがすべて揃っている）場合のみ
    PostedThemeEntryを組み立てる。未投稿ならNoneを返す（呼び出し側でスキップする）。

    draft_texts_by_idは{draft_id: 実際のdraft本文}の辞書。theme_signatureの計算材料として、
    実際に投稿されたdraft本文（published_draft_idに対応するもの）を使う。source_full_textを
    渡すとより安定した抽出になる（渡さなくても動作する）。
    """
    if not (
        minimal_run_log.get("published_at")
        and minimal_run_log.get("post_url")
        and minimal_run_log.get("published_draft_id")
    ):
        return None

    published_draft_id = minimal_run_log["published_draft_id"]
    draft_text = draft_texts_by_id.get(published_draft_id, "")
    texts = [draft_text]
    if source_full_text:
        texts.append(source_full_text)

    profile = build_theme_profile(texts)

    return PostedThemeEntry(
        run_id=minimal_run_log.get("run_id", ""),
        published_at=minimal_run_log.get("published_at"),
        post_url=minimal_run_log.get("post_url"),
        published_draft_id=published_draft_id,
        source_post_id=minimal_run_log.get("source_post_id"),
        target_layer=minimal_run_log.get("target_layer"),
        theme_signature=profile["theme_signature"],
        theme_key_terms=profile["theme_components"],
        topic_group=profile["topic_group"],
        exclusion_scope="mainline_block",
        cooldown_active=True,
        notes=notes,
    )


def registry_to_dict(entries: list[PostedThemeEntry]) -> dict[str, Any]:
    return {"entries": [asdict(e) for e in entries]}


def save_posted_theme_registry(entries: list[PostedThemeEntry], repo_root: Path | str, label: str | None = None) -> Path:
    repo_root = Path(repo_root)
    label = label or datetime.now().strftime("%Y-%m-%d")
    out_dir = repo_root / "ops" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"posted_theme_registry_{label}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(registry_to_dict(entries), f, ensure_ascii=False, indent=2)
    return out_path


def load_posted_theme_registry(path: str | Path) -> list[PostedThemeEntry]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [PostedThemeEntry(**e) for e in data.get("entries", [])]


def backfill_posted_theme_registry_from_reports_dir(
    reports_dir: str | Path, draft_texts_by_run_id: dict[str, dict[str, str]], source_full_texts_by_run_id: dict[str, str] | None = None
) -> list[PostedThemeEntry]:
    """ops/reports/配下のminimal_run_log_*.jsonをすべて走査し、実投稿済みのものだけから
    posted theme registryを再構築する。draft_texts_by_run_idは
    {run_id: {draft_id: draft_text}}の辞書（呼び出し側が既存run記録から用意する）。
    """
    reports_dir = Path(reports_dir)
    source_full_texts_by_run_id = source_full_texts_by_run_id or {}
    entries: list[PostedThemeEntry] = []
    for path in sorted(glob.glob(str(reports_dir / "minimal_run_log_*.json"))):
        log = json.loads(Path(path).read_text(encoding="utf-8"))
        run_id = log.get("run_id", "")
        draft_texts = draft_texts_by_run_id.get(run_id, {})
        entry = build_posted_theme_entry_from_minimal_run_log(
            log, draft_texts, source_full_text=source_full_texts_by_run_id.get(run_id),
            notes="backfilled from existing minimal_run_log",
        )
        if entry is not None:
            entries.append(entry)
    return entries


def _cooldown_still_active(published_at: str | None, cooldown_days: int = TOPIC_GROUP_COOLDOWN_DAYS) -> bool:
    if not published_at:
        return False
    try:
        published_date = datetime.strptime(published_at, "%Y-%m-%d").date()
    except ValueError:
        return False
    return (date.today() - published_date) <= timedelta(days=cooldown_days)


def check_posted_theme_guard(
    candidate_source_post_id: str | None,
    candidate_texts: list[str],
    target_layer: str | None,
    registry: list[PostedThemeEntry],
) -> dict[str, Any]:
    """mainline開始前ガード。candidate（sourceまたはdraft候補）を、posted theme registryと
    照合し、mainlineでblockすべきかを判定する。AIの重い意味判定には依存しない。

    判定優先順位: exact_source_match > high_theme_similarity > related_but_not_blocking > none
    """
    profile = build_theme_profile(candidate_texts)
    candidate_signature = profile["theme_signature"]
    candidate_topic_group = profile["topic_group"]
    candidate_components = profile["theme_components"]

    best_match_type = "none"
    best_entry: PostedThemeEntry | None = None
    best_overlap = 0.0
    cooldown_active = False

    for entry in registry:
        if target_layer and entry.target_layer and entry.target_layer != target_layer:
            continue

        if candidate_source_post_id and entry.source_post_id and candidate_source_post_id == entry.source_post_id:
            best_match_type = "exact_source_match"
            best_entry = entry
            best_overlap = 1.0
            break  # exact_source_matchが最優先。これ以上探す必要はない

        overlap = theme_component_overlap_ratio(candidate_components, entry.theme_key_terms)
        same_topic_group = candidate_topic_group == entry.topic_group and candidate_topic_group != "unclassified"

        if (overlap >= HIGH_SIMILARITY_THRESHOLD or (same_topic_group and overlap >= RELATED_THRESHOLD)):
            if overlap > best_overlap:
                best_match_type = "high_theme_similarity"
                best_entry = entry
                best_overlap = overlap
        elif overlap >= RELATED_THRESHOLD and best_match_type == "none":
            best_match_type = "related_but_not_blocking"
            best_entry = entry
            best_overlap = overlap

        if same_topic_group and _cooldown_still_active(entry.published_at):
            cooldown_active = True

    block_mainline = best_match_type in ("exact_source_match", "high_theme_similarity")
    route_to_research = block_mainline  # blockされた候補はresearch側で再検証してよい

    if best_entry is None:
        reason = "posted theme registryと一致する候補は見つからなかった。mainline候補として継続可能"
    elif best_match_type == "exact_source_match":
        reason = f"source_post_idが実投稿済みrun（{best_entry.run_id}、{best_entry.post_url}）と完全一致したためmainlineをblockする"
    elif best_match_type == "high_theme_similarity":
        reason = (
            f"theme_signature/構成要素の重なり（overlap_ratio={best_overlap:.2f}）が実投稿済みrun"
            f"（{best_entry.run_id}、{best_entry.post_url}）と高く、同一テーマとみなしmainlineをblockする"
        )
    else:
        reason = (
            f"実投稿済みrun（{best_entry.run_id}）と一部の要素が重なる（overlap_ratio={best_overlap:.2f}）が、"
            "block基準には達していないため、warningとして記録しmainlineは継続可能とする"
        )

    return {
        "posted_theme_check_status": "checked",
        "posted_theme_match_type": best_match_type,
        "matched_past_run_id": best_entry.run_id if best_entry else None,
        "matched_post_url": best_entry.post_url if best_entry else None,
        "matched_theme_signature": best_entry.theme_signature if best_entry else None,
        "block_mainline": block_mainline,
        "route_to_research": route_to_research,
        "cooldown_active": cooldown_active,
        "posted_theme_check_reason": reason,
        "candidate_theme_signature": candidate_signature,
        "candidate_topic_group": candidate_topic_group,
    }
