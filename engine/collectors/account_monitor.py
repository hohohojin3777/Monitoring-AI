"""특정 계정 모니터링 수집기.

Firestore targets/{id}/watchAccounts 에 등록된 계정들의 최신 글을 직접 수집.
키워드 필터 없이 해당 인물이 올린 글 전체를 가져온다.

watchAccounts 구조 (Firestore array of map):
  [
    { platform: "facebook", accountId: "정청래의알콩달콩", url: "https://www.facebook.com/pages/...", label: "정청래" },
    { platform: "x",        accountId: "minseokKim",      url: "https://x.com/minseokKim",         label: "김민석" },
    { platform: "instagram",accountId: "jungcheonrae",    url: "https://www.instagram.com/jungcheonrae/", label: "정청래" },
    { platform: "threads",  accountId: "jungcheonrae",    url: "https://www.threads.net/@jungcheonrae",   label: "정청래" },
  ]
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from playwright.async_api import async_playwright

from .base import RawItem

# 플랫폼별 프로필 페이지 URL 패턴
_PROFILE_URLS: dict[str, str] = {
    "x":         "https://x.com/{accountId}",
    "instagram": "https://www.instagram.com/{accountId}/",
    "threads":   "https://www.threads.net/@{accountId}",
    "facebook":  "{url}",  # 페이지마다 URL이 달라서 url 직접 사용
}

# 플랫폼별 글 링크 패턴
_POST_PATTERNS: dict[str, str] = {
    "x":         r"/status/\d+",
    "instagram": r"/p/|/reel/",
    "threads":   r"/post/",
    "facebook":  r"/posts/|/permalink/|story_fbid|/videos/",
}


async def collect_watch_accounts(
    accounts: list[dict[str, Any]],
    profile_dir: str,
    limit_per_account: int = 20,
) -> list[RawItem]:
    """watchAccounts 목록을 순회하며 각 계정의 최신 글을 수집."""
    if not accounts:
        return []

    items: list[RawItem] = []
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            profile_dir,
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        page = await ctx.new_page()

        for acct in accounts:
            platform = acct.get("platform", "")
            account_id = acct.get("accountId", "")
            label = acct.get("label", account_id)
            direct_url = acct.get("url", "")

            if platform not in _POST_PATTERNS:
                logger.warning("[account_monitor] 지원하지 않는 플랫폼: {}", platform)
                continue

            # 프로필 페이지 URL 결정
            if platform == "facebook" and direct_url:
                profile_url = direct_url
            elif account_id:
                profile_url = _PROFILE_URLS[platform].format(accountId=account_id)
            else:
                logger.warning("[account_monitor] accountId 또는 url 없음: {}", acct)
                continue

            try:
                logger.info("[account_monitor] {} @{} 수집 중…", platform, label)
                await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

                # 글 링크 추출
                post_pattern = re.compile(_POST_PATTERNS[platform])
                links = await page.eval_on_selector_all(
                    "a[href]",
                    "els => els.map(e => e.href)"
                )
                post_urls = list(dict.fromkeys(
                    href for href in links
                    if post_pattern.search(href)
                    # X: 리트윗 제외 — 본인 계정 URL이 포함된 것만 (x.com/{accountId}/status/...)
                    and (platform != "x" or f"/{account_id.lower()}/" in href.lower())
                ))[:limit_per_account]

                logger.info("[account_monitor] {} @{} — 글 {}건 발견", platform, label, len(post_urls))

                for post_url in post_urls:
                    try:
                        await page.goto(post_url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(1500)

                        # 본문 텍스트 추출 (플랫폼별)
                        text = await _extract_text(page, platform)
                        if not text or len(text) < 10:
                            continue

                        items.append(RawItem(
                            platform=platform,
                            source_type="sns",
                            url=post_url,
                            title=f"[{label}] {text[:60]}",
                            content=text,
                            author=label,
                            author_id=account_id,
                            published_at=datetime.now(timezone.utc),
                            matched_entities=[label],
                            metrics={},
                            raw={"watch_account": True},
                        ))
                    except Exception as e:
                        logger.debug("[account_monitor] 글 수집 실패 {}: {}", post_url[:60], e)

            except Exception as e:
                logger.warning("[account_monitor] {} @{} 실패: {}", platform, label, e)

        await ctx.close()

    logger.info("[account_monitor] 총 {}건 수집", len(items))
    return items


async def _extract_text(page: Any, platform: str) -> str:
    """플랫폼별 본문 텍스트 추출."""
    selectors = {
        "x":         ['[data-testid="tweetText"]', 'article div[lang]'],
        "instagram": ['._a9zs', 'h1', '._aacl'],
        "threads":   ['[data-pressable-container]', 'span'],
        "facebook":  ['[data-ad-preview="message"]', '[data-testid="post_message"]',
                      'div[dir="auto"]'],
    }
    for sel in selectors.get(platform, []):
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                t = (await el.inner_text()).strip()
                if t:
                    return t
        except Exception:
            continue
    # fallback: body 텍스트 앞부분
    try:
        body = await page.locator("body").inner_text()
        return body[:500].strip()
    except Exception:
        return ""
