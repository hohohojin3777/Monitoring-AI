"""게시일 파서 + no_date 필터 검증.

실행: python -m engine.tests.test_dateparse
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..analysis.filters import RejectFilter
from ..collectors.base import RawItem
from ..collectors.dateparse import parse_korean_date

NOW = datetime(2026, 6, 14, 15, 0, tzinfo=timezone.utc)


def test_parse():
    # 절대 일자
    assert parse_korean_date("허벅지하앍 26/06/14 06:08 412 1/6", NOW).date() == datetime(2026, 6, 14).date()
    assert parse_korean_date("점찍는노인 2026-06-13 20:43", NOW).date() == datetime(2026, 6, 13).date()
    assert parse_korean_date("국민의힘 비대위 갤러리2026.06.14 15:33", NOW).date() == datetime(2026, 6, 14).date()
    # 시간만 → 오늘
    assert parse_korean_date("야야요야 1837 14:38", NOW).date() == NOW.date()
    # 상대
    assert abs((parse_korean_date("3시간 전", NOW) - (NOW - timedelta(hours=3))).total_seconds()) < 2
    assert parse_korean_date("어제 13:00", NOW).date() == (NOW - timedelta(days=1)).date()
    # 오탐 방지: 추천비율(1/6, 슬래시)·조회수(1.2만)·본문숫자는 날짜 아님
    assert parse_korean_date("추천 1/6 비추 0", NOW) is None, "슬래시 비율을 날짜로 오인"
    assert parse_korean_date("조회 1.2만 댓글 34", NOW) is None, "조회수를 날짜로 오인"
    assert parse_korean_date("박근혜 영익 10배 이재명도 10배", NOW) is None
    assert parse_korean_date("", NOW) is None
    # 작년 글 → 과거 일자로 파싱(윈도우에서 걸러질 근거)
    old = parse_korean_date("작년글 2025.06.14 10:00", NOW)
    assert old.year == 2025
    print("✓ 날짜 파서 (절대·시간·상대 OK, 비율/조회수 오탐 차단)")


def _scraped(published):
    it = RawItem(platform="dcinside", source_type="community",
                 url="https://dc/" + str(abs(hash(published or "x")) % 9999),
                 title="이재명 전당대회 관련 글", published_at=published)
    return it


def test_no_date_filter():
    # 게시일 미상 스크랩 글 → require 시 no_date 거부
    items = [
        _scraped(NOW - timedelta(days=1)),          # 최근 → 통과
        _scraped(None),                              # 날짜 미상 → no_date 거부
        _scraped(datetime(2025, 1, 1, tzinfo=timezone.utc)),  # 작년 → old_date 거부
        RawItem(platform="naver_news", source_type="news",
                url="https://n/1", title="이재명 전당대회 기사", published_at=None),  # API 무날짜 → 통과
    ]
    rf = RejectFilter(keywords=["전당대회"], entities=["이재명"],
                      window_days=30, require_scraped_date=True)
    passed, rejected = rf.partition(items)
    reasons = sorted(r.reject_reason for r in rejected)
    assert reasons == ["no_date", "old_date"], reasons
    # 최근 스크랩글 + API무날짜글 통과
    assert len(passed) == 2, [p.platform for p in passed]
    print("✓ no_date 필터 (스크랩 무날짜 거부 / API 무날짜·최근글 통과)")

    # require=False 면 무날짜도 보관
    rf2 = RejectFilter(keywords=["전당대회"], entities=["이재명"],
                       window_days=30, require_scraped_date=False)
    passed2, _ = rf2.partition([_scraped(None)])
    assert len(passed2) == 1, "require=False 인데 무날짜가 거부됨"
    print("✓ scrape_require_date=False 면 무날짜 보관")


def main():
    test_parse()
    test_no_date_filter()
    print("\n=== 날짜 수집 로직 전부 통과 ===")


if __name__ == "__main__":
    main()
