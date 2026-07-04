"""SNS 로그인 세션 저장 스크립트 (최초 1회 실행).

실행:
    python -m engine.local_collectors.sns_login --platform x
    python -m engine.local_collectors.sns_login --platform facebook

브라우저가 열리면 직접 로그인하고 Enter 를 누르면 세션이 저장된다.
이후 sns_local_once.py 가 이 세션을 재사용한다.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.local_collectors.sns_collector import _DEFAULT_PROFILE

_URLS = {
    "x": "https://x.com/login",
    "facebook": "https://www.facebook.com/login",
    "instagram": "https://www.instagram.com/accounts/login/",
    "threads": "https://www.threads.net/login",
}


async def _login(platform: str, profile_dir: str) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("playwright 미설치: pip install playwright && playwright install chromium")
        return

    url = _URLS.get(platform)
    if not url:
        print(f"지원하지 않는 플랫폼: {platform}")
        return

    print(f"\n[{platform}] 로그인 창이 열립니다.")
    print("브라우저에서 직접 로그인한 후 여기서 Enter를 누르세요.")
    print(f"세션 저장 위치: {profile_dir}\n")

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            profile_dir,
            headless=False,
            locale="ko-KR",
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()
        await page.goto(url)

        # 사용자가 로그인 완료할 때까지 대기
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: input(f"[{platform}] 로그인 완료 후 Enter 입력: ")
        )

        await ctx.close()

    print(f"[{platform}] 세션 저장 완료. 이제 sns_local_once.py 를 실행하세요.")


def main() -> None:
    ap = argparse.ArgumentParser(description="SNS 로그인 세션 저장")
    ap.add_argument(
        "--platform", required=True,
        choices=["x", "facebook", "instagram", "threads"],
        help="로그인할 플랫폼",
    )
    ap.add_argument(
        "--profile-dir", default=_DEFAULT_PROFILE,
        help=f"세션 저장 디렉토리 (기본: {_DEFAULT_PROFILE})",
    )
    args = ap.parse_args()
    asyncio.run(_login(args.platform, args.profile_dir))


if __name__ == "__main__":
    main()
