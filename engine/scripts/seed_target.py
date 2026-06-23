"""1차 타깃(민주당 전당대회) 시드 생성 + (선택) 관리자 계정 생성.

실행:
    python -m engine.scripts.seed_target
    python -m engine.scripts.seed_target --admin-email you@example.com --admin-password '비밀번호'

--admin-* 를 주면 Firebase Auth 계정을 만들고 해당 target 의 admin 멤버로 등록한다.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from loguru import logger

from ..collectors.sites import DEFAULT_SITE_KEYS
from ..store import FirestoreStore

TARGET_ID = "minju-jeondaehoe"

TARGET_DOC = {
    "name": "민주당 전당대회",
    "description": "당대표 후보(김민석·정청래·김용민)·최고위원 후보·이재명 대통령 메시지 모니터링",
    "createdAt": datetime.now(timezone.utc),
    "keywords": [
        "민주당 전당대회", "전당대회", "당대표", "최고위원",
        "민주당 당대표 후보", "권리당원",
    ],
    "entities": [
        {"name": "김민석", "role": "당대표후보", "aliases": ["김민석 의원"]},
        {"name": "정청래", "role": "당대표후보", "aliases": ["정청래 의원"]},
        {"name": "김용민", "role": "당대표후보", "aliases": ["김용민 의원"]},
        {"name": "이재명", "role": "대통령", "aliases": ["이재명 대통령", "대통령실"]},
    ],
    "channels": [
        # {"platform":"youtube","label":"겸손은힘들다 김어준","url":"https://www.youtube.com/@..."},
    ],
    "sources": {
        "naver": True,
        "youtube": True,
        "rss": True,
        # 실접속 검증 완료 사이트만 기본 ON. 로그인 사이트(naver_cafe_login/x/instagram 등)와
        # 미검증 사이트(fmkorea/theqoo/instiz 등)는 login.py·튜닝 후 대시보드 설정에서 추가.
        "sites": DEFAULT_SITE_KEYS,
    },
    "schedule": {
        "collectEveryMin": 30,
        "reportDaily": "08:00",
        "reportWeekly": "mon 10:00",
    },
}


def seed(admin_email: str | None, admin_password: str | None) -> None:
    store = FirestoreStore()
    db = store.connect()

    ref = db.collection("targets").document(TARGET_ID)
    ref.set(TARGET_DOC, merge=True)
    logger.info("[seed] target '{}' 생성/갱신 완료", TARGET_ID)

    if admin_email and admin_password:
        from firebase_admin import auth

        try:
            user = auth.get_user_by_email(admin_email)
            logger.info("[seed] 기존 계정 사용: {}", admin_email)
        except auth.UserNotFoundError:
            user = auth.create_user(email=admin_email, password=admin_password)
            logger.info("[seed] 관리자 계정 생성: {}", admin_email)

        ref.collection("members").document(user.uid).set(
            {
                "role": "admin",
                "email": admin_email,
                "displayName": admin_email.split("@")[0],
                "joinedAt": datetime.now(timezone.utc),
            },
            merge=True,
        )
        logger.info("[seed] {} 를 '{}' 관리자로 등록", admin_email, TARGET_ID)
    else:
        logger.info(
            "[seed] 관리자 미지정. 대시보드 가입 후 add_member 로 등록하거나 "
            "--admin-email/--admin-password 로 다시 실행하세요."
        )


def main() -> None:
    p = argparse.ArgumentParser(description="전당대회 타깃 시드")
    p.add_argument("--admin-email")
    p.add_argument("--admin-password")
    args = p.parse_args()
    seed(args.admin_email, args.admin_password)


if __name__ == "__main__":
    main()
