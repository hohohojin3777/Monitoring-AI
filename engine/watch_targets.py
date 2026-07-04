"""HORIZON0817 모니터링 대상 마스터 목록.

tier: S / A / B / C
category: candidate / key_person / lawmaker / party_org / core_speaker / media / journalist
relationStatus: 본인 / 확정 지지 / 우호 가능 / 관망 / 비판 / 확인 필요
crawlIntervalMinutes: tier S=60, A=120, B=180
"""
from __future__ import annotations

WATCH_TARGETS: list[dict] = [

    # ════════════════════════════════════════════
    # S급 — 후보 본인 (60분)
    # ════════════════════════════════════════════
    {
        "name": "김민석",
        "category": "candidate",
        "tier": "S",
        "relationCandidate": "김민석",
        "relationStatus": "본인",
        "mustMonitor": True,
        "crawlIntervalMinutes": 60,
        "platforms": {
            "facebook": {"url": "https://www.facebook.com/minseok.kim.376043", "accountId": "minseok.kim.376043"},
            "x":        {"url": "https://x.com/ms2030", "accountId": "ms2030"},
            "youtube":  {"channelId": "UC0xm3nsJXdMEA6ILZRHCXvQ", "handle": "@kimminseok2030"},
        },
        "enabled": True,
    },
    {
        "name": "정청래",
        "category": "candidate",
        "tier": "S",
        "relationCandidate": "정청래",
        "relationStatus": "본인",
        "mustMonitor": True,
        "crawlIntervalMinutes": 60,
        "platforms": {
            "facebook": {"url": "https://www.facebook.com/cheongrae1", "accountId": "cheongrae1"},
            "x":        {"url": "https://x.com/ssaribi", "accountId": "ssaribi"},
            "youtube":  {"channelId": "UCNRVHeIfz11ggS_JJvJFTnw", "handle": "@ssaribi"},
        },
        "enabled": True,
    },
    {
        "name": "송영길",
        "category": "candidate",
        "tier": "S",
        "relationCandidate": "송영길",
        "relationStatus": "본인",
        "mustMonitor": True,
        "crawlIntervalMinutes": 60,
        "platforms": {
            "facebook": {"url": "https://www.facebook.com/songyounggil63", "accountId": "songyounggil63"},
            "x":        {"url": "https://x.com/Bulloger", "accountId": "Bulloger"},
            "youtube":  {"channelId": "UC6Swqra8BqePCs1ymFCdDMQ", "handle": "@songyounggil"},
        },
        "enabled": True,
    },
    {
        "name": "고민정",
        "category": "candidate",
        "tier": "S",
        "relationCandidate": "고민정",
        "relationStatus": "본인",
        "mustMonitor": True,
        "crawlIntervalMinutes": 60,
        "platforms": {
            "facebook": {"url": "https://www.facebook.com/gominjeong", "accountId": "gominjeong"},
            "x":        {"url": "https://x.com/gominjeong", "accountId": "gominjeong"},
        },
        "enabled": True,
    },
    {
        "name": "김용민",
        "category": "key_person",
        "tier": "A",
        "currentCandidate": False,
        "candidateGroup": "former_or_potential",
        "relationCandidate": "김용민",
        "relationStatus": "본인",
        "mustMonitor": True,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "facebook": {"url": "https://www.facebook.com/fopeople", "accountId": "fopeople"},
            "x":        {"url": "https://x.com/fopeopler", "accountId": "fopeopler"},
            "youtube":  {"channelId": "UCm6jDQGxHHBSHeHjin1bBaQ", "handle": "@kimyongmin"},
        },
        "enabled": True,
    },

    # ════════════════════════════════════════════
    # S급 — 핵심 미디어·유튜버 (60분)
    # ════════════════════════════════════════════
    {
        "name": "더불어민주당",
        "category": "party_org",
        "tier": "S",
        "relationCandidate": "중립",
        "relationStatus": "확인 필요",
        "mustMonitor": True,
        "crawlIntervalMinutes": 60,
        "platforms": {
            "facebook": {"url": "https://www.facebook.com/TheNewDemocraticParty", "accountId": "TheNewDemocraticParty"},
            "x":        {"url": "https://x.com/TheMinjoo", "accountId": "TheMinjoo"},
            "youtube":  {"handle": "@더불어민주당"},
        },
        "enabled": True,
    },
    {
        "name": "김어준의뉴스공장",
        "category": "core_speaker",
        "tier": "S",
        "relationCandidate": "중립",
        "relationStatus": "확인 필요",
        "mustMonitor": True,
        "crawlIntervalMinutes": 60,
        "platforms": {
            "youtube": {"handle": "@뉴스공장"},
        },
        "enabled": True,
    },
    {
        "name": "매불쇼",
        "category": "core_speaker",
        "tier": "S",
        "relationCandidate": "중립",
        "relationStatus": "확인 필요",
        "mustMonitor": True,
        "crawlIntervalMinutes": 60,
        "platforms": {
            "youtube": {"handle": "@매불쇼"},
        },
        "enabled": True,
    },
    {
        "name": "이동형TV",
        "category": "core_speaker",
        "tier": "S",
        "relationCandidate": "김민석",
        "relationStatus": "우호 가능",
        "mustMonitor": True,
        "crawlIntervalMinutes": 60,
        "platforms": {
            "youtube": {"handle": "@이동형tv"},
        },
        "enabled": True,
    },
    {
        "name": "서울의소리",
        "category": "media",
        "tier": "S",
        "relationCandidate": "중립",
        "relationStatus": "확인 필요",
        "mustMonitor": True,
        "crawlIntervalMinutes": 60,
        "platforms": {
            "youtube": {"handle": "@서울의소리TV"},
            "x":       {"url": "https://x.com/Seoul_Voice", "accountId": "Seoul_Voice"},
        },
        "enabled": True,
    },
    {
        "name": "박시영TV",
        "category": "core_speaker",
        "tier": "S",
        "relationCandidate": "중립",
        "relationStatus": "확인 필요",
        "mustMonitor": True,
        "crawlIntervalMinutes": 60,
        "platforms": {
            "youtube": {"handle": "@박시영tv"},
        },
        "enabled": True,
    },
    {
        "name": "새날",
        "category": "core_speaker",
        "tier": "S",
        "relationCandidate": "중립",
        "relationStatus": "확인 필요",
        "mustMonitor": True,
        "crawlIntervalMinutes": 60,
        "platforms": {
            "youtube": {"handle": "@새날tv"},
        },
        "enabled": True,
    },
    {
        "name": "김용민TV",
        "category": "core_speaker",
        "tier": "S",
        "relationCandidate": "김용민",
        "relationStatus": "우호 가능",
        "mustMonitor": True,
        "crawlIntervalMinutes": 60,
        "platforms": {
            "youtube": {"handle": "@김용민tv"},
        },
        "enabled": True,
    },
    {
        "name": "정치읽어주는여자",
        "category": "core_speaker",
        "tier": "S",
        "relationCandidate": "정청래",
        "relationStatus": "우호 가능",
        "mustMonitor": True,
        "crawlIntervalMinutes": 60,
        "platforms": {
            "youtube": {"handle": "@정치읽어주는여자"},
        },
        "enabled": True,
    },

    # ════════════════════════════════════════════
    # A급 — 지지 의원 / 주요 인사 (120분)
    # ════════════════════════════════════════════

    # 김민석 캠프
    {
        "name": "정성호",
        "category": "lawmaker",
        "tier": "A",
        "relationCandidate": "김민석",
        "relationStatus": "확정 지지",
        "mustMonitor": False,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "facebook": {"url": "https://www.facebook.com/sunghojeong", "accountId": "sunghojeong"},
            "x":        {"url": "https://x.com/sunghojeong01", "accountId": "sunghojeong01"},
        },
        "enabled": True,
    },
    {
        "name": "홍익표",
        "category": "lawmaker",
        "tier": "A",
        "relationCandidate": "김민석",
        "relationStatus": "확정 지지",
        "mustMonitor": False,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "facebook": {"url": "https://www.facebook.com/hongikpyo", "accountId": "hongikpyo"},
            "x":        {"url": "https://x.com/hongikpyo", "accountId": "hongikpyo"},
        },
        "enabled": True,
    },
    {
        "name": "이원욱",
        "category": "lawmaker",
        "tier": "A",
        "relationCandidate": "김민석",
        "relationStatus": "확정 지지",
        "mustMonitor": False,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "x": {"url": "https://x.com/wooklee64", "accountId": "wooklee64"},
        },
        "enabled": True,
    },
    {
        "name": "조응천",
        "category": "lawmaker",
        "tier": "A",
        "relationCandidate": "김민석",
        "relationStatus": "확정 지지",
        "mustMonitor": False,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "facebook": {"url": "https://www.facebook.com/eungcheon.cho", "accountId": "eungcheon.cho"},
        },
        "enabled": True,
    },

    # 정청래 캠프
    {
        "name": "추미애",
        "category": "lawmaker",
        "tier": "A",
        "relationCandidate": "정청래",
        "relationStatus": "확정 지지",
        "mustMonitor": False,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "facebook": {"url": "https://www.facebook.com/chumiae", "accountId": "chumiae"},
            "x":        {"url": "https://x.com/chumiae", "accountId": "chumiae"},
        },
        "enabled": True,
    },
    {
        "name": "민형배",
        "category": "lawmaker",
        "tier": "A",
        "relationCandidate": "정청래",
        "relationStatus": "확정 지지",
        "mustMonitor": False,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "facebook": {"url": "https://www.facebook.com/minhyungbae", "accountId": "minhyungbae"},
        },
        "enabled": True,
    },
    {
        "name": "서영교",
        "category": "lawmaker",
        "tier": "A",
        "relationCandidate": "정청래",
        "relationStatus": "확정 지지",
        "mustMonitor": False,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "facebook": {"url": "https://www.facebook.com/seoyoungjyo", "accountId": "seoyoungjyo"},
            "x":        {"url": "https://x.com/youngjyo", "accountId": "youngjyo"},
        },
        "enabled": True,
    },

    # 대권·차기주자 모니터링 (전당대회 후보군 아님)
    {
        "name": "우원식",
        "category": "lawmaker",
        "tier": "A",
        "relationCandidate": None,
        "relationStatus": "대권 모니터링",
        "mustMonitor": False,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "facebook": {"url": "https://www.facebook.com/wonsik.woo", "accountId": "wonsik.woo"},
            "x":        {"url": "https://x.com/woo_wonsik", "accountId": "woo_wonsik"},
        },
        "enabled": True,
    },

    # ════════════════════════════════════════════
    # A급 — 정치 미디어·채널 (120분)
    # ════════════════════════════════════════════
    {
        "name": "뷰리핑",
        "category": "media",
        "tier": "A",
        "relationCandidate": "김민석",
        "relationStatus": "우호 가능",
        "mustMonitor": False,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "youtube": {"handle": "@뷰리핑"},
        },
        "enabled": True,
    },
    {
        "name": "흑백여의도",
        "category": "media",
        "tier": "A",
        "relationCandidate": "중립",
        "relationStatus": "확인 필요",
        "mustMonitor": False,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "youtube": {"handle": "@흑백여의도"},
        },
        "enabled": True,
    },
    {
        "name": "알릴레오",
        "category": "core_speaker",
        "tier": "A",
        "relationCandidate": "정청래",
        "relationStatus": "우호 가능",
        "mustMonitor": False,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "youtube": {"handle": "@알릴레오"},
        },
        "enabled": True,
    },
    {
        "name": "열린공감TV",
        "category": "media",
        "tier": "A",
        "relationCandidate": "송영길",
        "relationStatus": "우호 가능",
        "mustMonitor": False,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "youtube": {"handle": "@열린공감TV"},
        },
        "enabled": True,
    },
    {
        "name": "민트TV",
        "category": "media",
        "tier": "A",
        "relationCandidate": "김용민",
        "relationStatus": "우호 가능",
        "mustMonitor": False,
        "crawlIntervalMinutes": 120,
        "platforms": {
            "youtube": {"handle": "@민트TV"},
        },
        "enabled": True,
    },
]


def get_targets(
    tier: str | None = None,
    platform: str | None = None,
    enabled_only: bool = True,
) -> list[dict]:
    """필터링된 타깃 목록 반환."""
    results = WATCH_TARGETS
    if enabled_only:
        results = [t for t in results if t.get("enabled", True)]
    if tier:
        results = [t for t in results if t.get("tier") == tier]
    if platform:
        results = [t for t in results if platform in t.get("platforms", {})]
    return results


def get_s_tier() -> list[dict]:
    return get_targets(tier="S")


def get_a_tier() -> list[dict]:
    return get_targets(tier="A")
