"""수집 사이트 레지스트리 — 검색 URL + 글 링크 패턴.

`{q}` 자리에 키워드(URL 인코딩)가 들어간다. BrowserCollector 가 검색 페이지를 열고
link_pattern(정규식)에 맞는 링크만 '글'로 추출한다(목록·로그인·광고 링크 배제).

verified=True 는 2026-06 Playwright 실접속으로 검색 동작·패턴을 확인한 사이트.
verified=False 는 봇 보호/로그인/검색파라미터 문제로 추가 튜닝이 필요(기본 비활성).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchSite:
    key: str
    name: str
    platform: str
    search_url: str                 # "{q}" 포함
    source_type: str = "community"  # community | news | sns
    requires_login: bool = False
    link_pattern: str | None = None # 글 링크 판별 정규식 (href 에 대해 search)
    base_url: str = ""
    verified: bool = False
    wait_ms: int = 1500             # 동적 로딩 대기(ms)
    min_text_len: int = 6
    # 검색 방식:
    #  GET  : search_url 의 {q} 치환 후 이동 (기본)
    #  POST : base_url 로딩 후 post_fields 로 폼 제출 ({q}·{since} 치환)
    #  FORM : base_url 로딩 후 search_input(CSS) 에 키워드 입력 → 그 폼 제출
    #         (세션 토큰 ds 등 hidden 필드가 자동 포함됨, 예: 에펨코리아)
    search_method: str = "GET"
    post_fields: dict | None = None
    search_input: str | None = None
    # date_filtered=True: 사이트가 검색에서 기간(startDate)을 직접 제한 → 행에 날짜 없어도 무방
    date_filtered: bool = False


# ── 검증 완료 커뮤니티 (실접속 확인) ───────────────────────────
_COMMUNITY = [
    SearchSite("dcinside", "디시인사이드", "dcinside",
               "https://search.dcinside.com/combine/q/{q}",
               link_pattern=r"/board/view/", base_url="https://www.dcinside.com", verified=True),
    SearchSite("clien", "클리앙", "clien",
               "https://www.clien.net/service/search?q={q}&sort=recency",
               link_pattern=r"/service/board/\w+/\d+", base_url="https://www.clien.net", verified=True),
    SearchSite("ruliweb", "루리웹", "ruliweb",
               "https://bbs.ruliweb.com/search?q={q}",
               link_pattern=r"/read/\d+", base_url="https://bbs.ruliweb.com",
               verified=True, wait_ms=3000),  # 구글 CSE 로딩 대기
    SearchSite("ppomppu", "뽐뿌", "ppomppu",
               "https://www.ppomppu.co.kr/search_bbs.php?search_type=sub_memo&keyword={q}",
               link_pattern=r"/zboard/view\.php", base_url="https://www.ppomppu.co.kr", verified=True),
    SearchSite("mlbpark", "엠엘비파크", "mlbpark",
               "https://mlbpark.donga.com/mp/b.php?m=search&select=sct&query={q}&b=bullpen",
               link_pattern=r"b\.php\?id=\d", base_url="https://mlbpark.donga.com", verified=True),
    SearchSite("natepann", "네이트판", "natepann",
               "https://pann.nate.com/search/talk?q={q}",
               link_pattern=r"/talk/\d+", base_url="https://pann.nate.com", verified=True),
    SearchSite("todayhumor", "오늘의유머", "todayhumor",
               "http://www.todayhumor.co.kr/board/list.php?table=sisa&kind=search&keyfield=subject&keyword={q}",
               link_pattern=r"view\.php\?table=", base_url="https://www.todayhumor.co.kr", verified=True),
    # ── 미검증(기본 비활성, 활성 시 추가 튜닝 필요) ──
    SearchSite("fmkorea", "에펨코리아", "fmkorea",
               "https://www.fmkorea.com/search.php",
               link_pattern=r"fmkorea\.com/\d{8,}", base_url="https://www.fmkorea.com/",
               verified=True, search_method="FORM", search_input="#IS_SEARCH",
               wait_ms=3000),  # 통합검색 폼(ds 토큰) → 구글 CSE(날짜순)
    SearchSite("theqoo", "더쿠", "theqoo",
               "https://theqoo.net/index.php?mid=square&search_target=title_content&search_keyword={q}",
               link_pattern=r"/\w+/\d+", base_url="https://theqoo.net",
               verified=False, requires_login=True),  # 검색 로그인 필요
    SearchSite("instiz", "인스티즈", "instiz",
               "https://www.instiz.net/name?category=1&k={q}",
               link_pattern=r"/name/\d+", base_url="https://www.instiz.net", verified=False),
    SearchSite("bobaedream", "보배드림", "bobaedream",
               "https://www.bobaedream.co.kr/search",
               link_pattern=r"/view\?code=", base_url="https://www.bobaedream.co.kr",
               verified=True, date_filtered=True, search_method="POST",
               post_fields={"keyword": "{q}", "searchField": "ALL", "sort": "DATE",
                            "startDate": "{since}", "colle": "community", "page": "1"}),
    SearchSite("inven", "인벤", "inven",
               "https://www.inven.co.kr/search/webzine/news/{q}",
               link_pattern=r"/\d{6,}", base_url="https://www.inven.co.kr", verified=False),
    SearchSite("ygosu", "와이고수", "ygosu",
               "https://www.ygosu.com/search/?type=community&keyword={q}",
               link_pattern=r"/community/", base_url="https://www.ygosu.com", verified=False),
]

# ── 검증 완료 포털 뉴스 ────────────────────────────────────────
_PORTAL = [
    SearchSite("daum_news", "다음뉴스", "daum_news",
               "https://search.daum.net/search?w=news&sort=recency&q={q}",
               source_type="news", link_pattern=r"v\.daum\.net/v/\d+",
               base_url="https://www.daum.net", verified=True),
    SearchSite("nate_news", "네이트뉴스", "nate_news",
               "https://news.nate.com/search?q={q}",
               source_type="news", link_pattern=r"news\.nate\.com/view/",
               base_url="https://news.nate.com", verified=True),
]

# ── 로그인 필요 (영구 프로필 세션 사용, 기본 비활성) ───────────
_LOGIN = [
    SearchSite("naver_cafe_login", "네이버 카페(로그인)", "naver_cafe",
               "https://search.naver.com/search.naver?ssc=tab.cafe.all&query={q}",
               source_type="community", requires_login=True,
               link_pattern=r"cafe\.naver\.com|/article", base_url="https://cafe.naver.com"),
    SearchSite("x", "X(트위터)", "x",
               "https://x.com/search?q={q}&f=live", source_type="sns",
               requires_login=True, link_pattern=r"/status/\d+", base_url="https://x.com"),
    SearchSite("instagram", "인스타그램", "instagram",
               "https://www.instagram.com/explore/search/keyword/?q={q}",
               source_type="sns", requires_login=True, link_pattern=r"/p/|/reel/",
               base_url="https://www.instagram.com"),
    SearchSite("threads", "스레드", "threads",
               "https://www.threads.net/search?q={q}", source_type="sns",
               requires_login=True, link_pattern=r"/post/", base_url="https://www.threads.net"),
    SearchSite("facebook", "페이스북", "facebook",
               "https://www.facebook.com/search/posts?q={q}", source_type="sns",
               requires_login=True, link_pattern=r"/posts/|/permalink/|story_fbid",
               base_url="https://www.facebook.com"),
]

ALL_SITES: list[SearchSite] = _COMMUNITY + _PORTAL + _LOGIN
_BY_KEY = {s.key: s for s in ALL_SITES}

# 실접속 검증 완료 — seed 기본 활성
DEFAULT_SITE_KEYS = [s.key for s in ALL_SITES if s.verified]


def get_sites(keys: list[str]) -> list[SearchSite]:
    if "all" in keys:
        return list(ALL_SITES)
    return [_BY_KEY[k] for k in keys if k in _BY_KEY]


def all_site_keys() -> list[str]:
    return [s.key for s in ALL_SITES]
