"""end-to-end 파이프라인 시뮬레이션 — 네트워크/Firebase/Claude 없이 실제 코드 경로 검증.

- 실제 run_target / 필터 / 임베딩(tfidf) / 클러스터링 / 등급 / 보고서 코드를 그대로 실행
- 수집기는 합성 데이터 FakeCollector 로 주입
- 저장소는 인메모리 FakeStore (실제 직렬화 함수 _item_doc/_cluster_doc/_doc_to_item 재사용)

실행: python -m engine.tests.test_pipeline_sim
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from ..collectors.base import Collector, RawItem
from ..models import Entity, Target
from ..pipeline import run_target
from ..report import generate_report
from ..store.firestore import _cluster_doc, _doc_to_item, _item_doc

NOW = datetime.now(timezone.utc)


def _ri(platform, source_type, url, title, sentiment="neutral", author="", days_ago=0):
    it = RawItem(
        platform=platform,
        source_type=source_type,
        url=url,
        title=title,
        author=author,
        published_at=NOW - timedelta(days=days_ago),
        keyword="전당대회",
    )
    it.sentiment = sentiment  # 합성 감정(키 없을 때 Claude 가 보존)
    return it


class FakeCollector(Collector):
    name = "fake"

    def __init__(self, items: list[RawItem]) -> None:
        self._items = items

    async def collect(self, keywords, *, since=None, limit=100):
        # run 마다 새 복제본 반환 (파이프라인이 item 을 변형하므로)
        return [self._clone(it) for it in self._items]

    @staticmethod
    def _clone(it: RawItem) -> RawItem:
        c = RawItem(
            platform=it.platform, source_type=it.source_type, url=it.url,
            title=it.title, content=it.content, author=it.author,
            author_id=it.author_id, published_at=it.published_at,
            metrics=dict(it.metrics), keyword=it.keyword,
        )
        c.sentiment = it.sentiment
        return c


class FakeStore:
    """FirestoreStore 와 동일 인터페이스의 인메모리 구현 (실제 직렬화 함수 사용)."""

    def __init__(self, target: Target) -> None:
        self._target = target
        self.items: dict[str, dict] = {}
        self.clusters: dict[str, dict] = {}
        self.rejected: dict[str, dict] = {}
        self.alerts: list[dict] = []
        self.authors: dict[str, dict] = {}
        self.keyword_trend: dict[str, dict] = {}
        self.reports: dict[str, dict] = {}

    def get_target(self, tid):
        return self._target

    def recent_item_ids(self, tid, days=30):
        since = NOW - timedelta(days=days)
        return {i for i, d in self.items.items() if d["collectedAt"] >= since}

    def load_active_clusters(self, tid, window_days=30):
        from ..analysis.cluster import Cluster

        since = NOW - timedelta(days=window_days)
        out = []
        for cid, data in self.clusters.items():
            if data["lastSeen"] >= since:
                out.append(
                    Cluster(
                        cluster_id=cid,
                        title=data["title"],
                        rep_text=data.get("repText", data["title"]),
                        first_seen=data["firstSeen"],
                        last_seen=data["lastSeen"],
                        status=data["status"],
                        item_ids=list(data.get("itemIds", [])),
                        grade=data["grade"],
                        patterns=list(data.get("patterns", [])),
                        filter_tag=data["filterTag"],
                        reactivated=data["reactivated"],
                        summary=data.get("summary", ""),
                        stats=data.get("stats", {}),
                    )
                )
        return out

    def load_cluster_items(self, tid, cluster_id):
        return [_doc_to_item(d) for d in self.items.values() if d.get("clusterId") == cluster_id]

    def save_items(self, tid, items):
        for it in items:
            self.items[it.item_id] = _item_doc(it)

    def save_rejected(self, tid, items):
        for it in items:
            self.rejected[it.item_id] = _item_doc(it)

    def save_clusters(self, tid, clusters):
        for c in clusters:
            self.clusters[c.cluster_id] = {**self.clusters.get(c.cluster_id, {}), **_cluster_doc(c)}

    def add_alert(self, tid, a):
        self.alerts.append(a)

    def save_authors(self, tid, authors):
        # 실제 store 의 Increment 누적을 모사
        for a in authors:
            cur = self.authors.get(a["authorId"], {"postCount": 0, "targetMentions": 0, "score": 0})
            self.authors[a["authorId"]] = {
                "authorId": a["authorId"],
                "name": a["name"],
                "mainPlatform": a["mainPlatform"],
                "postCount": cur["postCount"] + a["postCount"],
                "targetMentions": cur["targetMentions"] + a["targetMentions"],
                "score": cur["score"] + a["score"],
            }

    def save_keyword_trend(self, tid, date, doc):
        self.keyword_trend[date] = doc

    def save_polls(self, tid, polls):
        pass  # 테스트에서 여론조사 저장 불필요

    def save_report(self, tid, rid, doc):
        self.reports[rid] = doc

    def count_items_since(self, tid, since):
        return sum(1 for d in self.items.values() if d["collectedAt"] >= since)

    def alerts_since(self, tid, since):
        return [a for a in self.alerts if a["createdAt"] >= since]


def _target() -> Target:
    return Target(
        id="sim",
        name="시뮬 전당대회",
        keywords=["전당대회"],
        entities=[Entity("김민석", "당대표후보"), Entity("정청래", "당대표후보")],
        sources={"naver": True},
    )


def _run1_items():
    return [
        _ri("naver_news", "news", "https://n.news/1", "김민석 부동산 의혹 논란 확산", "negative", "기자A"),
        _ri("naver_blog", "blog", "https://blog/2", "김민석 부동산 의혹 일파만파", "negative", "블로거B"),
        _ri("youtube", "video", "https://yt/3", "김민석 부동산 의혹 단독 폭로", "attack", "채널C"),
        _ri("naver_news", "news", "https://n.news/4", "정청래 정책 토론회 호평 이어져", "positive", "기자D"),
        _ri("dcinside", "community", "https://dc/5", "전당대회 흥행 기대 크다", "neutral", "익명"),
        _ri("naver_news", "news", "https://n.news/1", "김민석 부동산 의혹 논란 확산", "negative"),  # 중복
        _ri("naver_blog", "blog", "https://blog/9", "맛집 추천 무료 체험 이벤트 안내", "neutral"),     # 노이즈
        _ri("naver_news", "news", "https://n.news/8", "프로야구 한화 9연승 질주", "neutral"),          # 무관
    ]


async def _sim():
    target = _target()
    store = FakeStore(target)

    # ── RUN 1 ──
    r1 = await run_target("sim", store=store, collectors=[FakeCollector(_run1_items())], skip_sns=True)
    assert r1["passed"] == 5, r1                 # 1~5 통과
    assert r1["rejected"] == 3, r1               # 중복·노이즈·무관
    assert len(store.items) == 5, len(store.items)
    assert len(store.rejected) == 3
    # 김민석 부정 클러스터: 3매체, red
    big = max(store.clusters.values(), key=lambda d: d["itemCount"])
    assert big["itemCount"] == 3, big["itemCount"]
    assert "부정다플랫폼" in big["patterns"], big["patterns"]
    assert "매체다양성" in big["patterns"], big["patterns"]
    assert big["grade"] == "red", big["grade"]
    assert big["filterTag"] == "대응필요", big["filterTag"]
    assert len(store.alerts) >= 1, store.alerts
    assert len(store.authors) >= 4, list(store.authors)
    assert store.keyword_trend, "키워드 트렌드 비어있음"
    print(f"✓ RUN1: 통과5/거부3, 대표클러스터 {big['itemCount']}건 {big['grade']} {big['patterns']}")

    big_id = [cid for cid, d in store.clusters.items() if d["itemCount"] == 3][0]
    n_clusters_after_1 = len(store.clusters)

    # ── RUN 2 ── 같은 이슈에 새 글 유입(작성자 누적 포함) + 중복 재유입
    run2 = [
        _ri("naver_cafe", "cafe", "https://cafe/10", "김민석 부동산 의혹 검찰 수사 착수", "negative", "회원E"),
        _ri("naver_news", "news", "https://n.news/11", "김민석 부동산 의혹 추가 폭로 나와", "negative", "기자A"),
        _ri("naver_news", "news", "https://n.news/1", "김민석 부동산 의혹 논란 확산", "negative"),  # 이미 수집됨→중복
    ]
    r2 = await run_target("sim", store=store, collectors=[FakeCollector(run2)], skip_sns=True)
    assert r2["passed"] == 2, r2                  # 새 글 2건
    assert r2["rejected"] == 1, r2                # 중복 1건
    assert store.clusters[big_id]["itemCount"] == 5, store.clusters[big_id]["itemCount"]
    assert len(store.clusters) == n_clusters_after_1, "중복인데 새 클러스터 생성됨"
    # 작성자 누적: 기자A 는 run1(1) + run2(1) = 2
    assert store.authors["기자A"]["postCount"] == 2, store.authors["기자A"]
    print(f"✓ RUN2: 신규2/중복1, 클러스터 5건 증가, 작성자 누적(기자A postCount=2)")

    # ── 보고서 ──
    rep = generate_report("sim", store=store, report_type="daily")
    assert rep["totals"]["mentions"] == 7, rep["totals"]
    assert rep["totals"]["uniqueIssues"] >= 1
    assert store.reports, "보고서 저장 안됨"
    print(f"✓ REPORT: 언급 {rep['totals']['mentions']} / 이슈 {rep['totals']['uniqueIssues']} / 알림 {rep['totals']['alerts']}")


def test_serialization_roundtrip():
    it = _ri("naver_news", "news", "https://x/1?utm_source=a", "테스트 <b>제목</b>", "negative", "기자")
    it.cluster_id = "abc123"
    it.matched_entities = ["김민석"]
    doc = _item_doc(it)
    back = _doc_to_item(doc)
    assert back.platform == "naver_news"
    assert back.sentiment == "negative"
    assert back.cluster_id == "abc123"
    assert back.title == "테스트 제목", back.title  # HTML 제거 확인
    assert doc["canonicalUrl"] == "https://x/1", doc["canonicalUrl"]  # 추적 파라미터 제거
    print("✓ 직렬화 라운드트립 (HTML 제거·canonical·필드 보존)")


def main():
    test_serialization_roundtrip()
    asyncio.run(_sim())
    print("\n=== 파이프라인 시뮬레이션 전부 통과 ===")


if __name__ == "__main__":
    main()
