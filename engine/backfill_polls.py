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
from .collectors.poll_collector import _fetch_article, _gpt_parse_poll, _parse_title_meta, extract_poll_sections, FULL_RE


async def backfill():
    s = get_settings()
    store = FirestoreStore(s)
    db = store.connect()
    tref = db.collection("targets").document("minju-jeondaehoe")

    polls = list(tref.collection("polls").stream())
    # 수치는 있지만 메타(조사기관·기간·매체 등)가 없는 것도 보강
    no_data = [
        p for p in polls
        if not p.to_dict().get("pollster") or not p.to_dict().get("pollPeriod")
    ]
    logger.info("메타 보강 대상 여론조사: {}건", len(no_data))

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
                    general = [{"name": m.group(1), "pct": float(m.group(2))}
                                for m in FULL_RE.finditer(text)]

            # Firestore에 저장된 스니펫도 시도
            if not general:
                stored_content = d.get("content") or d.get("snippet") or ""
                snippet = f"{title} {stored_content}"
                general = [{"name": m.group(1), "pct": float(m.group(2))}
                            for m in FULL_RE.finditer(snippet)]

            # GPT 파싱 (본문 또는 스니펫 기반) — 메타 포함
            gpt_input = text or d.get("content") or d.get("snippet") or ""
            meta = await _gpt_parse_poll(title, gpt_input)
            if not general:
                general = meta.get("general", [])
                party = meta.get("party", party)

            # 제목 직접 파싱으로 메타 보완 (확실하게)
            title_meta = _parse_title_meta(title)
            for k, v in title_meta.items():
                if v and not meta.get(k):
                    meta[k] = v

            update_data: dict = {}

            # 수치가 새로 추출됐으면 저장
            if general:
                update_data["candidatesGeneral"] = general
                update_data["candidatesParty"] = party
                update_data["hasData"] = len(general) >= 2

            # 메타 정보 저장 (기존 값 덮어쓰지 않고 없는 것만)
            existing = d
            BAD_VALUES = {"-", "", "없음", "미상", "알 수 없음", None}
            for field in ["pollster", "media", "pollPeriod", "sampleSize", "sampleGroup", "marginOfError", "surveyMethod"]:
                val = meta.get(field)
                cur = existing.get(field)
                # 좋은 새 값이 있고, 기존 값이 없거나 쓰레기 값이면 덮어쓰기
                if val and val not in BAD_VALUES and (cur in BAD_VALUES or cur == "-"):
                    update_data[field] = val

            if update_data:
                tref.collection("polls").document(doc.id).update(update_data)
                logger.info("✓ 보강 완료: {} | 기관:{} 기간:{} 매체:{}",
                    title[:35],
                    meta.get("pollster", "-"),
                    meta.get("pollPeriod", "-"),
                    meta.get("media", "-"),
                )
                updated += 1
            else:
                logger.info("- 변경 없음: {}", title[:40])

    logger.info("백필 완료: {}건 / {}건 업데이트", updated, len(no_data))


if __name__ == "__main__":
    asyncio.run(backfill())
