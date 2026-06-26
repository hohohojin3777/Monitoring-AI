"""계정 직접 모니터링 수집기.

watch_targets.py 의 타깃 목록을 순회하며 Facebook / X / YouTube(브라우저) 최신 글을 수집.

수집 전략:
  - 계정 기반 직접 모니터링 70%
  - dedupeKey = "{platform}:{sourceId}" 로 중복 차단
  - tier S=60분, A=120분 주기 (pipeline 에서 lastCollectedAt 비교)
  - 실패 시 status / lastError / nextRetryAt 저장, 무리한 재시도 없음
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger
from playwright.async_api import async_playwright, Page

from .base import RawItem

# ── 플랫폼별 포스트 링크 패턴 ─────────────────────────────────
_POST_RE: dict[str, re.Pattern] = {
    "facebook": re.compile(r"/posts/|/permalink/|story_fbid|pfbid|/videos/\d+"),
    "x":        re.compile(r"/status/\d+"),
    "youtube":  re.compile(r"/watch\?v=|/shorts/"),
}

# ── X 노이즈 필터 ────────────────────────────────────────────
_X_NOISE = {"Don't miss what's happening", "Sign in", "Log in"}


# ── dedupeKey ────────────────────────────────────────────────
def make_dedupe_key(platform: str, source_id: str) -> str:
    raw = f"{platform}:{source_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _source_id_from_url(platform: str, url: str) -> str:
    """URL에서 플랫폼별 고유 ID 추출."""
    if platform == "x":
        m = re.search(r"/status/(\d+)", url)
        return m.group(1) if m else url
    if platform == "facebook":
        for pat in [r"pfbid(\w+)", r"/posts/(\d+)", r"story_fbid=(\d+)"]:
            m = re.search(pat, url)
            if m:
                return m.group(1)
        return url
    if platform == "youtube":
        m = re.search(r"[?&]v=([^&]+)", url) or re.search(r"/shorts/([^/?]+)", url)
        return m.group(1) if m else url
    return url


# ── 플랫폼별 텍스트 추출 ──────────────────────────────────────
async def _extract_text(page: Page, platform: str) -> str:
    selectors: dict[str, list[str]] = {
        "x":        ['[data-testid="tweetText"]', "article div[lang]"],
        "facebook": ["[data-ad-preview='message']", "[data-testid='post_message']", "div[dir='auto']"],
        "youtube":  ["#description-inner", "#description", "yt-formatted-string#content"],
    }
    for sel in selectors.get(platform, []):
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                t = (await el.inner_text()).strip()
                if t and len(t) >= 10:
                    return t
        except Exception:
            continue
    try:
        body = await page.locator("body").inner_text()
        return body[:500].strip()
    except Exception:
        return ""


# ── YouTube 브라우저 채널 수집 ────────────────────────────────
async def _collect_youtube_browser(page: Page, handle: str, limit: int = 10) -> list[dict]:
    """YouTube 채널 핸들(@handle)의 최신 영상 목록을 브라우저로 수집.
    ytInitialData JSON 파싱 → API 키 불필요.
    """
    url = f"https://www.youtube.com/{handle}/videos"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        content = await page.content()
        # ytInitialData JSON 추출
        m = re.search(r"var ytInitialData\s*=\s*(\{.+?\});\s*</script>", content, re.DOTALL)
        if not m:
            logger.debug("[yt_browser] ytInitialData 없음: {}", handle)
            return []
        data = json.loads(m.group(1))
        # 영상 렌더러 찾기
        videos: list[dict] = []
        try:
            tabs = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
            for tab in tabs:
                content_tab = tab.get("tabRenderer", {})
                if content_tab.get("title") not in ("Videos", "동영상"):
                    continue
                items = (content_tab.get("content", {})
                         .get("richGridRenderer", {})
                         .get("contents", []))
                for item in items[:limit]:
                    vr = (item.get("richItemRenderer", {})
                          .get("content", {})
                          .get("videoRenderer", {}))
                    if not vr:
                        continue
                    vid_id = vr.get("videoId", "")
                    title_runs = vr.get("title", {}).get("runs", [])
                    title = "".join(r.get("text", "") for r in title_runs)
                    views_text = (vr.get("viewCountText", {}).get("simpleText", "")
                                  or vr.get("viewCountText", {}).get("runs", [{}])[0].get("text", ""))
                    pub_text = vr.get("publishedTimeText", {}).get("simpleText", "")
                    if vid_id and title:
                        videos.append({
                            "videoId": vid_id,
                            "title": title,
                            "url": f"https://www.youtube.com/watch?v={vid_id}",
                            "views": views_text,
                            "publishedTimeText": pub_text,
                        })
        except (KeyError, IndexError, TypeError):
            pass
        return videos
    except Exception as e:
        logger.debug("[yt_browser] {} 수집 실패: {}", handle, e)
        return []


# ── 메인 수집 함수 ────────────────────────────────────────────
async def collect_watch_accounts(
    accounts: list[dict[str, Any]],
    profile_dir: str,
    limit_per_account: int = 10,
) -> list[RawItem]:
    """레거시 호환용 — watch_targets 없이 accounts 리스트로 직접 수집."""
    # watch_targets 포맷으로 변환
    targets = []
    for a in accounts:
        platform = a.get("platform", "")
        url = a.get("url", "")
        account_id = a.get("accountId", "")
        label = a.get("label", account_id)
        if platform and url:
            targets.append({
                "name": label,
                "tier": "S",
                "crawlIntervalMinutes": 60,
                "platforms": {
                    platform: {"url": url, "accountId": account_id}
                },
            })
    return await collect_targets(targets, profile_dir, limit_per_account=limit_per_account)


async def collect_targets(
    targets: list[dict],
    profile_dir: str,
    limit_per_account: int = 10,
    since: datetime | None = None,
) -> list[RawItem]:
    """watch_targets 포맷의 타깃 리스트를 수집."""
    if not targets:
        return []
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(hours=24)

    all_items: list[RawItem] = []

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            profile_dir,
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        )
        page = await ctx.new_page()

        for target in targets:
            name = target.get("name", "")
            platforms = target.get("platforms", {})
            relation = target.get("relationCandidate", "확인 필요")

            for platform, pconf in platforms.items():
                if platform not in _POST_RE:
                    continue
                items = await _collect_platform(
                    page=page,
                    platform=platform,
                    name=name,
                    pconf=pconf,
                    limit=limit_per_account,
                    relation=relation,
                )
                all_items.extend(items)

        await ctx.close()

    logger.info("[account_monitor] 총 {}건 수집 (타깃 {}개)", len(all_items), len(targets))
    return all_items


async def _collect_platform(
    page: Page,
    platform: str,
    name: str,
    pconf: dict,
    limit: int,
    relation: str,
) -> list[RawItem]:
    """단일 플랫폼·계정 수집."""

    # ── YouTube: 브라우저로 채널 Videos 탭 직접 파싱 ──────────
    if platform == "youtube":
        handle = pconf.get("handle", "")
        if not handle:
            return []
        logger.info("[account_monitor] youtube {} 수집 중…", name)
        videos = await _collect_youtube_browser(page, handle, limit=limit)
        items = []
        for v in videos:
            source_id = v["videoId"]
            items.append(RawItem(
                platform="youtube",
                source_type="video",
                url=v["url"],
                title=v["title"],
                content=v.get("views", ""),
                author=name,
                author_id=handle,
                published_at=datetime.now(timezone.utc),  # 정확한 시각 없음 — 상대시각만 있음
                matched_entities=[name],
                raw={
                    "dedupeKey": make_dedupe_key("youtube", source_id),
                    "sourceId": source_id,
                    "contentType": "video",
                    "authorHandle": handle,
                    "authorName": name,
                    "relationCandidate": relation,
                    "publishedTimeText": v.get("publishedTimeText", ""),
                },
            ))
        logger.info("[account_monitor] youtube {} — {}건", name, len(items))
        return items

    # ── Facebook / X: 프로필 페이지 → 포스트 링크 → 본문 수집 ─
    url = pconf.get("url", "")
    account_id = pconf.get("accountId", "")
    if not url:
        return []

    try:
        logger.info("[account_monitor] {} @{} 수집 중…", platform, name)
        # Facebook은 타임라인 탭 직접
        if platform == "facebook":
            goto_url = url.rstrip("/") + "?sk=timeline"
        else:
            goto_url = url
        await page.goto(goto_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.6)")
        await page.wait_for_timeout(2000)

        # 포스트 링크 수집
        post_pattern = _POST_RE[platform]
        links: list[str] = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        post_urls = list(dict.fromkeys(
            href for href in links
            if post_pattern.search(href)
            and (platform != "x" or f"/{account_id.lower()}/" in href.lower())
        ))[:limit]

        logger.info("[account_monitor] {} @{} — 링크 {}건 발견", platform, name, len(post_urls))

        items: list[RawItem] = []
        for post_url in post_urls:
            try:
                await page.goto(post_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(1500)
                text = await _extract_text(page, platform)
                # 노이즈 필터
                if not text or len(text) < 10:
                    continue
                if any(noise in text for noise in _X_NOISE):
                    continue
                source_id = _source_id_from_url(platform, post_url)
                dedupe_key = make_dedupe_key(platform, source_id)
                items.append(RawItem(
                    platform=platform,
                    source_type="sns",
                    url=post_url,
                    title=f"[{name}] {text[:60]}",
                    content=text,
                    author=name,
                    author_id=account_id,
                    published_at=datetime.now(timezone.utc),
                    matched_entities=[name],
                    raw={
                        "dedupeKey": dedupe_key,
                        "sourceId": source_id,
                        "contentType": "post" if platform == "facebook" else "tweet",
                        "authorHandle": account_id,
                        "authorName": name,
                        "relationCandidate": relation,
                        "analysisStatus": "raw",
                    },
                ))
            except Exception as e:
                logger.debug("[account_monitor] 포스트 수집 실패 {}: {}", post_url[:60], e)

        logger.info("[account_monitor] {} @{} — {}건 수집 완료", platform, name, len(items))
        return items

    except Exception as e:
        logger.warning("[account_monitor] {} @{} 실패: {}", platform, name, e)
        return []
