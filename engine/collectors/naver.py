"""네이버 검색 API 수집기 — 뉴스·블로그·카페.

공식 문서: https://developers.naver.com/docs/serviceapi/search/news/news.md
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

_OG_IMAGE_RE = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https?://[^"\']+)["\']', re.I)
_OG_IMAGE_RE2 = re.compile(r'<meta[^>]+content=["\'](https?://[^"\']+)["\'][^>]+property=["\']og:image["\']', re.I)

async def _fetch_og_image(client: httpx.AsyncClient, url: str) -> str:
    try:
        r = await client.get(url, timeout=5.0, follow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
        html = r.text[:8000]
        m = _OG_IMAGE_RE.search(html) or _OG_IMAGE_RE2.search(html)
        return m.group(1) if m else ""
    except Exception:
        return ""

from ..config import get_settings
from .base import Collector, RawItem

_BASE = "https://openapi.naver.com/v1/search"

# (엔드포인트, source_type, platform)
_KINDS = [
    ("news.json", "news", "naver_news"),
    ("blog.json", "blog", "naver_blog"),
    ("cafearticle.json", "cafe", "naver_cafe"),
]
_MAX_DISPLAY = 100  # 네이버 API 1회 최대


def _parse_date(item: dict) -> datetime | None:
    # 뉴스: pubDate (RFC822) / 블로그·카페: postdate (yyyymmdd)
    if item.get("pubDate"):
        try:
            return parsedate_to_datetime(item["pubDate"]).astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None
    if item.get("postdate"):
        try:
            return datetime.strptime(item["postdate"], "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


class NaverCollector(Collector):
    name = "naver"

    def __init__(self) -> None:
        s = get_settings()
        self._cid = s.naver_client_id
        self._secret = s.naver_client_secret

    def available(self) -> bool:
        return bool(self._cid and self._secret)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
    async def _fetch(self, client: httpx.AsyncClient, endpoint: str, query: str) -> list[dict]:
        resp = await client.get(
            f"{_BASE}/{endpoint}",
            params={"query": query, "display": _MAX_DISPLAY, "sort": "date"},
            headers={
                "X-Naver-Client-Id": self._cid,
                "X-Naver-Client-Secret": self._secret,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("items", [])

    async def collect(
        self,
        keywords: list[str],
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[RawItem]:
        if not self.available():
            logger.warning("[naver] 키 없음 — skip")
            return []

        out: list[RawItem] = []
        async with httpx.AsyncClient() as client:
            for kw in keywords:
                for endpoint, source_type, platform in _KINDS:
                    try:
                        items = await self._fetch(client, endpoint, kw)
                    except Exception as e:  # noqa: BLE001
                        logger.error("[naver] {} '{}' 실패: {}", endpoint, kw, e)
                        continue
                    for it in items:
                        published = _parse_date(it)
                        if since and published and published < since:
                            continue
                        out.append(
                            RawItem(
                                platform=platform,
                                source_type=source_type,
                                url=it.get("originallink") or it.get("link", ""),
                                title=it.get("title", ""),
                                content=it.get("description", ""),
                                author=it.get("bloggername") or it.get("cafename", ""),
                                published_at=published,
                                keyword=kw,
                                raw={"link": it.get("link", "")},
                            )
                        )

        # 뉴스 기사만 og:image 병렬 수집 (최대 50건 — 과도한 요청 방지)
        news_items = [i for i in out if i.platform == "naver_news" and not i.image_url][:50]
        if news_items:
            imgs = await asyncio.gather(*[_fetch_og_image(client, i.url) for i in news_items])
            for i, img in zip(news_items, imgs):
                i.image_url = img

        logger.info("[naver] {}건 수집 (키워드 {}개)", len(out), len(keywords))
        return out[:limit] if limit else out
