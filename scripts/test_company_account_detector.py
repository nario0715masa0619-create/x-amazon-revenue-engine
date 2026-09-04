"""company_account_detector.py / watched_account_state.py 企業アカウント除外機能の
検証スクリプト。

pytest等の外部テストランナーには依存せず、このリポジトリの既存スタイルに合わせ、
`python scripts/test_company_account_detector.py`で直接実行できるplain assert
ベースの検証スクリプトとする。

回帰確認用の実データ: 2026-09-04にX API GET /2/users（user.fields=verified_type,name）
で実際に取得した、既存の監視対象個人アカウント6件（全件verified_type="blue"）と、
lee_shueisha（企業公式、verified_type="business"）の応答をそのまま固定フィクスチャ
として使う（scratchpad/phase0_verified_type_result.jsonより）。

外部API呼び出しは一切行わない。Gate A/thresholds/shipping decision、
_apply_engagement_gate()/_classify_core()本体には一切触れない。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from company_account_detector import detect_company_account_signal
from watched_account_state import (
    WatchedAccountState,
    active_author_ids,
    create_pending_review_watched_account,
    exclude_watched_account,
    register_or_reactivate_watched_account,
)

_FAILURES: list[str] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        _FAILURES.append(name)


# 2026-09-04実データ（scratchpad/phase0_verified_type_result.jsonより）。
_LEE_SHUEISHA_USER_DATA = {
    "id": "551019339",
    "name": "LEE編集部",
    "username": "lee_shueisha",
    "verified": True,
    "verified_type": "business",
}

_REAL_INDIVIDUAL_ACCOUNTS_USER_DATA = [
    {"id": "765724766502170624", "name": "𝑎𝑚𝑖｜ファッションコンサルタントNo.1｜業界初『触れずに、変える』", "username": "st_r0817", "verified": True, "verified_type": "blue"},
    {"id": "812466877184126977", "name": "Daisuke | 人生を変える男磨きコンサル", "username": "Daisuke__otoko", "verified": True, "verified_type": "blue"},
    {"id": "720220197668278273", "name": "やま", "username": "fukunokioku", "verified": True, "verified_type": "blue"},
    {"id": "756768794513584128", "name": "ようへい|30代の外見×モテ", "username": "ikaretemitai", "verified": True, "verified_type": "blue"},
    {"id": "55126678", "name": "大山シュン｜大人のファッション専門家", "username": "shun_4colors", "verified": True, "verified_type": "blue"},
    {"id": "4068452893", "name": "さっさん", "username": "SASSAN99999", "verified": True, "verified_type": "blue"},
]


def test_lee_shueisha_flagged_by_verified_type() -> None:
    print("\n=== 検証1: lee_shueisha（verified_type=business）がis_flagged=Trueになること ===")
    signal = detect_company_account_signal(_LEE_SHUEISHA_USER_DATA)
    _check("is_flagged_true", signal["is_flagged"] is True, str(signal))
    _check("confidence_high", signal["confidence"] == "high", signal["confidence"])
    _check("verified_type_business", signal["verified_type"] == "business")
    _check("reason_mentions_verified_type", any("verified_type=business" in r for r in signal["reasons"]))


def test_real_individual_accounts_not_flagged() -> None:
    print("\n=== 検証2: 実データの既存個人アカウント6件が誤ってis_flagged=Trueにならないこと（回帰確認） ===")
    for user_data in _REAL_INDIVIDUAL_ACCOUNTS_USER_DATA:
        signal = detect_company_account_signal(user_data)
        _check(
            f"not_flagged_{user_data['username']}",
            signal["is_flagged"] is False,
            f"verified_type={user_data['verified_type']} name={user_data['name']!r} signal={signal}",
        )


def test_display_name_keyword_fallback() -> None:
    print("\n=== 検証3: verified_typeがblueでも表示名に法人語があればlow confidenceで検出されること ===")
    user_data = {"id": "999", "name": "サンプル株式会社【公式】", "username": "sample_official", "verified_type": "blue"}
    signal = detect_company_account_signal(user_data)
    _check("is_flagged_true", signal["is_flagged"] is True, str(signal))
    _check("confidence_low", signal["confidence"] == "low", signal["confidence"])


def test_missing_user_data_not_flagged() -> None:
    print("\n=== 検証4: user_data取得失敗（None）の場合はis_flagged=False（通常登録継続）になること ===")
    signal = detect_company_account_signal(None)
    _check("is_flagged_false", signal["is_flagged"] is False, str(signal))
    _check("confidence_none", signal["confidence"] is None)


def test_pending_review_account_excluded_from_active_author_ids() -> None:
    print("\n=== 検証5: pending_review状態のアカウントがactive_author_ids()から除外されること ===")
    store: dict[str, WatchedAccountState] = {}
    register_or_reactivate_watched_account(store, "author-individual", observed_at="2026-09-04T00:00:00Z")
    create_pending_review_watched_account(
        store, "author-company", reason="verified_type=business", detected_at="2026-09-04T00:00:00Z"
    )
    targets = active_author_ids(store)
    _check("only_individual_active", targets == ["author-individual"], str(targets))
    _check("company_status_is_pending_review", store["author-company"].watch_status == "pending_review")


def test_pending_review_not_reactivated_by_register() -> None:
    print("\n=== 検証6: pending_review状態のアカウントがregister_or_reactivate_watched_account()で復帰しないこと ===")
    store: dict[str, WatchedAccountState] = {}
    create_pending_review_watched_account(
        store, "author-company", reason="verified_type=business", detected_at="2026-09-04T00:00:00Z"
    )
    result = register_or_reactivate_watched_account(store, "author-company", observed_at="2026-09-05T00:00:00Z")
    _check("still_pending_review", result.watch_status == "pending_review", result.watch_status)


def test_excluded_account_not_reactivated_by_register() -> None:
    print("\n=== 検証7: excluded状態のアカウントがregister_or_reactivate_watched_account()で復帰しないこと ===")
    store: dict[str, WatchedAccountState] = {}
    state = register_or_reactivate_watched_account(store, "author-1", observed_at="2026-09-01T00:00:00Z")
    exclude_watched_account(state, reason="企業公式アカウントのため", excluded_at="2026-09-02T00:00:00Z")
    _check("excluded_status_set", state.watch_status == "excluded")

    result = register_or_reactivate_watched_account(store, "author-1", observed_at="2026-09-04T00:00:00Z")
    _check("still_excluded", result.watch_status == "excluded", result.watch_status)
    _check("excluded_reason_preserved", result.excluded_reason == "企業公式アカウントのため")


def test_excluded_account_from_graduated_stays_excluded() -> None:
    print("\n=== 検証8: graduated状態からでもexclude_watched_account()でexcludedへ遷移できること ===")
    store: dict[str, WatchedAccountState] = {}
    state = register_or_reactivate_watched_account(store, "author-1", observed_at="2026-09-01T00:00:00Z")
    state.watch_status = "graduated"
    exclude_watched_account(state, reason="企業公式アカウントのため")
    _check("excluded_status_set", state.watch_status == "excluded")
    _check("active_author_ids_excludes_it", active_author_ids(store) == [])


def test_lee_shueisha_real_case_end_to_end() -> None:
    print("\n=== 検証9: lee_shueisha実ケースのエンドツーエンド（検出→pending_review作成→除外） ===")
    store: dict[str, WatchedAccountState] = {}
    signal = detect_company_account_signal(_LEE_SHUEISHA_USER_DATA)
    _check("detected_as_flagged", signal["is_flagged"] is True)

    reason = "; ".join(signal["reasons"])
    create_pending_review_watched_account(store, "551019339", reason=reason, detected_at="2026-09-03T23:05:40Z")
    _check("pending_review_created", store["551019339"].watch_status == "pending_review")

    exclude_watched_account(store["551019339"], reason="企業公式アカウントのため人間判断により除外", excluded_at="2026-09-04T00:52:26Z")
    _check("final_status_excluded", store["551019339"].watch_status == "excluded")
    _check("active_author_ids_excludes_lee_shueisha", "551019339" not in active_author_ids(store))


if __name__ == "__main__":
    test_lee_shueisha_flagged_by_verified_type()
    test_real_individual_accounts_not_flagged()
    test_display_name_keyword_fallback()
    test_missing_user_data_not_flagged()
    test_pending_review_account_excluded_from_active_author_ids()
    test_pending_review_not_reactivated_by_register()
    test_excluded_account_not_reactivated_by_register()
    test_excluded_account_from_graduated_stays_excluded()
    test_lee_shueisha_real_case_end_to_end()

    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} check(s) failed: {_FAILURES}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)
