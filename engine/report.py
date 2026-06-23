"""보고서 생성 — 일일/주간 통합 보고서를 만들어 reports 컬렉션에 저장."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from loguru import logger

from .config import get_settings
from .store import FirestoreStore

_GRADE_EMOJI = {"red": "🔴", "orange": "🟠", "yellow": "🟡", "none": "⚪"}


def generate_report(target_id: str, store: FirestoreStore | None = None, report_type: str = "daily") -> dict:
    s = get_settings()
    store = store or FirestoreStore(s)
    now = datetime.now(timezone.utc)
    span = timedelta(days=7) if report_type == "weekly" else timedelta(days=1)
    since = now - span

    clusters = store.load_active_clusters(target_id, s.window_days)
    clusters = [c for c in clusters if c.last_seen >= since]
    clusters.sort(key=lambda c: (c.grade != "red", c.grade != "orange", -len(c.item_ids)))

    mentions = store.count_items_since(target_id, since)
    alerts = store.alerts_since(target_id, since)

    lines = [
        f"# {'주간' if report_type == 'weekly' else '일일'} 동향 보고서",
        f"- 기간: {since.strftime('%Y-%m-%d %H:%M')} ~ {now.strftime('%Y-%m-%d %H:%M')} (UTC)",
        f"- 총 언급: **{mentions}** · 고유 이슈: **{len(clusters)}** · 위기 알림: **{len(alerts)}**",
        "",
        "## 주요 이슈",
    ]
    if not clusters:
        lines.append("_표시할 이슈가 없습니다._")
    for c in clusters[:15]:
        emoji = _GRADE_EMOJI.get(c.grade, "⚪")
        pats = (" / " + ", ".join(c.patterns)) if c.patterns else ""
        lines.append(f"- {emoji} **{c.title}** ({len(c.item_ids)}건{pats})")
        if c.summary and c.summary != c.title:
            lines.append(f"  - {c.summary}")

    report_id = f"{report_type}-{now.strftime('%Y%m%d-%H%M')}"
    doc = {
        "type": report_type,
        "period": now.strftime("%Y-%m-%d %H:%M"),
        "generatedAt": now,
        "totals": {"mentions": mentions, "uniqueIssues": len(clusters), "alerts": len(alerts)},
        "bodyMarkdown": "\n".join(lines),
        "excelUrl": None,
    }
    store.save_report(target_id, report_id, doc)
    logger.info("[report] {} 저장: 이슈 {} / 알림 {}", report_id, len(clusters), len(alerts))
    return doc
