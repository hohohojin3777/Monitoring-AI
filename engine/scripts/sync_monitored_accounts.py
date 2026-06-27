"""watch_targets.py → Firestore monitored_accounts 컬렉션 동기화.

실행:
  python -m engine.scripts.sync_monitored_accounts
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from engine.store.firestore import FirestoreStore
from engine.watch_targets import WATCH_TARGETS


def _account_id(name: str, platform: str) -> str:
    raw = f"{name}:{platform}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _tier_interval(tier: str) -> int:
    return {"S": 60, "A": 120, "B": 180, "C": 240}.get(tier, 120)


def build_docs() -> list[tuple[str, dict]]:
    docs = []
    now = datetime.now(timezone.utc)

    for target in WATCH_TARGETS:
        name = target.get("name", "")
        category = target.get("category", "unknown")
        tier = target.get("tier", "B")
        relation_candidate = target.get("relationCandidate")
        relation_status = target.get("relationStatus", "확인 필요")
        must_monitor = target.get("mustMonitor", False)
        crawl_interval = target.get("crawlIntervalMinutes", _tier_interval(tier))
        enabled = target.get("enabled", True)
        platforms = target.get("platforms", {})

        for platform, pconf in platforms.items():
            acc_id = _account_id(name, platform)
            doc = {
                "name": name,
                "category": category,
                "tier": tier,
                "platform": platform,
                "url": pconf.get("url") or pconf.get("channelId", ""),
                "handle": pconf.get("accountId") or pconf.get("handle", ""),
                "channelId": pconf.get("channelId", ""),
                "candidateRelation": relation_candidate or "중립",
                "relationStatus": relation_status,
                "enabled": enabled,
                "mustMonitor": must_monitor,
                "crawlIntervalMinutes": crawl_interval,
                # 상태 필드 — 이미 있으면 유지 (merge=True)
                "lastCollectedAt": None,
                "lastSuccessAt": None,
                "lastErrorAt": None,
                "lastError": None,
                "failureReason": None,
                "nextRetryAt": None,
                "status": "active",
                "createdAt": now,
                "updatedAt": now,
            }
            docs.append((acc_id, doc))

    return docs


def main() -> None:
    store = FirestoreStore()
    docs = build_docs()
    print(f"동기화할 계정: {len(docs)}개")

    for acc_id, doc in docs:
        # status/lastCollectedAt 등 기존 값은 merge=True로 보존
        existing = store._account_ref(acc_id).get()
        if existing.exists:
            # 기존 상태 필드는 덮어쓰지 않음
            keep = {
                k: existing.to_dict().get(k)
                for k in ("lastCollectedAt", "lastSuccessAt", "lastErrorAt",
                          "lastError", "failureReason", "nextRetryAt", "status")
                if existing.to_dict().get(k) is not None
            }
            doc.update(keep)

        store.upsert_monitored_account(acc_id, doc)
        print(f"  ✓ {doc['name']} / {doc['platform']} ({doc['tier']}급)")

    print(f"\n완료: monitored_accounts {len(docs)}건 동기화")


if __name__ == "__main__":
    main()
