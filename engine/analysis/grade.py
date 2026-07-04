"""위기 등급 + 이슈 3-레이어 분류.

기존 grade(red/orange/yellow/none)는 GPT/Telegram/reports 하위호환으로 유지.
신규: issueImportance / riskLevel / responseLevel 로 중요도와 리스크를 분리.

핵심 원칙:
- 매체다양성(여러 플랫폼)만으로는 '주의'가 되지 않는다.
- 출마선언·일정·정책발표 같은 긍정 뉴스는 중요도↑이지 리스크가 아니다.
- '주의/위기/긴급'은 부정 신호(sentiment, 키워드)가 있을 때만 사용.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..collectors.base import RawItem
from ..config import Settings
from .cluster import Cluster

_NEG = {"negative", "attack"}
_BURST_WINDOW_H = 6
_BURST_MIN_POSTS = 10

# 중요도를 높이는 키워드 (긍정적 핵심 이벤트)
_IMPORTANCE_KEYWORDS = {
    "출마", "출마선언", "선언", "당대표", "전당대회", "행보",
    "지지선언", "지지율", "여론조사", "기자회견", "토론회",
    "정책발표", "발표", "메시지", "인터뷰", "기조연설",
    "공약", "당선", "승리", "호남", "영남", "수도권",
}

# 리스크 키워드 (부정 신호)
_RISK_KEYWORDS_HARD = {
    "의혹", "논란", "수사", "고발", "폭로", "특혜",
    "거짓", "막말", "사퇴", "스캔들", "부정", "조작", "은폐",
}

# 리스크로 보지 않을 단순 뉴스 유형 키워드
_SAFE_KEYWORDS = {
    "출마선언", "일정", "지역방문", "방문", "선언",
    "정책발표", "지지선언", "인터뷰", "공약",
}


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

    # 1) 부정 다플랫폼 (진짜 리스크)
    if len(neg_platforms) >= s.multiplatform_min:
        patterns.append("부정다플랫폼")

    # 2) 부정 키워드
    risk_hits = sum(
        1 for it in items if any(k in it.text for k in s.risk_keywords)
    )
    if risk_hits >= s.negative_keyword_threshold:
        patterns.append("부정키워드")

    # 3) 매체 다양성 — 부정 비율 30% 이상일 때만 위험 신호로 인정
    neg_ratio = (stats["sentiment"]["negative"] + stats["sentiment"]["attack"]) / max(stats["posts"], 1)
    if stats["platformCount"] >= s.media_diversity_min and neg_ratio >= 0.3:
        patterns.append("매체다양성")
    elif stats["platformCount"] >= s.media_diversity_min:
        # 부정 없는 다매체 확산 → 리스크 아닌 확산(중요도 상승용)
        patterns.append("다매체확산")

    # 4) 다플랫폼 집단 (단기 급증 + 다플랫폼)
    recent = [
        it for it in items
        if it.published_at and it.published_at >= now - timedelta(hours=_BURST_WINDOW_H)
    ]
    if len(recent) >= _BURST_MIN_POSTS and len({it.platform for it in recent}) >= 2:
        patterns.append("다플랫폼집단")

    return patterns


def _grade(pattern_count: int, posts: int, s: Settings) -> str:
    """기존 grade — GPT/reports 하위호환. 리스크 패턴만 카운트."""
    if pattern_count >= s.grade_red_pattern_count or posts >= s.grade_red_post_count:
        return "red"
    if pattern_count >= s.grade_orange_pattern_count or posts >= s.grade_orange_post_count:
        return "orange"
    if pattern_count >= 1:
        return "yellow"
    return "none"


def _risk_pattern_count(patterns: list[str]) -> int:
    """실제 리스크 패턴만 카운트 (다매체확산 제외)."""
    risk_patterns = {"부정다플랫폼", "부정키워드", "매체다양성", "다플랫폼집단"}
    return sum(1 for p in patterns if p in risk_patterns)


def _compute_issue_importance(items: list[RawItem], patterns: list[str], stats: dict) -> str:
    """중요도 판단 — 리스크와 무관하게 이슈가 얼마나 중요한가."""
    # 부정 리스크 패턴이 있으면 중요도를 관찰 이하로
    has_risk_pattern = bool({"부정다플랫폼", "부정키워드"} & set(patterns))
    neg_ratio = (stats["sentiment"]["negative"] + stats["sentiment"]["attack"]) / max(stats["posts"], 1)

    all_text = " ".join((it.title or "") + " " + it.text[:150] for it in items[:15])
    importance_hits = sum(1 for kw in _IMPORTANCE_KEYWORDS if kw in all_text)
    has_safe = any(kw in all_text for kw in _SAFE_KEYWORDS)

    if has_risk_pattern and neg_ratio >= 0.5:
        return "관찰"

    # 핵심: 중요 키워드 다수 + 다매체 확산 + 부정 아님
    if importance_hits >= 2 and "다매체확산" in patterns and not has_risk_pattern:
        return "핵심"
    if importance_hits >= 1 or "다매체확산" in patterns:
        return "중요"
    if stats["posts"] >= 3 or stats["platformCount"] >= 2:
        return "관찰"
    return "일반"


def _compute_risk_level(items: list[RawItem], patterns: list[str], stats: dict) -> str:
    """리스크 레벨 — 진짜 위험 신호가 있을 때만."""
    risk_count = _risk_pattern_count(patterns)
    neg_ratio = (stats["sentiment"]["negative"] + stats["sentiment"]["attack"]) / max(stats["posts"], 1)

    # 경성 리스크 키워드 직접 감지
    all_text = " ".join(it.text[:200] for it in items[:20])
    hard_risk = sum(1 for kw in _RISK_KEYWORDS_HARD if kw in all_text)

    # 긴급: 강한 다중 신호
    if risk_count >= 3 or (risk_count >= 2 and hard_risk >= 2):
        return "긴급"
    # 위기: 명확한 부정 신호
    if risk_count >= 2 or (risk_count >= 1 and hard_risk >= 1 and neg_ratio >= 0.4):
        return "위기"
    # 주의: 부정 신호 초기
    if risk_count >= 1 or (hard_risk >= 1 and neg_ratio >= 0.3):
        return "주의"
    return "없음"


def _compute_response_level(risk_level: str, issue_importance: str, patterns: list[str]) -> str:
    """대응 레벨 — 리스크+중요도 조합."""
    if risk_level == "긴급":
        return "즉시대응"
    if risk_level == "위기" or "부정다플랫폼" in patterns:
        return "대응필요"
    if risk_level == "주의":
        return "보고필요"
    if issue_importance in ("핵심", "중요"):
        return "보고필요"
    if issue_importance == "관찰":
        return "모니터링"
    return "무대응"


def _filter_tag(cluster: Cluster, grade: str, patterns: set[str], risk_level: str) -> str:
    if cluster.reactivated:
        return "재발"
    if risk_level in ("긴급", "위기") or {"부정다플랫폼", "다플랫폼집단"} & patterns:
        return "대응필요"
    if risk_level == "주의":
        return "주의"
    if grade == "yellow" and risk_level == "없음":
        # 매체다양성만 있는 경우 → 주의 아님, 일반
        return "전체"
    if grade == "yellow":
        return "주의"
    return "전체"


def grade_cluster(cluster: Cluster, items: list[RawItem], s: Settings) -> Cluster:
    """클러스터의 stats/patterns/grade/filter_tag/issueImportance/riskLevel/responseLevel 갱신."""
    stats = compute_stats(items)
    patterns = _detect_patterns(items, stats, s)

    # 리스크 패턴만으로 기존 grade 계산 (하위호환)
    risk_count = _risk_pattern_count(patterns)
    grade = _grade(risk_count, stats["posts"], s)

    # 3-레이어 분류
    issue_importance = _compute_issue_importance(items, patterns, stats)
    risk_level = _compute_risk_level(items, patterns, stats)
    response_level = _compute_response_level(risk_level, issue_importance, patterns)

    cluster.stats = stats
    cluster.patterns = patterns
    cluster.grade = grade
    cluster.issue_importance = issue_importance
    cluster.risk_level = risk_level
    cluster.response_level = response_level

    if not (cluster.reactivated and cluster.filter_tag == "재발"):
        cluster.filter_tag = _filter_tag(cluster, grade, set(patterns), risk_level)
    return cluster
