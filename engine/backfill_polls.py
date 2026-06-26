"""수치 없는 여론조사 기사에 GPT-4o-mini로 후보 지지율 백필.

실행:
    python -m engine.backfill_polls
"""
from __future__ import annotations

import asyncio
import os

import httpx
from loguru import logger

from .config import get_settings
from .store import FirestoreStore
from .collectors.poll_collector import _fetch_article, _gpt_parse_candidates, extract_poll_sections, FULL_RE


async def backfill():
    s = get_settings()
    store = FirestoreStore(s)
    db = store.connect()
    tref = db.collection("targets").document("minju-jeondaehoe")

    polls = list(tref.collection("polls").stream())
    no_data = [p for p in polls if not p.to_dict().get("candidatesGeneral") and not p.to_dict().get("candidates")]
    logger.info("수치 없는 여론조사: {}건 백필 시작", len(no_data))

    updated = 0
    async with httpx.AsyncClient() as client:
        for doc in no_data:
            d = doc.to_dict()
            url = d.get("url") or d.get("detailUrl") or ""
            title = d.get("title") or d.get("name") or ""

            if not url:
                logger.warning("URL 없음: {}", title[:40])
                continue

            text, _ = await _fetch_article(client, url)

            general, party = [], []
            if text:
                general, party = extract_poll_sections(text)
                if not general:
                    snippet = f"{title} {d.get('content','')}"
                    general = [{"name": m.group(1), "pct": float(m.group(2))}
                                for m in FULL_RE.finditer(snippet)]

            if not general and (text or title):
                general, party = await _gpt_parse_candidates(title, text or title)

            if general:
                tref.collection("polls").document(doc.id).update({
                    "candidatesGeneral": general,
                    "candidatesParty": party,
                })
                logger.info("✓ 백필 완료: {} → {}건 수치", title[:40], len(general))
                updated += 1
            else:
                logger.warning("✗ 수치 추출 실패: {}", title[:40])

    logger.info("백필 완료: {}건 / {}건 업데이트", updated, len(no_data))


if __name__ == "__main__":
    asyncio.run(backfill())
