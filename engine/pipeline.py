"""파이프라인 — target 하나를 수집→필터→감정→클러스터→등급→알림→저장.

CLI:
    python -m engine.pipeline --target <targetId> --once
    python -m engine.pipeline --target <targetId> --cleanup
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone

from loguru import logger

from .analysis.claude import ClaudeAnalyzer
from .analysis.cluster import Cluster, assign_clusters
from .analysis.embed import get_embedder
from .analysis.filters import RejectFilter
from .analysis.grade import grade_cluster
from .collectors.base import RawItem
from .collectors.naver import NaverCollector
from .collectors.rss import RSSCollector
from .collectors.youtube import YouTubeCollector
from .config import get_settings
from .models import Target
from .store import FirestoreStore

_LOOKBACK = timedelta(days=2)   # 수집 조회 기간(겹침은 dedup 으로 흡수)
_ALERT_GRADES = {"red", "orange"}


def _build_collectors(target: Target):
    collectors = []
    if target.source_enabled("naver"):
        collectors.append(NaverCollector())
    if target.source_enabled("youtube"):
        collectors.append(YouTubeCollector())
    if target.source_enabled("rss"):
        collectors.append(RSSCollector())
    # 브라우저 직접 수집 (커뮤니티·SNS·로그인 사이트)
    site_keys = target.browser_site_keys()
    if site_keys:
        from .collectors.scraper import BrowserCollector
        from .collectors.sites import get_sites

        sites = get_sites(site_keys)
        if sites:
            collectors.append(BrowserCollector(sites))
    return [c for c in collectors if c.available()]


async def _collect_all(target: Target, collectors=None) -> list[RawItem]:
    keywords = target.search_keywords()
    if not keywords:
        logger.warning("[pipeline] '{}' 검색 키워드 없음", target.id)
        return []
    since = datetime.now(timezone.utc) - _LOOKBACK
    if collectors is None:
        collectors = _build_collectors(target)
    logger.info("[pipeline] 수집기 {}개 가동", len(collectors))
    results = await asyncio.gather(
        *(c.collect(keywords, since=since) for c in collectors),
        return_exceptions=True,
    )
    items: list[RawItem] = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("[pipeline] 수집기 오류: {}", r)
        else:
            items.extend(r)
    return items


def _aggregate_authors(items: list[RawItem]) -> list[dict]:
    by_author: dict[str, list[RawItem]] = {}
    for it in items:
        key = it.author_id or it.author
        if not key:
            continue
        by_author.setdefault(key, []).append(it)
    authors = []
    for key, group in by_author.items():
        mentions = sum(1 for g in group if g.matched_entities)
        likes = sum(int(g.metrics.get("likes", 0)) for g in group)
        # 이 run 의 증분값 — 저장소에서 Increment 로 누적된다(최근 윈도우 누적).
        delta_score = len(group) + mentions * 2 + likes // 100
        authors.append(
            {
                "authorId": key,
                "name": group[0].author or key,
                "mainPlatform": Counter(g.platform for g in group).most_common(1)[0][0],
                "score": delta_score,
                "postCount": len(group),
                "targetMentions": mentions,
                "updatedAt": datetime.now(timezone.utc),
            }
        )
    return authors


def _keyword_trend(items: list[RawItem], target: Target) -> dict:
    own = {w for w in target.search_keywords()}
    own |= {a for e in target.entities for a in ([e.name] + e.aliases)}
    counter: Counter = Counter()
    for it in items:
        for token in it.title.split():
            token = token.strip("#.,!?·\"'()[]{}")
            if len(token) >= 2 and token not in own:
                counter[token] += 1
    top = [{"word": w, "count": c} for w, c in counter.most_common(20)]
    return {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "top": top}


async def run_target(target_id: str, store: FirestoreStore | None = None, collectors=None) -> dict:
    s = get_settings()
    store = store or FirestoreStore(s)
    target = store.get_target(target_id)
    if target is None:
        raise RuntimeError(f"target '{target_id}' 없음 — Firestore targets/{target_id} 확인")
    logger.info("=== [{}] 파이프라인 시작 ===", target.name)

    # 1) 수집 (collectors 주입 시 그걸 사용 — 테스트/시뮬레이션용)
    raw = await _collect_all(target, collectors)

    # 2) 필터
    seen = store.recent_item_ids(target_id, days=s.window_days)
    keywords, entity_terms = target.relevance_terms()
    # 사이트가 검색에서 기간을 직접 제한하는 플랫폼은 no_date 면제
    from .collectors.sites import get_sites
    date_filtered = {
        site.platform
        for site in get_sites(target.browser_site_keys())
        if site.date_filtered
    }
    rejector = RejectFilter(
        keywords=keywords,
        entities=entity_terms,
        window_days=s.window_days,
        seen_ids=seen,
        require_scraped_date=s.scrape_require_date,
        date_filtered_platforms=date_filtered,
    )
    passed, rejected = rejector.partition(raw)

    if not passed:
        logger.info("[pipeline] 신규 통과 항목 없음")
        if rejected:
            store.save_rejected(target_id, rejected)
        return {"collected": len(raw), "passed": 0, "rejected": len(rejected), "clusters": 0}

    # 3) 감정 분류
    claude = ClaudeAnalyzer(s)
    await claude.classify_sentiments(passed, target.name)

    # 4) 임베딩 + 클러스터링
    embedder = get_embedder(s)
    active = store.load_active_clusters(target_id, s.window_days)
    prev_grade = {c.cluster_id: c.grade for c in active}
    touched = assign_clusters(active, passed, embedder, s.similarity_threshold())

    # 5) 채점 (클러스터별 기존+신규 item 합쳐 등급)
    new_by_cluster: dict[str, list[RawItem]] = {}
    for it in passed:
        if it.cluster_id:
            new_by_cluster.setdefault(it.cluster_id, []).append(it)

    alerts: list[dict] = []
    for c in touched:
        existing_items = store.load_cluster_items(target_id, c.cluster_id)
        all_items = existing_items + new_by_cluster.get(c.cluster_id, [])
        grade_cluster(c, all_items, s)
        # 요약(신규 또는 요약 없음)
        if not c.summary:
            samples = [i.text for i in all_items[:8]]
            c.summary = await claude.summarize_cluster(c.title, samples)
        # 알림: 신규 위험 또는 등급 승급
        before = prev_grade.get(c.cluster_id, "none")
        if c.grade in _ALERT_GRADES and c.grade != before:
            alerts.append(_make_alert(c))

    # 6) 저장
    store.save_items(target_id, passed)
    if rejected:
        store.save_rejected(target_id, rejected)
    store.save_clusters(target_id, touched)
    for a in alerts:
        store.add_alert(target_id, a)
    store.save_authors(target_id, _aggregate_authors(passed))
    trend = _keyword_trend(passed, target)
    store.save_keyword_trend(target_id, trend["date"], trend)

    logger.info(
        "=== [{}] 완료: 수집 {} / 통과 {} / 거부 {} / 클러스터 {} / 알림 {} ===",
        target.name, len(raw), len(passed), len(rejected), len(touched), len(alerts),
    )
    return {
        "collected": len(raw),
        "passed": len(passed),
        "rejected": len(rejected),
        "clusters": len(touched),
        "alerts": len(alerts),
    }


def _make_alert(c: Cluster) -> dict:
    return {
        "createdAt": datetime.now(timezone.utc),
        "grade": c.grade,
        "type": " · ".join(c.patterns) or "위험 신호",
        "summary": c.summary or c.title,
        "clusterIds": [c.cluster_id],
        "platforms": c.stats.get("platforms", []),
        "patterns": c.patterns,
    }


def _cli() -> None:
    parser = argparse.ArgumentParser(description="모니터링 AI 파이프라인")
    parser.add_argument("--target", required=True, help="targetId")
    parser.add_argument("--once", action="store_true", help="1회 실행")
    parser.add_argument("--cleanup", action="store_true", help="윈도우 밖 데이터 정리")
    args = parser.parse_args()

    store = FirestoreStore()
    if args.cleanup:
        store.cleanup_old(args.target, get_settings().window_days)
        return
    asyncio.run(run_target(args.target, store))


if __name__ == "__main__":
    _cli()
