"""위기 등급 — 클러스터 단위로 4가지 상승 패턴을 감지하고 red/orange/yellow 부여.

패턴(설정값으로 임계 조정 가능):
- 부정다플랫폼 : 부정 글이 서로 다른 N개 매체 이상에서 발생
- 부정키워드   : 위험 키워드(의혹·논란·수사 등)가 임계 빈도 초과
- 매체다양성   : 한 이슈가 N개 이상 플랫폼에서 동시 발생
- 다플랫폼집단 : 단기 급증 + 다플랫폼

등급: red = 패턴 N개+ 또는 글 N건+ / orange = 패턴 2 또는 글 N건+ / yellow = 패턴 1 / none.
filter_tag 는 대시보드 1차 버킷(재발 > 대응필요 > 주의 > 전체).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..collectors.base import RawItem
from ..config import Settings
from .cluster import Cluster

_NEG = {"negative", "attack"}
_BURST_WINDOW_H = 6
_BURST_MIN_POSTS = 10


def compute_stats(items: list[RawItem]) -> dict:
    platforms = sorted({it.platform for it in items})
    sentiment = {"positive": 0, "neutral": 0, "negative": 0, "attack": 0}
    likes = comments = views = 0
    for it in items:
        sentiment[it.sentiment if it.sentiment in sentiment else "neutral"] += 1
        likes += int(it.metrics.get("likes", 0))
        comments += int(it.metrics.get("comments", 0))
        views += int(it.metrics.get("views", 0))
    return {
        "posts": len(items),
        "platforms": platforms,
        "platformCount": len(platforms),
        "likes": likes,
        "comments": comments,
        "views": views,
        "sentiment": sentiment,
    }


def _detect_patterns(items: list[RawItem], stats: dict, s: Settings) -> list[str]:
    patterns: list[str] = []
    now = datetime.now(timezone.utc)

    neg_items = [it for it in items if it.sentiment in _NEG]
    neg_platforms = {it.platform for it in neg_items}

    # 1) 부정 다플랫폼
    if len(neg_platforms) >= s.multiplatform_min:
        patterns.append("부정다플랫폼")

    # 2) 부정 키워드
    risk_hits = sum(
        1 for it in items if any(k in it.text for k in s.risk_keywords)
    )
    if risk_hits >= s.negative_keyword_threshold:
        patterns.append("부정키워드")

    # 3) 매체 다양성
    if stats["platformCount"] >= s.media_diversity_min:
        patterns.append("매체다양성")

    # 4) 다플랫폼 집단 (단기 급증 + 다플랫폼)
    recent = [
        it for it in items
        if it.published_at and it.published_at >= now - timedelta(hours=_BURST_WINDOW_H)
    ]
    if len(recent) >= _BURST_MIN_POSTS and len({it.platform for it in recent}) >= 2:
        patterns.append("다플랫폼집단")

    return patterns


def _grade(pattern_count: int, posts: int, s: Settings) -> str:
    if pattern_count >= s.grade_red_pattern_count or posts >= s.grade_red_post_count:
        return "red"
    if pattern_count >= s.grade_orange_pattern_count or posts >= s.grade_orange_post_count:
        return "orange"
    if pattern_count >= 1:
        return "yellow"
    return "none"


def _filter_tag(cluster: Cluster, grade: str, patterns: set[str]) -> str:
    if cluster.reactivated:
        return "재발"
    if grade in ("red", "orange") or {"부정다플랫폼", "다플랫폼집단"} & patterns:
        return "대응필요"
    if grade == "yellow":
        return "주의"
    return "전체"


def grade_cluster(cluster: Cluster, items: list[RawItem], s: Settings) -> Cluster:
    """클러스터의 stats/patterns/grade/filter_tag 를 갱신해 반환."""
    stats = compute_stats(items)
    patterns = _detect_patterns(items, stats, s)
    grade = _grade(len(patterns), stats["posts"], s)

    cluster.stats = stats
    cluster.patterns = patterns
    cluster.grade = grade
    if not (cluster.reactivated and cluster.filter_tag == "재발"):
        cluster.filter_tag = _filter_tag(cluster, grade, set(patterns))
    return cluster
