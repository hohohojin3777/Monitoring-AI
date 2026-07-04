"""수집기 공통: RawItem 모델 + Collector 추상 클래스 + URL/HTML 유틸."""
from __future__ import annotations

import hashlib
import html
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# 제거할 추적용 쿼리 파라미터 prefix
_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "igshid", "spm")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str | None) -> str:
    """HTML 태그 제거 + 엔티티 디코드 + 공백 정리. 네이버 API 의 <b> 등 처리용."""
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def canonical_url(url: str) -> str:
    """URL 정규화: 소문자 호스트, 추적 파라미터 제거, fragment 제거, 끝 슬래시 정리."""
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip()
    host = parts.netloc.lower()
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not any(k.lower().startswith(p) for p in _TRACKING_PREFIXES)
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme or "https", host, path, urlencode(query), ""))


@dataclass
class RawItem:
    """수집된 개별 글/영상/기사 1건. 파이프라인의 공통 단위."""

    platform: str               # naver_news | naver_blog | naver_cafe | youtube | x | dcinside ...
    source_type: str            # news | blog | cafe | video | sns | community
    url: str
    title: str = ""
    content: str = ""
    author: str = ""
    author_id: str = ""
    published_at: datetime | None = None
    collected_at: datetime | None = None
    metrics: dict[str, int] = field(default_factory=dict)   # views, likes, comments
    keyword: str = ""           # 매칭된 검색 키워드
    image_url: str = ""         # og:image 등 대표 이미지 URL
    raw: dict[str, Any] = field(default_factory=dict)       # 원본 응답 일부(디버깅)
    # ── 커뮤니티 세분류 필드 (sourceType=community 전용) ──
    community_content_type: str = ""     # original_post | comment | shared_news | unknown
    board_name: str = ""                 # 게시판명
    community_name: str = ""            # 커뮤니티명
    post_id: str = ""                   # 게시글 고유 ID
    parent_post_id: str = ""            # 댓글인 경우 부모 글 ID
    parent_url: str = ""                # 댓글인 경우 부모 글 URL
    comment_id: str = ""                # 댓글 고유 ID
    shared_url: str = ""                # 공유된 외부 URL (shared_news용)
    article_url: str = ""               # 본문 내 뉴스 기사 URL
    detected_links: list[str] = field(default_factory=list)  # 본문에서 감지된 링크 목록
    classification_confidence: float = 0.0   # 분류 신뢰도 (0~1)
    classification_reason: str = ""     # 분류 근거

    # ── 파이프라인이 채우는 주석 필드 (수집 시점엔 비어있음) ──
    matched_entities: list[str] = field(default_factory=list)
    sentiment: str = ""         # positive | neutral | negative | attack
    event_key: str = ""         # Claude 추출 이벤트 키 — 다르면 병합 차단
    embedding: list[float] | None = None
    cluster_id: str | None = None
    rejected: bool = False
    reject_reason: str = ""     # noise | old_date | irrelevant | hallucination | duplicate

    def __post_init__(self) -> None:
        self.url = self.url.strip()
        self.title = strip_html(self.title)
        self.content = strip_html(self.content)
        if self.collected_at is None:
            self.collected_at = datetime.now(timezone.utc)

    @property
    def canonical(self) -> str:
        return canonical_url(self.url)

    @property
    def item_id(self) -> str:
        """dedup 키: sha256(platform + canonical_url)[:16]."""
        basis = f"{self.platform}|{self.canonical}".encode("utf-8")
        return hashlib.sha256(basis).hexdigest()[:16]

    @property
    def text(self) -> str:
        """임베딩/분류에 쓰는 통합 텍스트."""
        return f"{self.title}\n{self.content}".strip()


class Collector(ABC):
    """수집기 인터페이스. 구현체는 collect() 만 채우면 된다."""

    #: 수집기 식별자 (로그/설정용)
    name: str = "base"

    @abstractmethod
    async def collect(
        self,
        keywords: list[str],
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[RawItem]:
        """keywords 로 since 이후 항목을 최대 limit 건 수집한다."""
        raise NotImplementedError

    def available(self) -> bool:
        """필요한 키/설정이 있어 사용 가능한지. 없으면 파이프라인이 skip."""
        return True
