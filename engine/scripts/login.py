"""로그인 세션 준비 — 컴퓨터가 직접 수집할 수 있도록 한 번만 수동 로그인.

브라우저(영구 프로필)를 띄워서 네이버/X/인스타/페북/스레드 등에 사용자가 직접 로그인하면
세션이 프로필에 저장된다. 이후 BrowserCollector 가 그 세션으로 로그인 상태에서 수집한다.

실행(노트북, 직접):
    python -m engine.scripts.login
    python -m engine.scripts.login --sites naver x instagram

세션은 .env 의 BROWSER_PROFILE_DIR(기본 .browser_profile)에 저장된다.
"""
from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from ..config import get_settings

LOGIN_URLS = {
    "naver": "https://nid.naver.com/nidlogin.login",
    "x": "https://x.com/login",
    "instagram": "https://www.instagram.com/accounts/login/",
    "facebook": "https://www.facebook.com/login",
    "threads": "https://www.threads.net/login",
    "daum": "https://logins.daum.net/accounts/loginform.do",
}


async def run(sites: list[str]) -> None:
    s = get_settings()
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("playwright 미설치: pip install playwright; playwright install chromium")
        return

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            s.browser_profile_dir,
            headless=False,  # 사용자가 직접 로그인해야 하므로 항상 보이게
            locale="ko-KR",
            viewport={"width": 1280, "height": 900},
        )
        # 사이트별 로그인 페이지를 탭으로 연다
        for site in sites:
            url = LOGIN_URLS.get(site)
            if not url:
                logger.warning("알 수 없는 사이트: {}", site)
                continue
            page = await ctx.new_page()
            await page.goto(url)
            logger.info("[{}] 로그인 페이지 열림: {}", site, url)

        print(
            "\n────────────────────────────────────────────\n"
            "열린 탭에서 각 사이트에 로그인하세요.\n"
            "모두 로그인했으면 이 터미널에서 Enter 를 누르세요. (세션이 저장됩니다)\n"
            "────────────────────────────────────────────"
        )
        await asyncio.to_thread(input, "")
        await ctx.close()
        logger.info("세션 저장 완료 → {}", s.browser_profile_dir)


def main() -> None:
    p = argparse.ArgumentParser(description="로그인 세션 준비")
    p.add_argument(
        "--sites",
        nargs="*",
        default=["naver", "x", "instagram", "facebook", "threads"],
        help="로그인할 사이트 (naver x instagram facebook threads daum)",
    )
    args = p.parse_args()
    asyncio.run(run(args.sites))


if __name__ == "__main__":
    main()
