"""한국어 게시일 파서 — 스크랩한 검색결과 행 텍스트에서 게시일자를 추출.

지원 형식:
- 상대: "3분 전", "2시간 전", "5일 전", "어제", "방금", "오늘"
- 절대: "2026.06.14", "2026-06-14 15:33", "26/06/14 06:08"
- 시간만: "14:38"  → 오늘 (커뮤니티는 당일 글에 시간만 표기)

오탐 방지를 위해 'MM/DD'(슬래시·추천비율 1/6 등)·조회수(1.2만) 같은 모호한 숫자는 날짜로
해석하지 않는다. 날짜를 못 찾으면 None → 호출부에서 (옵션에 따라) 수집 제외할 수 있다.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

# 절대일자: 두 개의 구분자 필요 (YYYY/YY . - / MM DD [HH:MM])
_FULL = re.compile(
    r"(\d{2,4})[.\-/](\d{1,2})[.\-/](\d{1,2})(?:[ T]+(\d{1,2}):(\d{2}))?"
)
_TIME = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
_REL = re.compile(r"(\d+)\s*(분|시간|일|주|개월|달|년)\s*전")

_REL_DELTA = {
    "분": lambda n: timedelta(minutes=n),
    "시간": lambda n: timedelta(hours=n),
    "일": lambda n: timedelta(days=n),
    "주": lambda n: timedelta(weeks=n),
    "개월": lambda n: timedelta(days=30 * n),
    "달": lambda n: timedelta(days=30 * n),
    "년": lambda n: timedelta(days=365 * n),
}


def parse_korean_date(text: str, now: datetime | None = None) -> datetime | None:
    if not text:
        return None
    now = now or datetime.now(timezone.utc)

    # 1) 상대 표현 (마지막 매치 우선)
    rels = _REL.findall(text)
    if rels:
        n, unit = rels[-1]
        return now - _REL_DELTA[unit](int(n))
    if "어제" in text:
        return now - timedelta(days=1)
    if "방금" in text or "오늘" in text:
        return now

    # 2) 절대 일자 (마지막 매치 = 보통 메타영역)
    fulls = list(_FULL.finditer(text))
    if fulls:
        g = fulls[-1]
        y = int(g.group(1))
        if y < 100:
            y += 2000
        try:
            return datetime(
                y, int(g.group(2)), int(g.group(3)),
                int(g.group(4) or 0), int(g.group(5) or 0),
                tzinfo=timezone.utc,
            )
        except ValueError:
            return None

    # 3) 시간만 → 오늘
    times = _TIME.findall(text)
    if times:
        hh, mn = int(times[-1][0]), int(times[-1][1])
        if hh <= 23 and mn <= 59:
            return now.replace(hour=hh, minute=mn, second=0, microsecond=0)

    return None
