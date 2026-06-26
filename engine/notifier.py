"""텔레그램 알림 — 위기 경보 발생 시 등록된 채팅에 메시지 전송."""
from __future__ import annotations

import httpx
from loguru import logger

from .config import get_settings

_GRADE_EMOJI = {"red": "🔴", "orange": "🟠", "yellow": "🟡"}


def send_telegram(text: str) -> bool:
    s = get_settings()
    if not s.telegram_bot_token or not s.telegram_chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage"
        r = httpx.post(url, json={"chat_id": s.telegram_chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
        if not r.is_success:
            logger.warning("[telegram] 전송 실패: {}", r.text[:100])
            return False
        return True
    except Exception as e:
        logger.warning("[telegram] 오류: {}", e)
        return False


def notify_alert(grade: str, summary: str, cluster_title: str, target_name: str = "") -> None:
    emoji = _GRADE_EMOJI.get(grade, "⚠️")
    grade_label = {"red": "위기", "orange": "경고", "yellow": "주의"}.get(grade, grade)
    lines = [
        f"{emoji} <b>[{grade_label}] {target_name or '모니터링'} 경보</b>",
        f"📌 {cluster_title}",
        f"💬 {summary}",
    ]
    send_telegram("\n".join(lines))
