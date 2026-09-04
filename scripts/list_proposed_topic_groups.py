""""proposed"状態のtopic_group一覧を、人間が確認しやすい形で出力するCLI。

コンソール出力に加え、Markdownレポート（ops/reports/proposed_topic_groups_<日付>.md）を
生成する。読み取り専用（topic_group_stateの状態は一切変更しない）——昇格は
scripts/topic_group_state.py の promote_proposed_topic_group() を別途呼び出すこと
（本スクリプトでは行わない）。

使い方:
    python scripts/list_proposed_topic_groups.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from topic_group_state import list_proposed_topic_groups, load_topic_group_state_store
from topic_group_source_account_review import get_account_review_warning_for_topic_group

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOPIC_GROUP_STATE_PATH = _REPO_ROOT / "ops" / "reports" / "topic_group_state_2026-08-31.json"
_CUMULATIVE_JSONL_PATH = _REPO_ROOT / "ops" / "data" / "x_api_phase1_cumulative.jsonl"
_WATCHED_ACCOUNT_STATE_PATH = _REPO_ROOT / "ops" / "data" / "watched_account_state.json"


def main() -> None:
    store = load_topic_group_state_store(_TOPIC_GROUP_STATE_PATH)
    proposed = list_proposed_topic_groups(store)

    if not proposed:
        print("proposed状態のtopic_groupはありません。")
        return

    print(f"proposed状態のtopic_group: {len(proposed)}件\n")
    lines = [
        "# proposed状態のtopic_group一覧",
        "",
        f"生成日時: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "人間が内容を確認し、mainlineの候補として妥当と判断したもののみ、",
        "`promote_proposed_topic_group(store, topic_group_id)` で\"active\"へ昇格させること。",
        "昇格するまでは、既存の`passes_mainline_candidate_filter()`により",
        "mainlineの候補生成には一切現れない。",
        "",
        "| topic_group_id | theme_signature | source_diversity_tag | 登録日時 | 投稿者に関する注意 |",
        "|---|---|---|---|---|",
    ]
    for s in proposed:
        warning = get_account_review_warning_for_topic_group(
            s.source_diversity_tag, _CUMULATIVE_JSONL_PATH, _WATCHED_ACCOUNT_STATE_PATH
        )
        print(f"- topic_group_id={s.topic_group_id!r}")
        print(f"  theme_signature={s.theme_signature!r}")
        print(f"  source_diversity_tag={s.source_diversity_tag!r}  created_at={s.created_at}")
        if warning:
            print(f"  {warning}")
        lines.append(
            f"| `{s.topic_group_id}` | `{s.theme_signature}` | {s.source_diversity_tag or '-'} | "
            f"{s.created_at} | {warning or '-'} |"
        )

    out_path = _REPO_ROOT / "ops" / "reports" / f"proposed_topic_groups_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nMarkdownレポート保存先: {out_path}")


if __name__ == "__main__":
    main()
