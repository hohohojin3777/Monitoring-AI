"""유튜브 Data API v3 수집기 — 키워드 검색 + 영상 통계.

문서: https://developers.google.com/youtube/v3/docs/search/list
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import get_settings
from .base import Collector, RawItem

_SEARCH = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


class YouTubeCollector(Collector):
    name = "youtube"

    def __init__(self) -> None:
        self._key = get_settings().youtube_api_key

    def available(self) -> bool:
        return bool(self._key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
    async def _get(self, client: httpx.AsyncClient, url: str, params: dict) -> dict:
        resp = await client.get(url, params={**params, "key": self._key}, timeout=10.0)
        resp.raise_for_status()
        return resp.json()

    async def collect(
        self,
        keywords: list[str],
        *,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[RawItem]:
        if not self.available():
            logger.warning("[youtube] 키 없음 — skip")
            return []

        out: list[RawItem] = []
        async with httpx.AsyncClient() as client:
            for kw in keywords:
                params = {
                    "part": "snippet",
                    "q": kw,
                    "type": "video",
                    "order": "date",
                    "maxResults": min(limit, 50),
                    "relevanceLanguage": "ko",
                }
                if since:
                    params["publishedAfter"] = since.astimezone(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )
                try:
                    data = await self._get(client, _SEARCH, params)
                except Exception as e:  # noqa: BLE001
                    logger.error("[youtube] 검색 '{}' 실패: {}", kw, e)
                    continue

                video_ids: list[str] = []
                snippets: dict[str, dict] = {}
                for it in data.get("items", []):
                    vid = (it.get("id") or {}).get("videoId")
                    if vid:
                        video_ids.append(vid)
                        snippets[vid] = it.get("snippet", {})

                stats = await self._fetch_stats(client, video_ids)
                for vid in video_ids:
                    sn = snippets[vid]
                    st = stats.get(vid, {})
                    out.append(
                        RawItem(
                            platform="youtube",
                            source_type="video",
                            url=f"https://www.youtube.com/watch?v={vid}",
                            title=sn.get("title", ""),
                            content=sn.get("description", ""),
                            author=sn.get("channelTitle", ""),
                            author_id=sn.get("channelId", ""),
                            published_at=_parse_iso(sn.get("publishedAt")),
                            metrics={
                                "views": int(st.get("viewCount", 0)),
                                "likes": int(st.get("likeCount", 0)),
                                "comments": int(st.get("commentCount", 0)),
                            },
                            keyword=kw,
                        )
                    )
        logger.info("[youtube] {}건 수집 (키워드 {}개)", len(out), len(keywords))
        return out

    async def _fetch_stats(
        self, client: httpx.AsyncClient, video_ids: list[str]
    ) -> dict[str, dict]:
        if not video_ids:
            return {}
        try:
            data = await self._get(
                client,
                _VIDEOS,
                {"part": "statistics", "id": ",".join(video_ids)},
            )
        except Exception as e:  # noqa: BLE001
            logger.error("[youtube] 통계 조회 실패: {}", e)
            return {}
        return {it["id"]: it.get("statistics", {}) for it in data.get("items", [])}
