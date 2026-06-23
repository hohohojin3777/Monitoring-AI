"""target 에 회원/관리자 등록.

대시보드에서 가입(이메일/비번)한 사용자를 멤버로 추가하거나 권한을 바꾼다.
이메일로 Firebase Auth UID 를 찾아 members/{uid} 문서를 만든다.

실행:
    python -m engine.scripts.add_member --target minju-jeondaehoe --email user@x.com --role member
    python -m engine.scripts.add_member --target minju-jeondaehoe --email boss@x.com --role admin
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from loguru import logger

from ..store import FirestoreStore


def main() -> None:
    p = argparse.ArgumentParser(description="멤버 등록")
    p.add_argument("--target", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--role", choices=["admin", "member"], default="member")
    args = p.parse_args()

    store = FirestoreStore()
    db = store.connect()
    from firebase_admin import auth

    try:
        user = auth.get_user_by_email(args.email)
    except auth.UserNotFoundError:
        logger.error("계정 없음: {} — 대시보드에서 먼저 가입하거나 seed 로 생성하세요.", args.email)
        return

    (
        db.collection("targets")
        .document(args.target)
        .collection("members")
        .document(user.uid)
        .set(
            {
                "role": args.role,
                "email": args.email,
                "displayName": args.email.split("@")[0],
                "joinedAt": datetime.now(timezone.utc),
            },
            merge=True,
        )
    )
    logger.info("[add_member] {} → '{}' {} 등록 완료", args.email, args.target, args.role)


if __name__ == "__main__":
    main()
