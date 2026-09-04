"""proposed状態のtopic_groupを、人間が対話的に昇格・却下するためのCLI。

引数なし: 現在"proposed"状態の全topic_groupを番号付きで一覧表示する
    （list_proposed_topic_groups.pyと同じlist_proposed_topic_groups()を再利用、
    フィルタ・整列ロジックの重複実装はしない）。
<topic_group_id>: 指定したtopic_groupを"active"へ昇格する（y/n確認を挟む）。
<topic_group_id> --reject: 指定したtopic_groupを却下し、以後候補プールに出ない
    "retired"状態へ遷移させる（y/n確認を挟む）。
--yes: 確認をスキップする（デフォルトは必ず確認を挟む、誤操作防止）。

昇格・却下そのものは、既存のpromote_proposed_topic_group()/
reject_proposed_topic_group()（topic_group_state.py）をそのまま呼び出すだけで、
新規の判定ロジックは一切追加していない。Gate A/thresholds/shipping decision、
teacher判定・抽出ロジック本体、既存の日次・深掘りワークフロー本体には一切触れない。

使い方:
    python scripts/promote_topic_group.py
    python scripts/promote_topic_group.py <topic_group_id>
    python scripts/promote_topic_group.py <topic_group_id> --reject
    python scripts/promote_topic_group.py <topic_group_id> --yes
    python scripts/promote_topic_group.py <topic_group_id> --reject --yes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from topic_group_state import (
    TopicGroupState,
    TopicGroupStateError,
    list_proposed_topic_groups,
    load_topic_group_state_store,
    promote_proposed_topic_group,
    reject_proposed_topic_group,
    save_topic_group_state_store,
)
from topic_group_source_account_review import get_account_review_warning_for_topic_group

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOPIC_GROUP_STATE_PATH = _REPO_ROOT / "ops" / "reports" / "topic_group_state_2026-08-31.json"
_CUMULATIVE_JSONL_PATH = _REPO_ROOT / "ops" / "data" / "x_api_phase1_cumulative.jsonl"
_WATCHED_ACCOUNT_STATE_PATH = _REPO_ROOT / "ops" / "data" / "watched_account_state.json"


def print_numbered_proposed_list(proposed: list[TopicGroupState]) -> None:
    if not proposed:
        print("現在proposed状態のtopic_groupはありません。")
        return
    print(f"proposed状態のtopic_group: {len(proposed)}件\n")
    for i, s in enumerate(proposed, start=1):
        print(f"[{i}] topic_group_id={s.topic_group_id!r}")
        print(f"    theme_signature={s.theme_signature!r}")
        print(f"    元になったteacher投稿のpost_id(source_diversity_tag)={s.source_diversity_tag!r}")
        print(f"    登録日時={s.created_at}")
        warning = get_account_review_warning_for_topic_group(
            s.source_diversity_tag, _CUMULATIVE_JSONL_PATH, _WATCHED_ACCOUNT_STATE_PATH
        )
        if warning:
            print(f"    {warning}")


def resolve_proposed_target(store: dict[str, TopicGroupState], topic_group_id: str) -> TopicGroupState:
    """topic_group_idの存在確認 + "proposed"状態であることの確認。

    問題があればTopicGroupStateErrorを送出する（呼び出し側で捕捉し、
    現在のproposed一覧を添えてエラー表示することを想定）。
    """
    if topic_group_id not in store:
        raise TopicGroupStateError(f"topic_group_id={topic_group_id!r} は存在しません。")
    state = store[topic_group_id]
    if state.topic_status != "proposed":
        raise TopicGroupStateError(
            f"topic_group_id={topic_group_id!r} はtopic_status={state.topic_status!r}であり、"
            "'proposed'ではないため昇格/却下できません。"
        )
    return state


def apply_promote_or_reject(
    store: dict[str, TopicGroupState], topic_group_id: str, reject: bool
) -> TopicGroupState:
    """確認は呼び出し側（main）の責務。ここでは既存のpromote_proposed_topic_group()/
    reject_proposed_topic_group()（topic_group_state.py、無変更）をそのまま呼ぶだけで、
    新規の判定ロジックは一切持たない。
    """
    if reject:
        return reject_proposed_topic_group(store, topic_group_id)
    return promote_proposed_topic_group(store, topic_group_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="proposedトピックグループの昇格/却下CLI")
    parser.add_argument("topic_group_id", nargs="?", default=None, help="対象のtopic_group_id（省略時は一覧表示のみ）")
    parser.add_argument("--reject", action="store_true", help="昇格ではなく却下（'retired'へ遷移）する")
    parser.add_argument("--yes", action="store_true", help="確認プロンプトをスキップする")
    args = parser.parse_args()

    store = load_topic_group_state_store(_TOPIC_GROUP_STATE_PATH)
    proposed = list_proposed_topic_groups(store)

    if args.topic_group_id is None:
        print_numbered_proposed_list(proposed)
        return

    try:
        state = resolve_proposed_target(store, args.topic_group_id)
    except TopicGroupStateError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        print(file=sys.stderr)
        print_numbered_proposed_list(proposed)
        sys.exit(1)

    action_label = "却下（'retired'へ遷移、以後候補プールに出ません）" if args.reject else "昇格（'active'へ遷移）"
    print(f"対象: topic_group_id={state.topic_group_id!r}")
    print(f"theme_signature={state.theme_signature!r}")
    print(f"元になったteacher投稿のpost_id(source_diversity_tag)={state.source_diversity_tag!r}")
    warning = get_account_review_warning_for_topic_group(
        state.source_diversity_tag, _CUMULATIVE_JSONL_PATH, _WATCHED_ACCOUNT_STATE_PATH
    )
    if warning:
        print(warning)
    print(f"実施する操作: {action_label}")

    if not args.yes:
        answer = input(f"\n{action_label}を実行しますか？ [y/N]: ").strip().lower()
        if answer != "y":
            print("キャンセルしました。何も変更していません。")
            return

    apply_promote_or_reject(store, args.topic_group_id, reject=args.reject)
    save_topic_group_state_store(store, _REPO_ROOT, label="2026-08-31")
    print(f"\n完了: topic_group_id={args.topic_group_id!r} を{action_label}しました。")


if __name__ == "__main__":
    main()
