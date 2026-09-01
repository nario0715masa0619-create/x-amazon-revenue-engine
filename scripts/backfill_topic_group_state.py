"""backfill_topic_group_state（topic_group_stateの初期構築、read-only backfill）。

過去の`minimal_run_log_*.json`全件から、実際に発生したmainline runの内容を使って
topic_group_stateストアを初期構築する。既存ログ（minimal_run_log/enrichment_record/
post_analytics）は**読み取り専用**でアクセスし、一切書き換えない。mainline本体の
コードパス（scripts/post_generation_pipeline.pyのfinalize_minimal_run_log()等）とは
独立して実行可能——誤って本線run実行時にbackfillが混入することはない
（このスクリプトはCLIから明示的に実行するときのみ動く）。

minimal_run_logは「投稿時最小ログ」という設計上、draft/source本文を保持していない
（scripts/minimal_run_log.pyのMinimalRunLogにdraft_text/source_full_textフィールドは
存在しない）。そのためtheme_signature計算に必要な本文は、このスクリプトの呼び出し側が
`draft_texts_by_run_id`/`source_full_texts_by_run_id`として別途用意する必要がある
（scripts/posted_theme_registry.backfill_posted_theme_registry_from_reports_dir()と
同じ制約・同じ設計）。本文が用意できないrunはskipされ、backfill結果にその旨を記録する。

外部AI呼び出しは一切行わない。production scoring/Gate A/thresholds/shipping decision
には一切触れない。

設計文書: ops/reports/topic_group_lifecycle_design_2026-08-31.md
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any

from topic_dedupe import build_theme_profile
from topic_group_state import (
    TopicGroupState,
    get_or_create_topic_group,
    record_publication,
    record_topic_group_run_observed,
    update_performance_band,
    save_topic_group_state_store,
)


def backfill_topic_group_state_from_reports_dir(
    reports_dir: str | Path,
    draft_texts_by_run_id: dict[str, dict[str, str]],
    source_full_texts_by_run_id: dict[str, str] | None = None,
) -> dict[str, Any]:
    """ops/reports/配下のminimal_run_log_*.jsonを走査し（読み取り専用）、
    mainline_status=completedのrunからtopic_group_stateストアを構築する。

    戻り値: {"store": {topic_group_id: TopicGroupState}, "processed_run_ids": [...],
             "skipped_run_ids": [...]}（本文が用意できず処理できなかったrun）
    """
    reports_dir = Path(reports_dir)
    source_full_texts_by_run_id = source_full_texts_by_run_id or {}
    store: dict[str, TopicGroupState] = {}
    processed_run_ids: list[str] = []
    skipped_run_ids: list[str] = []

    for path in sorted(glob.glob(str(reports_dir / "minimal_run_log_*.json"))):
        # 読み取り専用: json.loadのみ、書き込み・変更は一切行わない
        log = json.loads(Path(path).read_text(encoding="utf-8"))
        if log.get("mainline_status") != "completed":
            continue

        run_id = log.get("run_id", "")
        human_selected_top = log.get("human_selected_top")
        draft_texts = draft_texts_by_run_id.get(run_id)
        if not draft_texts or not human_selected_top or human_selected_top not in draft_texts:
            skipped_run_ids.append(run_id)
            continue

        selected_text = draft_texts[human_selected_top]
        texts = [selected_text]
        source_text = source_full_texts_by_run_id.get(run_id)
        if source_text:
            texts.append(source_text)

        profile = build_theme_profile(texts)
        state = get_or_create_topic_group(store, profile["topic_group"], profile["theme_signature"])
        record_topic_group_run_observed(state)

        published_at = log.get("published_at")
        if published_at:
            record_publication(state, published_at=published_at)

        # post_analyticsが存在すればperformance_bandへ反映（読み取り専用）
        analytics_matches = glob.glob(str(reports_dir / f"post_analytics_*_{run_id}.json"))
        if analytics_matches:
            analytics = json.loads(Path(analytics_matches[0]).read_text(encoding="utf-8"))
            impression_count = (analytics.get("public_metrics") or {}).get("impression_count")
            update_performance_band(state, impression_count=impression_count)

        processed_run_ids.append(run_id)

    return {"store": store, "processed_run_ids": processed_run_ids, "skipped_run_ids": skipped_run_ids}


if __name__ == "__main__":
    # 実行例（このリポジトリの2026-08-31時点の既知run群）。
    # 新しいmainline runが積み重なった際は、ここへdraft本文を追記して再実行する
    # （minimal_run_logが本文を保持しない設計上の制約への対応。将来的にdraft本文を
    # 別途永続化する仕組みができれば、この手動辞書は不要にできる——次のfollow-up）。
    REPO = Path(__file__).resolve().parent.parent
    SOURCE_TEXT_ATH = (
        "RT @inno_pastime: オススメのネックバンド型ワイヤレス軟骨伝導ヘッドホン🎧\n"
        "マイク付きなのでヘッドセットになるのかな？\n軽量なのでジム用としても重宝してます。\n\n"
        "自宅用のヘッドホンもATH-PRO5MK2だったりと、\n地味にオーテクには足を向けて寝られなかったり…"
    )
    draft_texts_by_run_id = {
        "mainline-run-2026-08-29-001": {
            "gadget-mainline0829-G": "軽さ優先ならネックバンド型骨伝導、ジムではこれを使っている。自宅ではATH-PRO5MK2で、場面によって2本を使い分けている",
            "gadget-mainline0829-H": "ジム用はネックバンド型骨伝導。軽さでこれを選んだ。自宅ではATH-PRO5MK2を使っていて、用途ごとに使い分けている",
        },
        "mainline-run-2026-08-29-002": {
            "gadget-mainline0829b-I": "ジム用の骨伝導ネックバンドは軽さで選んだ。自宅ではATH-PRO5MK2を使っていて、場所で2本を使い分けている",
            "gadget-mainline0829b-J": "自宅ではATH-PRO5MK2、ジムでは骨伝導ネックバンド。軽さを優先したいジム用と、自宅用とで使い分けている",
        },
        "mainline-run-2026-08-30-003": {
            "gadget-mainline0830-K": "マイク付きで通話もできる骨伝導ネックバンドをジム用に、自宅ではATH-PRO5MK2を使う。用途ごとに2本を持っている",
            "gadget-mainline0830-L": "軽さ重視の骨伝導ネックバンドはジム用。自宅用は別でATH-PRO5MK2を使っていて、場面によって使い分けている",
        },
        "mainline-run-2026-08-30-004": {
            "gadget-mainline0830b-M": "ジムには骨伝導ネックバンド、自宅にはATH-PRO5MK2。軽さが要る場面と、そうでない場面で分けている",
            "gadget-mainline0830b-N": "自宅用はATH-PRO5MK2、ジム用は軽さ優先で骨伝導ネックバンド。マイクも付いているので通話にも使える",
        },
        "mainline-run-2026-08-30-005": {
            "gadget-mainline0830c-O": "ジム用は軽さで骨伝導ネックバンド、自宅用はATH-PRO5MK2。場面ごとに使い分けている",
            "gadget-mainline0830c-P": "自宅ではATH-PRO5MK2を使い、ジムでは軽さ重視の骨伝導ネックバンドにしている。用途で分けている",
        },
        "mainline-run-2026-08-30-006": {
            "gadget-mainline0830d-Q": "ジムでは軽さ優先の骨伝導ネックバンド、自宅ではATH-PRO5MK2。2本を場面ごとに使い分けている",
            "gadget-mainline0830d-R2": "ジム用は軽い骨伝導ネックバンド、自宅用はATH-PRO5MK2。マイクも付いていて、用途で2本を使い分けている",
        },
        "mainline-run-2026-08-30-007": {
            "gadget-mainline0830e-S": "軽さ重視のジム用は骨伝導ネックバンド、自宅用は別にATH-PRO5MK2。用途で分けて使っている",
            "gadget-mainline0830e-T": "自宅ではATH-PRO5MK2、ジムでは骨伝導ネックバンドと使い分けていて、軽さが要る場面で使い分けを意識している",
        },
    }
    source_full_texts_by_run_id = {rid: SOURCE_TEXT_ATH for rid in draft_texts_by_run_id}

    result = backfill_topic_group_state_from_reports_dir(
        reports_dir=REPO / "ops" / "reports",
        draft_texts_by_run_id=draft_texts_by_run_id,
        source_full_texts_by_run_id=source_full_texts_by_run_id,
    )
    print("processed_run_ids:", result["processed_run_ids"])
    print("skipped_run_ids:", result["skipped_run_ids"])
    for tgid, state in result["store"].items():
        print(f"  topic_group={tgid}: status={state.topic_status}, "
              f"performance_band={state.topic_performance_band}, "
              f"retired={state.topic_retired_from_mainline}, "
              f"cooldown_until={state.topic_cooldown_until}")

    # labelを固定日付でハードコードせず実行日を使う（再実行のたびに新しいスナップショットとして
    # 保存し、過去に保存済みのファイルを無断で上書きしない。2026-09-01: mainline_run_count
    # 集計対応でrecord_topic_group_run_observed()呼び出しを追加したための再実行分）。
    saved_path = save_topic_group_state_store(result["store"], REPO)
    print("saved to:", saved_path)
