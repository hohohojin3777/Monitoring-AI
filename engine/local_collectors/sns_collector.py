"""MacBook 로컬 SNS 수집기 — X(트위터)·Facebook 로그인 세션 기반.

실행 전제:
  1. engine/scripts/login.py 로 X/Facebook 최초 로그인 완료
  2. 세션이 .browser_profile_sns/ 에 저장됨
  3. MacBook에서만 실행 — DigitalOcean 파이프라인과 독립

안전 원칙:
  - 로그인 요구·CAPTCHA·차단 화면 감지 시 즉시 중단 (우회 없음)
  - 짧은 수집 (사이트당 키워드당 최대 20건)
  - 중복 URL은 Firestore recent_item_ids 체크로 제외
  - 수집 실패해도 전체 파이프라인에 영향 없음 (독립 프로세스)
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from loguru import logger

from ..candidates import ALL_CANDIDATE_NAMES
from ..collectors.base import RawItem
from ..collectors.dateparse import parse_korean_date

# 프로필 디렉토리 (login.py 와 별도 — SNS 전용)
_DEFAULT_PROFILE = str(Path(__file__).parent.parent / ".browser_profile_sns")

# 차단/로그인 감지 패턴
_BLOCKED_URL_RE = re.compile(
    r"/(login|signin|accounts/login|checkpoint|challenge|captcha|auth/flow)",
    re.IGNORECASE,
)
_BLOCKED_TEXT_RE = re.compile(
    r"로그인이 필요|로그인하여|sign in to|log in to|captcha|자동화된 요청|비정상적인 접근",
    re.IGNORECASE,
)

# 본문 내 링크 추출
_URL_RE = re.compile(r"https?://[^\s\"'<>\]]{10,}", re.IGNORECASE)

# 뉴스 도메인 (detected_links 분류용)
_NEWS_DOMAIN_RE = re.compile(
    r"https?://(?:www\.)?(?:"
    r"news\.naver\.com|n\.news\.naver\.com|news\.daum\.net|v\.daum\.net|"
    r"news\.nate\.com|yna\.co\.kr|chosun\.com|joongang\.co\.kr|donga\.com|"
    r"hani\.co\.kr|khan\.co\.kr|ohmynews\.com|newsis\.com|"
    r"hankyung\.com|mk\.co\.kr|sbs\.co\.kr|kbs\.co\.kr|mbc\.co\.kr|jtbc\.co\.kr"
    r")",
    re.IGNORECASE,
)

# 키워드: 후보명 + 전당대회
_DEFAULT_KEYWORDS = ALL_CANDIDATE_NAMES + ["전당대회", "민주당 대표"]

_MAX_PER_KEYWORD = 20  # 키워드당 최대 수집 건수


# ── X(트위터) ──────────────────────────────────────────────────

_X_EXTRACT_JS = r"""
() => {
  const posts = [];
  const seen = new Set();
  document.querySelectorAll('article[data-testid="tweet"]').forEach(art => {
    const linkEl = art.querySelector('a[href*="/status/"]');
    if (!linkEl) return;
    const href = linkEl.href;
    if (seen.has(href)) return;
    seen.add(href);

    const textEl = art.querySelector('[data-testid="tweetText"]');
    const text = textEl ? (textEl.innerText || '').trim() : '';

    const timeEl = art.querySelector('time');
    const time = timeEl ? timeEl.getAttribute('datetime') : '';

    const userEl = art.querySelector('[data-testid="User-Name"]');
    const user = userEl ? (userEl.innerText || '').split('\n')[0].trim() : '';

    const links = [];
    art.querySelectorAll('a[href]').forEach(a => {
      const h = (a.href || '').trim();
      if (h.startsWith('http') && !h.includes('twitter.com') && !h.includes('x.com')) {
        links.push(h);
      }
    });

    posts.push({ url: href, text, time, user, links: links.slice(0, 5) });
  });
  return posts.slice(0, 20);
}
"""


async def collect_x(
    page,
    keywords: list[str],
    *,
    limit_per_kw: int = _MAX_PER_KEYWORD,
) -> list[RawItem]:
    """X 검색 결과 수집. 로그인·차단 감지 시 빈 리스트 반환."""
    items: list[RawItem] = []
    seen_urls: set[str] = set()

    for kw in keywords:
        search_url = f"https://x.com/search?q={quote(kw)}&f=live&src=typed_query"
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2500)

            final_url = page.url
            page_text = await page.inner_text("body")

            if _BLOCKED_URL_RE.search(final_url) or _BLOCKED_TEXT_RE.search(page_text):
                logger.warning("[sns/x] 로그인 필요 또는 차단 감지 — 수집 중단 ({})", kw)
                return items  # 우회 없이 즉시 중단

            posts = await page.evaluate(_X_EXTRACT_JS)
            kw_count = 0
            for p in posts:
                if kw_count >= limit_per_kw:
                    break
                url = p.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                content = p.get("text", "")
                # 후보명/키워드 포함 여부 확인
                if not _contains_keyword(content + " " + kw, keywords):
                    continue

                published = _parse_iso(p.get("time", ""))
                detected = _URL_RE.findall(content)
                detected += [lnk for lnk in p.get("links", []) if lnk not in detected]

                it = RawItem(
                    platform="x",
                    source_type="sns",
                    url=url,
                    title=content[:120],
                    content=content,
                    author=p.get("user", ""),
                    published_at=published,
                    keyword=kw,
                )
                it.detected_links = detected[:20]
                items.append(it)
                kw_count += 1

        except Exception as e:  # noqa: BLE001
            logger.error("[sns/x] 수집 실패 ({}): {}", kw, e)

    logger.info("[sns/x] {}건 수집 (키워드 {}개)", len(items), len(keywords))
    return items


# ── Facebook ──────────────────────────────────────────────────

_FB_EXTRACT_JS = r"""
() => {
  const posts = [];
  const seen = new Set();

  // 게시글 컨테이너 후보
  const containers = document.querySelectorAll(
    '[data-pagelet*="FeedUnit"], [role="article"], .x1yztbdb'
  );

  containers.forEach(c => {
    // 게시글 링크: /posts/, /permalink/, story_fbid=
    const linkEls = c.querySelectorAll('a[href*="/posts/"], a[href*="story_fbid"], a[href*="/permalink/"]');
    let url = '';
    linkEls.forEach(a => { if (!url) url = a.href; });
    if (!url) return;
    if (seen.has(url)) return;
    seen.add(url);

    const text = (c.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 500);
    const timeEl = c.querySelector('abbr[data-utime], [data-testid="story-subtitle"] abbr, a[role="link"] span');
    const time = timeEl ? (timeEl.getAttribute('data-utime') || timeEl.innerText || '') : '';

    const userEl = c.querySelector('h2, strong, [data-testid="story-subtitle"] strong');
    const user = userEl ? (userEl.innerText || '').split('\n')[0].trim().slice(0, 60) : '';

    const links = [];
    c.querySelectorAll('a[href]').forEach(a => {
      const h = (a.href || '').trim();
      if (h.startsWith('http') && !h.includes('facebook.com') && !h.includes('fb.com')) {
        links.push(h);
      }
    });

    posts.push({ url, text, time, user, links: links.slice(0, 5) });
  });

  return posts.slice(0, 20);
}
"""


async def collect_facebook(
    page,
    keywords: list[str],
    *,
    limit_per_kw: int = _MAX_PER_KEYWORD,
) -> list[RawItem]:
    """Facebook 검색 결과 수집. 로그인·차단 감지 시 빈 리스트 반환."""
    items: list[RawItem] = []
    seen_urls: set[str] = set()

    for kw in keywords:
        search_url = f"https://www.facebook.com/search/posts?q={quote(kw)}"
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)

            final_url = page.url
            page_text = await page.inner_text("body")

            if _BLOCKED_URL_RE.search(final_url) or _BLOCKED_TEXT_RE.search(page_text):
                logger.warning("[sns/fb] 로그인 필요 또는 차단 감지 — 수집 중단 ({})", kw)
                return items

            posts = await page.evaluate(_FB_EXTRACT_JS)
            kw_count = 0
            for p in posts:
                if kw_count >= limit_per_kw:
                    break
                url = p.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                content = p.get("text", "")
                if not _contains_keyword(content + " " + kw, keywords):
                    continue

                published = _parse_unix_or_text(p.get("time", ""))
                detected = _URL_RE.findall(content)
                detected += [lnk for lnk in p.get("links", []) if lnk not in detected]

                it = RawItem(
                    platform="facebook",
                    source_type="sns",
                    url=url,
                    title=content[:120],
                    content=content,
                    author=p.get("user", ""),
                    published_at=published,
                    keyword=kw,
                )
                it.detected_links = detected[:20]
                items.append(it)
                kw_count += 1

        except Exception as e:  # noqa: BLE001
            logger.error("[sns/fb] 수집 실패 ({}): {}", kw, e)

    logger.info("[sns/fb] {}건 수집 (키워드 {}개)", len(items), len(keywords))
    return items


# ── Instagram / Threads (구조 열어둠 — 오늘 구현 아님) ─────────

async def collect_instagram(page, keywords: list[str]) -> list[RawItem]:
    logger.info("[sns/instagram] 미구현 — 향후 구현 예정")
    return []


async def collect_threads(page, keywords: list[str]) -> list[RawItem]:
    logger.info("[sns/threads] 미구현 — 향후 구현 예정")
    return []


# ── 헬퍼 ──────────────────────────────────────────────────────

def _contains_keyword(text: str, keywords: list[str]) -> bool:
    """텍스트에 후보명 또는 전당대회 키워드가 포함되는지."""
    return any(kw in text for kw in keywords)


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_unix_or_text(s: str) -> datetime | None:
    if not s:
        return None
    # Unix timestamp (data-utime)
    if s.isdigit():
        try:
            return datetime.fromtimestamp(int(s), tz=timezone.utc)
        except Exception:
            pass
    return parse_korean_date(s)


# ── 메인 수집 함수 ─────────────────────────────────────────────

async def run_sns_collection(
    *,
    target_id: str,
    keywords: list[str] | None = None,
    platforms: list[str] | None = None,
    profile_dir: str = _DEFAULT_PROFILE,
    headless: bool = False,
) -> dict[str, list[RawItem]]:
    """X + Facebook 수집 실행. 반환값: {"x": [...], "facebook": [...]}"""
    kws = keywords or _DEFAULT_KEYWORDS
    plats = set(platforms or ["x", "facebook"])
    results: dict[str, list[RawItem]] = {"x": [], "facebook": []}

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[sns] playwright 미설치 — pip install playwright && playwright install chromium")
        return results

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            profile_dir,
            headless=headless,
            locale="ko-KR",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        try:
            page = await ctx.new_page()

            if "x" in plats:
                results["x"] = await collect_x(page, kws)

            if "facebook" in plats:
                results["facebook"] = await collect_facebook(page, kws)

        finally:
            await ctx.close()

    total = sum(len(v) for v in results.values())
    logger.info("[sns] 전체 {}건 수집 완료 (X={}, FB={})",
                total, len(results["x"]), len(results["facebook"]))
    return results
