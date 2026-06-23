// engine/collectors/sites.py 와 동기화된 사이트 목록 (설정 UI 용).
export interface SiteOption {
  key: string;
  name: string;
  login?: boolean;
  tune?: boolean; // 실접속 미검증 — 활성 시 URL/패턴 튜닝 필요
}

export const SITE_GROUPS: { label: string; sites: SiteOption[] }[] = [
  {
    label: "커뮤니티 · 포털 (검증 완료)",
    sites: [
      { key: "dcinside", name: "디시인사이드" },
      { key: "clien", name: "클리앙" },
      { key: "ruliweb", name: "루리웹" },
      { key: "ppomppu", name: "뽐뿌" },
      { key: "mlbpark", name: "엠엘비파크" },
      { key: "fmkorea", name: "에펨코리아" },
      { key: "natepann", name: "네이트판" },
      { key: "todayhumor", name: "오늘의유머" },
      { key: "bobaedream", name: "보배드림" },
      { key: "daum_news", name: "다음뉴스" },
      { key: "nate_news", name: "네이트뉴스" },
    ],
  },
  {
    label: "추가 사이트 (튜닝 필요)",
    sites: [
      { key: "theqoo", name: "더쿠", login: true, tune: true },
      { key: "instiz", name: "인스티즈", tune: true },
      { key: "inven", name: "인벤", tune: true },
      { key: "ygosu", name: "와이고수", tune: true },
    ],
  },
  {
    label: "로그인 필요 (login.py 로 세션 준비)",
    sites: [
      { key: "naver_cafe_login", name: "네이버 카페", login: true },
      { key: "x", name: "X(트위터)", login: true },
      { key: "instagram", name: "인스타그램", login: true },
      { key: "threads", name: "스레드", login: true },
      { key: "facebook", name: "페이스북", login: true },
    ],
  },
];
