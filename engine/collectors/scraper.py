"""브라우저 직접 수집기 — 컴퓨터가 실제 크롬을 움직여 검색·추출.

핵심: launch_persistent_context(영구 프로필) 로 사용자가 login.py 에서 로그인해 둔
세션(네이버 카페·X·인스타 등)을 그대로 사용한다. 즉 "로그인된 상태로 컴퓨터가 직접 수집".

사이트별 selector 가 있으면 그걸 쓰고, 없으면 일반 추출기(검색결과 페이지에서
의미있는 링크를 자동 추출)로 처리한다. → 사이트가 많아도 selector 없이 폭넓게 커버.
"""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import quote

from loguru import logger

from ..config import get_settings
from .base import Collector, RawItem
from .dateparse import parse_korean_date
from .sites import SearchSite

# 검색결과에서 제외할 흔한 내비/푸터 텍스트
_SKIP_TEXTS = {
    "로그인", "회원가입", "검색", "전체", "더보기", "다음", "이전", "홈", "공지",
    "댓글", "이미지", "동영상", "newest", "메뉴", "닫기", "신고", "더보기 ▷",
    "통합검색 바로가기", "본문영역 바로가기",
}

# link_pattern 이 없을 때 '글 링크처럼 보이는지' 판정하는 휴리스틱
_POST_LIKE = re.compile(r"(view|read|article|/posts?/|document_srl=|[?&]no=\d|/\d{5,})", re.I)

# 검색결과 페이지에서 앵커 + (날짜가 든) 행 컨텍스트를 뽑는 JS.
# 각 앵커에서 상위로 올라가며 날짜 패턴이 있는 가장 작은 조상의 텍스트를 ctx 로 가져온다.
_EXTRACT_JS = r"""
() => {
  const DATE = /\d{1,2}:\d{2}|\d{2,4}[.\-\/]\d{1,2}[.\-\/]\d{1,2}|\d+\s*(분|시간|일|주|개월|달|년)\s*전|어제|방금|오늘/;
  function ctxOf(a) {
    let el = a;
    for (let i = 0; i < 7 && el; i++) {
      el = el.parentElement;
      if (!el) break;
      const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
      if (t && t.length < 400 && DATE.test(t)) return t;
    }
    return '';
  }
  const out = [];
  const seen = new Set();
  for (const a of document.querySelectorAll('a')) {
    const text = (a.innerText || '').trim().replace(/\s+/g, ' ');
    const href = a.href || '';
    if (!href.startsWith('http')) continue;
    if (text.length < 4) continue;
    if (seen.has(href)) continue;
    seen.add(href);
    out.push({ text, href, ctx: ctxOf(a) });
  }
  return out.slice(0, 200);
}
"""


