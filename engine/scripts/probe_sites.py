"""사이트 점검 — 각 사이트 검색이 실제로 글을 뽑는지 확인(로그인 사이트 포함).

login.py 로 로그인해 둔 영구 프로필을 그대로 쓰므로, 네이버 카페·X 등도 점검 가능.
사이트별 수집 건수와 샘플 제목을 출력한다. 0건이면 URL/패턴/로그인 튜닝이 필요.

실행:
    python -m engine.scripts.probe_sites --keyword 이재명
    python -m engine.scripts.probe_sites --keyword 전당대회 --sites all
    python -m engine.scripts.probe_sites --sites dcinside clien x
"""
from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from ..collectors.scraper import BrowserCollector
from ..collectors.sites import all_site_keys, get_sites


async def run(keyword: str, keys: list[str], headed: bool) -> None:
    sites = get_sites(keys)
    if not sites:
        logger.error("해당 사이트 없음: {}", keys)
        return
    print(f"\n점검 키워드: '{keyword}' / 사이트 {len(sites)}개\n" + "-" * 50)
    for site in sites:
        collector = BrowserCollector([site], headless=not headed)
        try:
            items = await collector.collect([keyword])
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {site.name:14s} 오류: {e}")
            continue
        mark = "✓" if items else "✗"
        login = " (로그인필요)" if site.requires_login else ""
        sample = items[0].title[:30] if items else "—"
        print(f"  {mark} {site.name:14s} {len(items):3d}건{login}  예: {sample}")
    print("-" * 50)
    print("0건인 사이트는 sites.py 의 search_url/link_pattern 또는 로그인 세션을 점검하세요.")


def main() -> None:
    p = argparse.ArgumentParser(description="사이트 수집 점검")
    p.add_argument("--keyword", default="이재명")
    p.add_argument("--sites", nargs="*", default=all_site_keys(), help="사이트 key 들 또는 all")
    p.add_argument("--headed", action="store_true", help="브라우저 화면 표시")
    args = p.parse_args()
    asyncio.run(run(args.keyword, args.sites, args.headed))


if __name__ == "__main__":
    main()
