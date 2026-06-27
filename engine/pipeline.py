"""파이프라인 — target 하나를 수집→필터→감정→클러스터→등급→알림→저장.

CLI:
    python -m engine.pipeline --target <targetId> --once
    python -m engine.pipeline --target <targetId> --cleanup
"""
from __future__ import annotations

import argparse
import asyncio
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
from .notifier import notify_alert
from .models import Target
from .store import FirestoreStore

_LOOKBACK = timedelta(days=2)   # 수집 조회 기간(겹침은 dedup 으로 흡수)
_ALERT_GRADES = {"red", "orange"}


def _build_collectors(target: Target):
    collectors = []
    if target.source_enabled("naver"):
        collectors.append(NaverCollector())
    # YouTube keyword search 비활성화 — 채널 직접 수집(playlistItems)만 사용
    # (keyword search = 100 unit/call → 할당량 소진. 채널수집 = 1 unit/call)
    if target.source_enabled("rss"):
        collectors.append(RSSCollector())
    # 브라우저 직접 수집 — Railway 환경에서는 Playwright 커뮤니티 수집 비활성화
    import os as _os
    if not _os.environ.get("RAILWAY_ENVIRONMENT"):
        site_keys = target.browser_site_keys()
        if site_keys:
            from .collectors.scraper import BrowserCollector
            from .collectors.sites import get_sites
            sites = get_sites(site_keys)
            if sites:
                collectors.append(BrowserCollector(sites))
    return [c for c in collectors if c.available()]