class BrowserCollector(Collector):
    name = "browser"

    def __init__(
        self,
        sites: list[SearchSite],
        *,
        profile_dir: str | None = None,
        headless: bool | None = None,
        limit_per_site: int | None = None,
    ) -> None:
        s = get_settings()
        self._sites = sites
        self._profile_dir = profile_dir or s.browser_profile_dir
        self._headless = s.headless if headless is None else headless
        self._limit = limit_per_site or s.scrape_limit_per_site
        self._window_days = s.window_days

    def available(self) -> bool:
        return bool(self._sites)

    async def collect(
        self,
        keywords: list[str],
        *,
        since: datetime | None = None,
        limit: int = 30,
    ) -> list[RawItem]:
        if not self._sites:
            return []
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("[browser] playwright 미설치 — skip (pip install playwright; playwright install chromium)")
            return []

        out: list[RawItem] = []
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                self._profile_dir,
                headless=self._headless,
                locale="ko-KR",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            try:
                for site in self._sites:
                    for kw in keywords:
                        out += await self._scrape(ctx, site, kw)
            finally:
                await ctx.close()
        logger.info("[browser] {}건 수집 (사이트 {}개)", len(out), len(self._sites))
        return out

    async def _scrape(self, ctx, site: SearchSite, kw: str) -> list[RawItem]:
        page = await ctx.new_page()
        items: list[RawItem] = []
        try:
            if site.search_method == "POST":
                await self._submit_post(page, site, kw)
            elif site.search_method == "FORM":
                await self._submit_form(page, site, kw)
            else:
                url = site.search_url.replace("{q}", quote(kw))
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(site.wait_ms)  # 동적 로딩 여유(사이트별)
            items = await self._scrape_generic(page, site, kw)
        except Exception as e:  # noqa: BLE001
            login = " (로그인 필요 — login.py 확인)" if site.requires_login else ""
            logger.error("[browser] {} '{}' 실패{}: {}", site.key, kw, login, e)
        finally:
            await page.close()
        return items[: self._limit]

    async def _submit_post(self, page, site: SearchSite, kw: str) -> None:
        """POST 검색: base 로딩 → 폼 주입·제출. {q}=키워드, {since}=윈도우 시작일."""
        from datetime import datetime, timedelta, timezone

        since = (datetime.now(timezone.utc) - timedelta(days=self._window_days)).strftime("%Y.%m.%d")
        fields = {
            k: v.replace("{q}", kw).replace("{since}", since)
            for k, v in (site.post_fields or {}).items()
        }
        await page.goto(site.base_url or site.search_url, wait_until="domcontentloaded", timeout=25000)
        await page.evaluate(
            """([action, fields]) => {
                const f=document.createElement('form');
                f.method='POST'; f.action=action;
                for(const k in fields){const i=document.createElement('input');
                    i.type='hidden'; i.name=k; i.value=fields[k]; f.appendChild(i);}
                document.body.appendChild(f); f.submit();
            }""",
            [site.search_url, fields],
        )
        await page.wait_for_load_state("domcontentloaded", timeout=20000)

    async def _submit_form(self, page, site: SearchSite, kw: str) -> None:
        """FORM 검색: base 로딩 → 검색 input 에 키워드 입력 → 그 폼 제출(토큰 자동 포함)."""
        await page.goto(site.base_url or site.search_url, wait_until="domcontentloaded", timeout=25000)
        await page.evaluate(
            """([sel, kw]) => {
                const i = document.querySelector(sel);
                if (!i || !i.form) throw new Error('검색 input/form 없음: ' + sel);
                i.value = kw;
                i.form.submit();
            }""",
            [site.search_input, kw],
        )
        await page.wait_for_load_state("domcontentloaded", timeout=20000)

    async def _scrape_generic(self, page, site: SearchSite, kw: str) -> list[RawItem]:
        rows = await page.evaluate(_EXTRACT_JS)
        host = site.base_url.split("//")[-1].split("/")[0] if site.base_url else ""
        pat = re.compile(site.link_pattern) if site.link_pattern else None
        items: list[RawItem] = []
        seen: set[str] = set()
        seen_titles: set[str] = set()
        for r in rows:
            text, href = r["text"], r["href"]
            if text in _SKIP_TEXTS or len(text) < site.min_text_len:
                continue
            if text.isdigit():  # 글번호만 있는 링크 제외
                continue
            # 글 링크 판정: link_pattern 우선, 없으면 휴리스틱(+같은 호스트)
            if pat:
                if not pat.search(href):
                    continue
            else:
                if host and site.source_type != "news" and host not in href:
                    continue
                if not _POST_LIKE.search(href):
                    continue
            if href in seen:
                continue
            seen.add(href)
            # 같은 글이 여러 링크(썸네일·댓글수 등)로 중복 노출되는 경우 제목으로 1건만
            title_key = re.sub(r"\s+", "", text)
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            # 행 컨텍스트(또는 제목)에서 게시일 추출 → 날짜 기준 수집/필터의 근거
            published = parse_korean_date(r.get("ctx", "")) or parse_korean_date(text)
            items.append(
                RawItem(
                    platform=site.platform,
                    source_type=site.source_type,
                    url=href,
                    title=text,
                    published_at=published,
                    keyword=kw,
                )
            )
        return items
