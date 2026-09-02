"""広域/日次キーワード収集経路のpre_teacher_candidateから、topic_groupを自動抽出し
"proposed"状態で登録するCLI。

x_api_phase2_classify.pyが出力した outputs/x_api_phase2/pre_teacher_candidate.json
（本文=textを含む、Phase 2出力はプライバシー方針によりcommit対象外だが本文自体は
保持している）を**読み取り専用で参照するだけ**の独立した後段ステップ
（register_watched_accounts.pyと同じ設計パターン）。同一job・同一runner内で、
Phase 2分類の直後・本文がまだ存在するタイミングで実行する必要がある
（outputs/x_api_phase2/はジョブをまたいで永続化されないため）。

_apply_engagement_gate()/_classify_core()本体、topic_groupの既存ライフサイクル関数
（record_mainline_attempt等）・候補フィルタ（passes_mainline_candidate_filter）には
一切手を入れない（importも呼び出しも行わない）。

使い方:
    python scripts/extract_topic_groups_from_teachers.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from teacher_theme_extraction import register_proposed_topic_group_from_teacher_post
from topic_group_state import load_topic_group_state_store, save_topic_group_state_store

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PRE_TEACHER_CANDIDATE_PATH = _REPO_ROOT / "outputs" / "x_api_phase2" / "pre_teacher_candidate.json"
# post_generation_pipeline.py の _DEFAULT_TOPIC_GROUP_STATE_PATH と同一パスを指す
# （重い依存を避けるため、post_generation_pipeline.py本体はimportせずパス文字列のみ
# 複製している。変更する場合は両方を同時に更新すること）。
_TOPIC_GROUP_STATE_PATH = _REPO_ROOT / "ops" / "reports" / "topic_group_state_2026-08-31.json"


def main() -> None:
    if not _PRE_TEACHER_CANDIDATE_PATH.exists():
        print(
            f"警告: {_PRE_TEACHER_CANDIDATE_PATH} が見つかりません。抽出は行いません。",
            file=sys.stderr,
        )
        sys.exit(1)

    records = json.loads(_PRE_TEACHER_CANDIDATE_PATH.read_text(encoding="utf-8"))
    store = load_topic_group_state_store(_TOPIC_GROUP_STATE_PATH)

    newly_proposed: list[str] = []
    already_known: list[str] = []
    unclassified_count = 0

    for record in records:
        text = record.get("text")
        if not text:
            continue
        source_tag = record.get("post_id")
        result = register_proposed_topic_group_from_teacher_post(store, text, source_diversity_tag=source_tag)
        if result is None:
            unclassified_count += 1
            continue
        state, profile = result
        if state.topic_group_id in newly_proposed or state.topic_group_id in already_known:
            continue
        # get_or_create_topic_group()は既存なら上書きしないため、直前のcreated_at==updated_at
        # かどうかで「今回新規作成されたか」を判定する（新規作成時のみ created_at==updated_at）。
        if state.created_at == state.updated_at and state.topic_status == "proposed":
            newly_proposed.append(state.topic_group_id)
        else:
            already_known.append(state.topic_group_id)

    # save_topic_group_state_store()はデフォルトで今日の日付をファイル名に使う（既存仕様）。
    # post_generation_pipeline.py側が参照するcanonicalパス（_DEFAULT_TOPIC_GROUP_STATE_PATH
    # と同一ファイル名）へ明示的にlabelを指定して書き戻す。
    save_topic_group_state_store(store, _REPO_ROOT, label="2026-08-31")

    print(f"pre_teacher_candidate件数: {len(records)}件")
    print(f"新規proposed登録: {len(newly_proposed)}件 {newly_proposed}")
    print(f"既存topic_groupとして合流（新規作成なし）: {len(already_known)}件")
    print(f"抽出不能（unclassified）: {unclassified_count}件")
    print(f"保存先: {_TOPIC_GROUP_STATE_PATH}")


if __name__ == "__main__":
    main()