async def _collect_watch_accounts(target: Target, s, store=None) -> list[RawItem]:
    """watch_targets 기반 SNS 계정 직접 모니터링.

    tier별 주기 적용:
      S급 = 60분, A급 = 120분
    현재 사이클에서 수집해야 할 타깃만 필터링.
    """
    import os
    from .watch_targets import get_targets
    from .collectors.account_monitor import collect_targets

    profile_dir = s.browser_profile_dir
    if not os.path.isabs(profile_dir):
        profile_dir = str(Path(__file__).parent / profile_dir)

    now = datetime.now(timezone.utc)
    all_targets = get_targets(enabled_only=True)

    # Firestore lastCollectedAt 체크 대신 단순 시간 기반 필터
    # (30분 파이프라인 주기 기준: S=2사이클=60분, A=4사이클=120분)
    cycle_min = s.collect_interval_minutes  # 기본 30분
    collect_this_cycle: list[dict] = []
    for t in all_targets:
        interval = t.get("crawlIntervalMinutes", 120)
        # 현재 사이클 번호 (0부터 시작)
        cycle_num = int(now.timestamp() // 60 // cycle_min)
        # tier별 주기를 파이프라인 사이클 수로 환산 → 해당 사이클이면 수집
        cycles_needed = max(1, interval // cycle_min)
        if cycle_num % cycles_needed == 0:
            collect_this_cycle.append(t)

    if not collect_this_cycle:
        return []

    logger.info("[pipeline] SNS 모니터링: {}개 타깃 수집 (전체 {}개 중)",
                len(collect_this_cycle), len(all_targets))

    try:
        return await asyncio.wait_for(
            collect_targets(collect_this_cycle, profile_dir, limit_per_account=10, store=store),
            timeout=600,  # 10분
        )
    except asyncio.TimeoutError:
        logger.warning("[pipeline] SNS 모니터링 타임아웃(10분) — 건너뜀")
        return []


# YouTube API는 하루 10,000 unit 제한 — 핵심 키워드만 사용 (100 unit/검색)
_YT_KEYWORDS = [
    "민주당 전당대회", "김민석 당대표", "정청래 당대표", "송영길 당대표", "8.17 전당대회",
]


async def _collect_all(target: Target, collectors=None) -> list[RawItem]:
    keywords = target.search_keywords()
    if not keywords:
        logger.warning("[pipeline] '{}' 검색 키워드 없음", target.id)
        return []
    since = datetime.now(timezone.utc) - _LOOKBACK
    if collectors is None:
        collectors = _build_collectors(target)
    logger.info("[pipeline] 수집기 {}개 가동", len(collectors))
    # YouTube는 API 할당량 절약을 위해 핵심 키워드만 전달
    tasks = [
        asyncio.create_task(
            c.collect(_YT_KEYWORDS if c.name == "youtube" else keywords, since=since)
        )
        for c in collectors
    ]
    done, pending = await asyncio.wait(tasks, timeout=300)
    for t in pending:
        t.cancel()
        logger.warning("[pipeline] 수집기 타임아웃(5분) — 1개 강제 종료")
    results = []
    for t in done:
        try:
            results.append(t.result())
        except Exception as e:
            logger.error("[pipeline] 수집기 오류: {}", e)
    items: list[RawItem] = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("[pipeline] 수집기 오류: {}", r)
        else:
            items.extend(r)

    # 후보 공식 채널 수집 — 6시간마다만 (API 할당량 절약)
    now_hour = datetime.now(timezone.utc).hour
    if target.source_enabled("youtube") and now_hour % 6 == 0:
        try:
            from .collectors.youtube import YouTubeCollector, CANDIDATE_CHANNELS
            yt = YouTubeCollector()
            channel_items = await yt.collect_channels(
                list(CANDIDATE_CHANNELS.values()), since=since, limit=10
            )
            items.extend(channel_items)
            logger.info("[pipeline] 후보 채널 {}건 추가", len(channel_items))
        except Exception as e:
            logger.warning("[pipeline] 후보 채널 수집 실패: {}", e)

    return items


# 채널명 → (성향, 세부계열) 매핑 — 직접 지정 우선
_CHANNEL_MAP: dict[str, tuple[str, str]] = {
    # 친이재명·친명 계열
    "이재명": ("민주성향", "친명"),
    "알릴레오": ("민주성향", "친명"),
    "스픽스": ("민주성향", "친명"),
    "뷰리핑": ("민주성향", "친명"),
    "민주당": ("민주성향", "친명"),
    # 김민석 캠프 우호
    "김민석": ("민주성향", "친김민석"),
    "민트tv": ("민주성향", "친김민석"),
    "민트TV": ("민주성향", "친김민석"),
    # 정청래 계열
    "정청래": ("민주성향", "친정청래"),
    # 송영길 계열
    "송영길": ("민주성향", "친송영길"),
    # 김용민 계열
    "김용민": ("민주성향", "친김용민"),
    # 범친문 / 비명 성향
    "추미애": ("민주성향", "범친문"),
    "홍익표": ("민주성향", "범친문"),
    "우원식": ("민주성향", "범친문"),
    "임종석": ("민주성향", "범친문"),
    "설훈": ("민주성향", "범친문"),
    "이낙연": ("민주성향", "비명"),
    "박용진": ("민주성향", "비명"),
    "금태섭": ("민주성향", "비명"),
    # 진보 일반
    "뉴스공장": ("민주성향", "진보미디어"),
    "매불쇼": ("민주성향", "진보미디어"),
    "딴지": ("민주성향", "진보미디어"),
    "참세상": ("민주성향", "진보미디어"),
    "새날": ("민주성향", "진보미디어"),
    "이동형": ("민주성향", "진보미디어"),
    "홍사훈": ("민주성향", "진보미디어"),
    "황현희": ("민주성향", "진보미디어"),
    "장윤선": ("민주성향", "진보미디어"),
    "고현준": ("민주성향", "진보미디어"),
    "박지훈": ("민주성향", "진보미디어"),
    "정치읽어주는여자": ("민주성향", "진보미디어"),
    "뉴스다이브": ("민주성향", "진보미디어"),
    "흑백여의도": ("민주성향", "진보미디어"),
    "장르만여의도": ("민주성향", "진보미디어"),
    "열린공감tv": ("민주성향", "진보미디어"),
    # 보수 계열
    "국민의힘": ("보수성향", "국민의힘"),
    "윤석열": ("보수성향", "친윤"),
    "이준석": ("보수성향", "개혁신당"),
    "나경원": ("보수성향", "국민의힘"),
    "한동훈": ("보수성향", "친한"),
    "펜앤마이크": ("보수성향", "보수미디어"),
    "신의한수": ("보수성향", "보수미디어"),
    "가로세로연구소": ("보수성향", "보수미디어"),
    "미래한국": ("보수성향", "보수미디어"),
}

# 키워드 기반 fallback
_MINJOO_KW = ["진보", "민주", "참여정부", "문재인", "노무현"]
_CONSERVATIVE_KW = ["보수", "자유", "한국당", "태극기"]


def _author_tendency(name: str) -> tuple[str, str]:
    """채널명으로 (성향, 세부계열) 반환."""
    for key, val in _CHANNEL_MAP.items():
        if key in name:
            return val
    if any(k in name for k in _MINJOO_KW):
        return ("민주성향", "진보미디어")
    if any(k in name for k in _CONSERVATIVE_KW):
        return ("보수성향", "보수미디어")
    return ("중립/불명", "-")


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
        views = sum(int(g.metrics.get("views", 0)) for g in group)
        delta_score = len(group) + mentions * 2 + likes // 100 + views // 10000
        name = group[0].author or key
        platform = Counter(g.platform for g in group).most_common(1)[0][0]
        tendency, faction = _author_tendency(name) if platform == "youtube" else ("미디어/커뮤니티", "-")
        authors.append(
            {
                "authorId": key,
                "name": name,
                "mainPlatform": platform,
                "tendency": tendency,
                "faction": faction,
                "score": delta_score,
                "postCount": len(group),
                "targetMentions": mentions,
                "totalViews": views,
                "updatedAt": datetime.now(timezone.utc),
            }
        )
    return authors


_KO_PARTICLES = re.compile(
    r"(이|가|을|를|은|는|의|에|서|에서|에게|으로|로|와|과|랑|이랑|도|만|도|보다|처럼|부터|까지|에도|에서도|이다|입니다|했다|한다|했습니다|하는|한|하고|하며|하여|해서|됩니다|된다|됩니다|라는|라고|이라는|이라고|라며|이며)$"
)
_KO_STOPWORDS = {
    # 시간/날짜
    "이번", "지난", "오늘", "내일", "어제", "올해", "작년", "내년",
    # 조사/접속
    "관련", "대해", "통해", "위해", "따라", "대한", "위한", "이후",
    "있다", "없다", "됩니다", "한다", "됐다", "했다", "있는", "없는",
    "속에", "앞에", "뒤에", "함께", "또한", "하지만", "그러나", "그리고",
    "더불어", "특히", "이미", "아직", "모두", "모든", "각각", "각종",
    "주요", "새로운", "새로", "다시", "같은", "이런", "저런", "그런",
    "무엇", "어떤", "어디", "이것", "저것", "그것", "이를", "이에",
    "#shorts", "shorts", "short",
    # 전당대회 맥락에서 의미없는 일반 정치 단어
    "대표", "차기", "후보", "누가", "의원", "출마", "전대", "전당대회",
    "민주당", "당대표", "당원", "지지율", "여론", "조사", "결과",
    "발언", "입장", "공식", "논란", "관련해", "가능성", "이후",
    "오늘", "내일", "이번주", "다음주", "현재", "상황", "전망",
    "민주", "국민", "정치", "선거", "투표", "당선", "낙선",
    # 구어체/감탄사/무의미 단어
    "ㅋㅋ", "ㅋㅋㅋ", "ㅎㅎ", "ㄷㄷ", "ㅠㅠ", "ㅜㅜ", "ㅎㄷㄷ",
    "의원님", "나올까", "근데", "예정", "폐지", "아마", "혹시",
    "진짜", "정말", "완전", "너무", "매우", "굉장히", "엄청",
    "합니다", "입니다", "습니다", "했습니다", "됩니다", "있습니다",
    "것이다", "것은", "것을", "것도", "것만", "것과",
    "보도", "기자", "뉴스", "속보", "단독", "긴급", "특보",
    "이날", "당일", "같이", "처럼", "만큼", "보다", "부터", "까지",
    # 동사/형용사 어미형 (찾은, 강조, 밝혀 등)
    "찾은", "찾아", "찾기", "강조", "강조한", "강조해", "밝혀", "밝힌", "밝혀진",
    "나온", "나와", "나오는", "보인", "보여", "보이는", "알려", "알린", "알려진",
    "받은", "받아", "받는", "드러", "드러난", "드러낸", "내린", "내려", "내놓",
    "이어", "이은", "이을", "위해", "위한", "통해", "통한", "따른", "따라서",
    "하는", "하는데", "하면", "하며", "하여", "해야", "해서", "해도",
    "되는", "되며", "되어", "됐는", "되고", "되면", "됐다", "됩니",
    "있어", "있으며", "있는데", "없어", "없으며", "없는데",
    "것으로", "것이며", "것에", "것까지",
    # 숫자/단위 (단독)
    "1위", "2위", "3위", "1차", "2차", "3차",
    # 미디어 보도체 단어
    "인터뷰", "발표", "주장", "언급", "표명", "제시", "공개", "확인",
    "예정", "계획", "방침", "예상", "전망", "분석", "평가", "지적",
}

def _normalize_token(token: str) -> str:
    """한국어 조사/어미 제거 후 어근 반환."""
    token = token.strip("#.,!?·\"'()[]{}<>…|/\\@~%^&*+=`")
    # 숫자+단위 제거 (e.g. "3일", "20%", "1위")
    if re.match(r"^\d+[위일월년%개명건조억만원]*$", token):
        return ""
    # 조사 제거 (3글자 이상인 경우에만 — "서"같은 짧은 건 안 건드림)
    if len(token) >= 3:
        token = _KO_PARTICLES.sub("", token)
    return token

def _keyword_trend(items: list[RawItem], target: Target) -> dict:
    own = {w for w in target.search_keywords()}
    own |= {a for e in target.entities for a in ([e.name] + e.aliases)}
    # 자신의 키워드·인물 별칭도 제거 대상에 추가
    own_norm = {re.sub(r"\s+", "", w) for w in own}
    counter: Counter = Counter()
    for it in items:
        for raw_tok in it.title.split():
            token = _normalize_token(raw_tok)
            if not token or len(token) < 2:
                continue
            if token in _KO_STOPWORDS:
                continue
            # 한글 자음/모음만으로 된 토큰 제거 (ㅋㅋ, ㅎㅎ 등)
            if re.match(r"^[ㄱ-ㅎㅏ-ㅣ]+$", token):
                continue
            # 자체 키워드 제거 (정규화 비교)
            if re.sub(r"\s+", "", token) in own_norm:
                continue
            # 영어 1~2글자 단어 제거
            if re.match(r"^[a-zA-Z]{1,2}$", token):
                continue
            counter[token] += 1
    top = [{"word": w, "count": c} for w, c in counter.most_common(20)]
    now_kst = datetime.now(timezone(timedelta(hours=9)))
    return {"date": now_kst.strftime("%Y-%m-%d %H:%M"), "top": top}


async def run_target(target_id: str, store: FirestoreStore | None = None, collectors=None) -> dict:
    s = get_settings()
    store = store or FirestoreStore(s)
    target = store.get_target(target_id)
    if target is None:
        raise RuntimeError(f"target '{target_id}' 없음 — Firestore targets/{target_id} 확인")
    logger.info("=== [{}] 파이프라인 시작 ===", target.name)

    # 1) 수집 (collectors 주입 시 그걸 사용 — 테스트/시뮬레이션용)
    raw = await _collect_all(target, collectors)

    # 1-b) 특정 계정 모니터링 수집 (watchAccounts)
    watch_items = await _collect_watch_accounts(target, s, store=store)
    if watch_items:
        logger.info("[pipeline] 계정 모니터링 {}건 추가", len(watch_items))
        raw.extend(watch_items)

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

    # 메모리 보호 — 최대 100건만 Claude 분석
    if len(passed) > 100:
        logger.info("[pipeline] 통과 {}건 → 최신 100건으로 제한", len(passed))
        passed = sorted(passed, key=lambda x: x.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:100]

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
        notify_alert(a["grade"], a.get("summary", ""), a.get("type", ""), target.name)
        if a["grade"] in ("red", "orange"):
            try:
                import asyncio as _asyncio
                from .telegram_bot import push_red_alert
                cluster_obj = next((c for c in touched if c.grade == a["grade"]), None)
                title = cluster_obj.title if cluster_obj else a.get("type", "")
                posts = (cluster_obj.stats or {}).get("posts", len(cluster_obj.item_ids)) if cluster_obj else 0
                _asyncio.run(push_red_alert(a["grade"], title, a.get("summary", ""), posts))
            except Exception as _te:
                logger.warning("텔레그램 RED 알림 실패: {}", _te)
    store.save_authors(target_id, _aggregate_authors(passed))
    trend = _keyword_trend(passed, target)
    store.save_keyword_trend(target_id, trend["date"], trend)

    # 7) 여론조사 수집 (파이프라인 실행마다 갱신)
    try:
        from .collectors.poll_collector import collect_poll_news
        from datetime import timedelta
        poll_since = datetime.now(timezone.utc) - timedelta(days=90)
        polls = await collect_poll_news(since=poll_since)
        if polls:
            store.save_polls(target_id, polls)
            logger.info("[pipeline] 여론조사 {}건 저장", len(polls))
    except Exception as e:
        logger.warning("[pipeline] 여론조사 수집 실패: {}", e)

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
