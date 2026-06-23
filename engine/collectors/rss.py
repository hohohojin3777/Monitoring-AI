"""RSS 수집기 — 구글 뉴스 검색 RSS + 구글 알리미 + 언론사 RSS.

API 키 없이 동작. 인터넷 매체·지역지·영문 보도 보완용.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from time import mktime
from urllib.parse import quote

import feedparser
from loguru import logger

from .base import Collector, RawItem

# 구글 뉴스 검색 RSS (한국어)
_GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"


def _entry_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            return datetime.fromtimestamp(mktime(t), tz=timezone.utc)
    return None


class RSSCollector(Collector):
    """기본은 구글 뉴스 RSS. extra_feeds 로 언론사/알리미 피드 추가 가능."""

    name = "rss"

    def __init__(self, extra_feeds: list[str] | None = None) -> None:
        self._extra_feeds = extra_feeds or []

    def _parse(self, url: str, keyword: str) -> list[RawItem]:
        feed = feedparser.parse(url)
        items: list[RawItem] = []
        for e in feed.entries:
            items.append(
                RawItem(
                    platform="google_news" if "news.google" in url else "rss",
                    source_type="news",
                    url=getattr(e, "link", ""),
                    title=getattr(e, "title", ""),
                    content=getattr(e, "summary", ""),
                    author=getattr(e, "source", {}).get("title", "")
                    if hasattr(e, "source")
                    else "",
                    published_at=_entry_date(e),
                    keyword=keyword,
                )
            )
        return items

    async def collect(
        self,
        keywords: list[str],
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[RawItem]:
        urls: list[tuple[str, str]] = [
            (_GOOGLE_NEWS.format(q=quote(kw)), kw) for kw in keywords
        ]
        urls += [(f, "") for f in self._extra_feeds]

        out: list[RawItem] = []
        for url, kw in urls:
            try:
                items = await asyncio.to_thread(self._parse, url, kw)
            except Exception as e:  # noqa: BLE001
                logger.error("[rss] {} 실패: {}", url, e)
                continue
            for it in items:
                if since and it.published_at and it.published_at < since:
                    continue
                out.append(it)
        logger.info("[rss] {}건 수집", len(out))
        return out[:limit] if limit else out
