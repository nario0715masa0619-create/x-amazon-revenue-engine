"""企業公式アカウントらしさを検出するpure function層（2026-09-04新設）。

背景: 集英社「LEE」編集部の公式アカウント（lee_shueisha）がteacher判定を通過し、
監視対象へ自動登録されてしまった実ケースを受けて追加した。模倣対象は個人の実践者
アカウントに限定する、という人間の運用方針に基づく。

方針（「疑わしきは人間確認へ」）: 誤って個人アカウントを排除するより、誤って企業
アカウントを一度通してしまう方が実害は小さい。そのため、判定材料が取得できない・
不十分な場合は"is_flagged=False"（＝通常どおり自動登録を継続）とし、明確な
positiveシグナル（verified_type==business/government、または表示名の法人・
メディア語一致）がある場合のみ"is_flagged=True"（＝人間確認へ回す）とする。

外部API呼び出しは一切行わない（本モジュールはpure functionのみ。X API呼び出しは
呼び出し元のregister_watched_accounts.pyの責務）。Gate A/thresholds/shipping
decision、_apply_engagement_gate()/_classify_core()本体には一切触れない
（このモジュールが対象とするのは「teacher判定を通過した後の、アカウント登録可否」
という後段の判定のみ）。
"""

from __future__ import annotations

from typing import Any

# X API GET /2/users のuser.fields=verified_typeで取得できる値のうち、
# 企業・組織アカウントを示すもの。個人アカウント（本プロジェクトの既存監視対象6件は
# 全件"blue"、実データで確認済み）はここに含めない。
COMPANY_VERIFIED_TYPES = ("business", "government")

# 表示名（name）に含まれる場合、企業・メディアアカウントらしさの予備シグナルとする
# 語。verified_typeが取得できない/blueでない場合の補助チェック。
CORPORATE_NAME_KEYWORDS = (
    "編集部", "公式", "株式会社", "合同会社", "公式アカウント",
    "Inc.", "Corp", "Official", "PR事務局",
)


def detect_company_account_signal(user_data: dict[str, Any] | None) -> dict[str, Any]:
    """X API GET /2/usersのdataオブジェクト（id/name/username/verified_type等）から、
    企業公式アカウントらしさのシグナルを判定する。

    user_dataがNone（API取得失敗・情報なし）の場合は、判定不能として
    is_flagged=Falseを返す（=通常どおり自動登録を継続する。取得失敗を理由に
    人間確認へ回すと、API障害のたびに個人アカウントまで止めてしまうため）。

    戻り値: {"is_flagged", "confidence"("high"|"low"|None), "reasons"(list[str]),
             "verified_type"}
    """
    if not user_data:
        return {"is_flagged": False, "confidence": None, "reasons": [], "verified_type": None}

    verified_type = user_data.get("verified_type")
    name = user_data.get("name") or ""

    reasons: list[str] = []
    if verified_type in COMPANY_VERIFIED_TYPES:
        reasons.append(f"verified_type={verified_type}")

    matched_keywords = [kw for kw in CORPORATE_NAME_KEYWORDS if kw in name]
    if matched_keywords:
        reasons.append(f"display_name_keyword_match={matched_keywords}")

    is_flagged = bool(reasons)
    if verified_type in COMPANY_VERIFIED_TYPES:
        confidence = "high"
    elif matched_keywords:
        confidence = "low"
    else:
        confidence = None

    return {
        "is_flagged": is_flagged,
        "confidence": confidence,
        "reasons": reasons,
        "verified_type": verified_type,
    }
