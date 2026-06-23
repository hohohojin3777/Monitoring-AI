"""오프라인 코어 테스트 — 네트워크/Firebase/Claude 없이 두뇌 로직 검증.

실행: python -m engine.tests.test_core   (engine venv 권장)
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..analysis.cluster import assign_clusters
from ..analysis.embed import TfidfEmbedder
from ..analysis.filters import RejectFilter
from ..analysis.grade import grade_cluster
from ..collectors.base import RawItem, canonical_url
from ..config import get_settings


def _item(platform, title, content="", sentiment="neutral", url=None, published=None):
    it = RawItem(
        platform=platform,
        source_type="news",
        url=url or f"https://{platform}.example/{abs(hash(title)) % 99999}",
        title=title,
        content=content,
        published_at=published or datetime.now(timezone.utc),
        keyword="전당대회",
    )
    it.sentiment = sentiment
    return it


def test_canonical_url():
    a = canonical_url("https://Example.com/path/?utm_source=x&id=3#frag")
    assert a == "https://example.com/path?id=3", a
    print("✓ canonical_url")


def test_filter():
    items = [
        _item("naver_news", "민주당 전당대회 김민석 출마 선언"),         # 관련 통과
        _item("naver_news", "민주당 전당대회 김민석 출마 선언"),         # 중복 → 거부
        _item("naver_blog", "오늘 점심 맛집 추천 무료 체험 이벤트"),     # 노이즈+무관 → 거부
        _item("naver_news", "프로야구 한화 승리"),                       # 무관 → 거부
    ]
    rf = RejectFilter(keywords=["전당대회"], entities=["김민석"], window_days=30)
    passed, rejected = rf.partition(items)
    assert len(passed) == 1, [p.title for p in passed]
    reasons = sorted(r.reject_reason for r in rejected)
    assert reasons == ["duplicate", "irrelevant", "noise"], reasons
    assert passed[0].matched_entities == ["김민석"], passed[0].matched_entities
    print("✓ filter (통과1 / 거부3, 사유 정확)")


def test_cluster_and_grade():
    # 같은 사건(부정)이 3개 매체에서 + 위험 키워드 → 다매체/부정 패턴
    items = [
        _item("naver_news", "김민석 부동산 의혹 논란 확산", sentiment="negative"),
        _item("naver_blog", "김민석 부동산 의혹 논란 일파만파", sentiment="negative"),
        _item("youtube", "김민석 부동산 의혹 단독 폭로", sentiment="attack"),
        _item("naver_news", "정청래 정책 토론회 호평", sentiment="positive"),  # 다른 이슈
    ]
    embedder = TfidfEmbedder()
    touched = assign_clusters([], items, embedder, threshold=0.25)
    # 부정 3건은 한 클러스터, 정청래 1건은 별도 → 최소 2개 클러스터
    assert len(touched) >= 2, len(touched)
    biggest = max(touched, key=lambda c: len(c.item_ids))
    assert len(biggest.item_ids) >= 3, [len(c.item_ids) for c in touched]

    s = get_settings()
    cluster_items = [it for it in items if it.cluster_id == biggest.cluster_id]
    graded = grade_cluster(biggest, cluster_items, s)
    assert "부정다플랫폼" in graded.patterns, graded.patterns
    assert "매체다양성" in graded.patterns, graded.patterns
    assert graded.grade in ("orange", "red", "yellow"), graded.grade
    print(f"✓ cluster+grade (대표 클러스터 {len(biggest.item_ids)}건, "
          f"patterns={graded.patterns}, grade={graded.grade})")


def main():
    test_canonical_url()
    test_filter()
    test_cluster_and_grade()
    print("\n=== 모든 코어 테스트 통과 ===")


if __name__ == "__main__":
    main()
