"""필터 — 수집물을 거부(reject)하는 규칙. 통과분만 클러스터링으로 넘어간다.

거부 사유:
- duplicate    : 같은 글 재수집 (itemId 중복)
- old_date     : 윈도우(기본 30일) 밖
- irrelevant   : 등록 키워드/인물과 무관 (본문에 미등장)
- noise        : 광고·홍보·노이즈 패턴
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from loguru import logger

from ..collectors.base import RawItem

# 광고/노이즈 패턴 (제목+본문에서 감지)
_NOISE_PATTERNS = [
    r"무료\s*체험", r"할인\s*이벤트", r"카지노", r"토토", r"대출", r"비아그라",
    r"클릭\s*▶", r"바로\s*가기\s*▶", r"\b광고\b", r"제휴\s*문의", r"협찬",
]
_NOISE_RE = re.compile("|".join(_NOISE_PATTERNS))

# 공식 API/RSS 소스(게시일을 자체 제공) — no_date 강제 대상에서 제외
_API_PLATFORMS = {
    "naver_news", "naver_blog", "naver_cafe", "youtube", "google_news", "rss",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


class RejectFilter:
    """수집 RawItem 목록을 (통과, 거부)로 분리."""

    def __init__(
        self,
        *,
        keywords: list[str],
        entities: list[str],
        window_days: int = 30,
        seen_ids: set[str] | None = None,
        require_scraped_date: bool = True,
        date_filtered_platforms: set[str] | None = None,
    ) -> None:
        self.keywords = [k for k in keywords if k]
        self.entities = [e for e in entities if e]
        self.window_start = datetime.now(timezone.utc) - timedelta(days=window_days)
        self.seen_ids = seen_ids or set()
        self.require_scraped_date = require_scraped_date
        # 사이트가 검색에서 기간을 직접 제한하는 플랫폼 → no_date 면제
        self.date_filtered_platforms = date_filtered_platforms or set()
        # 관련성 검사용 정규화 토큰 (키워드 + 인물 + 인물 별칭)
        self._needles = [_norm(t) for t in (self.keywords + self.entities) if t]

    def _is_relevant(self, item: RawItem) -> bool:
        # 관련성 토큰이 없으면(설정 안 됨) 통과시킴
        if not self._needles:
            return True
        hay = _norm(item.text)
        return any(n in hay for n in self._needles)

    def _matched_entities(self, item: RawItem) -> list[str]:
        hay = _norm(item.text)
        return [e for e in self.entities if e and _norm(e) in hay]

    def partition(self, items: list[RawItem]) -> tuple[list[RawItem], list[RawItem]]:
        passed: list[RawItem] = []
        rejected: list[RawItem] = []
        local_seen: set[str] = set()

        for item in items:
            iid = item.item_id

            # 1) 중복
            if iid in self.seen_ids or iid in local_seen:
                item.rejected, item.reject_reason = True, "duplicate"
                rejected.append(item)
                continue
            local_seen.add(iid)

            # 2) 날짜
            if item.published_at and item.published_at < self.window_start:
                item.rejected, item.reject_reason = True, "old_date"
                rejected.append(item)
                continue
            # 2-1) 스크랩 글인데 게시일을 못 구함 → 작년글 등 검색 잔재 차단(옵션)
            if (
                item.published_at is None
                and self.require_scraped_date
                and item.platform not in _API_PLATFORMS
                and item.platform not in self.date_filtered_platforms
            ):
                item.rejected, item.reject_reason = True, "no_date"
                rejected.append(item)
                continue

            # 3) 노이즈/광고
            if _NOISE_RE.search(item.text):
                item.rejected, item.reject_reason = True, "noise"
                rejected.append(item)
                continue

            # 4) 관련성
            if not self._is_relevant(item):
                item.rejected, item.reject_reason = True, "irrelevant"
                rejected.append(item)
                continue

            item.matched_entities = self._matched_entities(item)
            passed.append(item)

        logger.info("[filter] 통과 {} / 거부 {}", len(passed), len(rejected))
        return passed, rejected
