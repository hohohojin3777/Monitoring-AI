"""클러스터링 — 같은 사건을 여러 매체에서 묶는다(케이스 B).

온라인(증분) 방식: 새 item 을 최근 활성 클러스터 대표 벡터와 코사인 유사도 비교해
임계값 이상이면 편입, 아니면 신규 클러스터. 한 번의 run 안에서 생성된 클러스터에도 편입 가능.

모든 provider 에서 동일하게 동작하도록, 매 run 마다 (기존 클러스터 대표텍스트 + 신규 item 텍스트)
를 함께 임베딩한다.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
from loguru import logger

from ..collectors.base import RawItem
from .embed import Embedder


import re as _re
from datetime import timedelta

_SNS_PREFIX_RE = _re.compile(r"^\[([^\]]+)\]\s*")

# 도메인 불용어 — 이 단어만 겹친다고 병합하지 않음
_DOMAIN_STOPWORDS = {
    "당권주자", "전당대회", "민주당", "더불어민주당", "당대표", "후보", "신경전",
    "전대", "당권", "대표", "의원", "김민석", "정청래", "송영길", "고민정",
    "여당", "與", "이재명", "대통령", "민주", "국회", "정치", "선거",
    "연임", "출마", "캠프", "경쟁", "레이스",
}


def _title_key_words(title: str) -> set[str]:
    """제목에서 도메인 불용어 제외한 핵심어 집합 반환."""
    tokens = set(_re.sub(r"[^\w가-힣]", " ", title).split())
    return {t for t in tokens if len(t) >= 2 and t not in _DOMAIN_STOPWORDS}


def _title_overlap(title_a: str, title_b: str) -> float:
    """두 제목의 핵심어 Jaccard 유사도 (0~1)."""
    a = _title_key_words(title_a)
    b = _title_key_words(title_b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _effective_threshold(
    base: float,
    item_pub: "datetime | None",
    cluster_latest_pub: "datetime | None",
    time_gate_hours: int,
    time_gate_threshold: float,
    item_title: str,
    cluster_title: str,
) -> float:
    """시간 차이와 제목 오버랩을 고려한 실효 임계값 반환."""
    # 1) 시간 게이트
    if item_pub and cluster_latest_pub:
        gap = abs((item_pub - cluster_latest_pub).total_seconds()) / 3600
        if gap >= time_gate_hours:
            # 시간이 많이 벌어졌을 때 강화
            base = max(base, time_gate_threshold)

    # 2) 제목 핵심어 오버랩 — 낮으면 임계값 추가 상향
    overlap = _title_overlap(item_title, cluster_title)
    if overlap < 0.15:
        # 핵심어가 거의 안 겹치면 매우 엄격하게
        base = max(base, 0.92)
    elif overlap < 0.30:
        base = max(base, 0.82)

    return base


def _cluster_title(item: "RawItem") -> str:
    """클러스터 대표 제목 — SNS 이름 태그만 있으면 content 앞부분으로 보완."""
    title = item.title or ""
    # "[이름]" 접두사만 있고 뒤에 내용이 없는 경우 → content로 보완
    m = _SNS_PREFIX_RE.match(title)
    if m and len(title.strip()) <= len(m.group(0).strip()) + 5:
        prefix = m.group(0)  # "[이름] "
        body = item.content[:60].strip() if item.content else ""
        if body:
            return f"{prefix}{body}"
    return title or item.text[:40]


@dataclass
class Cluster:
    cluster_id: str
    title: str
    rep_text: str                          # 재임베딩용 대표 텍스트(시드 글)
    first_seen: datetime
    last_seen: datetime
    latest_published_at: datetime | None = None  # 클러스터 내 가장 최신 실제 발행 시간
    first_published_at: datetime | None = None   # 클러스터 내 가장 오래된 발행 시간
    status: str = "active"                  # active | resolved | archived
    item_ids: list[str] = field(default_factory=list)
    grade: str = "none"
    patterns: list[str] = field(default_factory=list)
    filter_tag: str = "전체"
    reactivated: bool = False
    summary: str = ""
    stats: dict = field(default_factory=dict)
    # 최신 기사 정보 (뉴스 탭 대표 표시용)
    latest_article_title: str = ""
    latest_article_url: str = ""
    representative_title: str = ""
    representative_url: str = ""
    published_at_missing: bool = False      # publishedAt 없이 수집된 클러스터
    needs_time_review: bool = False
    cluster_confidence: float = 1.0   # 최근 병합 시 유사도/임계값 비율 (낮을수록 불안정)
    # transient (이번 run 에서 추가된 item)
    new_item_ids: list[str] = field(default_factory=list)
    touched: bool = False


def _new_cluster_id(seed_item_id: str) -> str:
    return hashlib.sha256(seed_item_id.encode()).hexdigest()[:8]


def assign_clusters(
    existing: list[Cluster],
    new_items: list[RawItem],
    embedder: Embedder,
    threshold: float,
    time_gate_hours: int = 24,
    time_gate_threshold: float = 0.88,
) -> list[Cluster]:
    """new_items 를 기존/신규 클러스터에 배정. 변경된 클러스터 목록을 반환.

    각 item 의 .cluster_id 를 채운다. 반환값은 이번 run 에서 생성/수정된 클러스터.
    """
    if not new_items:
        return []

    now = datetime.now(timezone.utc)

    # 1) 기존 대표 + 신규 텍스트를 한 번에 임베딩
    rep_texts = [c.rep_text for c in existing]
    new_texts = [it.text for it in new_items]
    all_vecs = embedder.embed(rep_texts + new_texts)
    rep_vecs = all_vecs[: len(existing)]
    new_vecs = all_vecs[len(existing):]

    # 현재 비교 대상 클러스터(기존 + 이번 run 신규)의 벡터 리스트
    cluster_vecs: list[np.ndarray] = [rep_vecs[i] for i in range(len(existing))]
    clusters: list[Cluster] = list(existing)
    touched: dict[str, Cluster] = {}

    for idx, item in enumerate(new_items):
        vec = new_vecs[idx]
        best_i, best_sim = -1, -1.0
        if cluster_vecs:
            sims = np.array([float(np.dot(vec, cv)) for cv in cluster_vecs])
            best_i = int(np.argmax(sims))
            best_sim = float(sims[best_i])

        effective = _effective_threshold(
            threshold,
            item.published_at,
            clusters[best_i].latest_published_at if best_i >= 0 else None,
            time_gate_hours,
            time_gate_threshold,
            item.title or "",
            clusters[best_i].title if best_i >= 0 else "",
        ) if best_i >= 0 else threshold

        if best_i >= 0 and best_sim >= effective:
            c = clusters[best_i]
            c.cluster_confidence = round(best_sim / effective, 3) if effective > 0 else 1.0
            c.item_ids.append(item.item_id)
            c.new_item_ids.append(item.item_id)
            c.last_seen = now
            if item.published_at:
                # 최신 발행 시간 갱신 → 대표 기사 title/url 동시 갱신
                if c.latest_published_at is None or item.published_at > c.latest_published_at:
                    c.latest_published_at = item.published_at
                    if item.title:
                        c.latest_article_title = item.title
                        c.representative_title = item.title
                    if item.url:
                        c.latest_article_url = item.url
                        c.representative_url = item.url
                # 가장 오래된 발행 시간
                if c.first_published_at is None or item.published_at < c.first_published_at:
                    c.first_published_at = item.published_at
            else:
                c.published_at_missing = True
                c.needs_time_review = True
            c.touched = True
            # 종료된 클러스터에 새 글 유입 → 재발
            if c.status in ("resolved", "archived"):
                c.status = "active"
                c.reactivated = True
                c.filter_tag = "재발"
            item.cluster_id = c.cluster_id
            touched[c.cluster_id] = c
        else:
            cid = _new_cluster_id(item.item_id)
            published = item.published_at or now
            seed_title = _cluster_title(item)
            c = Cluster(
                cluster_id=cid,
                title=seed_title,
                rep_text=item.text,
                first_seen=published,
                last_seen=now,
                latest_published_at=item.published_at,
                first_published_at=item.published_at,
                latest_article_title=item.title or seed_title,
                latest_article_url=item.url or "",
                representative_title=item.title or seed_title,
                representative_url=item.url or "",
                published_at_missing=item.published_at is None,
                needs_time_review=item.published_at is None,
                item_ids=[item.item_id],
                new_item_ids=[item.item_id],
                touched=True,
            )
            item.cluster_id = cid
            clusters.append(c)
            cluster_vecs.append(vec)
            touched[cid] = c

    result = list(touched.values())
    logger.info(
        "[cluster] 신규/수정 클러스터 {}개 (배정 item {}건)",
        len(result),
        len(new_items),
    )
    return result
