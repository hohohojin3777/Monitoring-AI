"""엔진 진입점 — APScheduler 로 모든 target 을 주기 수집·분석하고 자정에 정리·보고.

실행:
    python -m engine.main
환경변수(.env) 가 채워져 있어야 한다. Ctrl+C 로 종료.
"""
from __future__ import annotations

import asyncio
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import sys
from loguru import logger

logger.remove()
logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}", colorize=False)

from .config import get_settings
from .pipeline import run_target
from .report import generate_report
from .report_generator import generate_report as generate_briefing
from .store import FirestoreStore
from .strategy_analyzer import process_pending_requests, auto_generate as auto_generate_strategy


async def _morning_briefing(store: FirestoreStore) -> None:
    for tid in store.list_target_ids():
        try:
            logger.info("[main] 오전 6시 브리핑 생성 시작: {}", tid)
            await generate_briefing(tid)
            logger.info("[main] 오전 6시 브리핑 완료: {}", tid)
        except Exception as e:
            logger.error("[main] 브리핑 실패: {}", e)


async def _process_strategy_memos(store: FirestoreStore) -> None:
    for tid in store.list_target_ids():
        try:
            n = await process_pending_requests(tid)
            if n:
                logger.info("[main] 전략 메모 요청 처리: {}건 ({})", n, tid)
            await auto_generate_strategy(tid)
        except Exception as e:  # noqa: BLE001
            logger.error("[main] '{}' 전략 메모 처리 실패: {}", tid, e)


async def _collect_all_targets(store: FirestoreStore) -> None:
    for tid in store.list_target_ids():
        try:
            await run_target(tid, store)
        except Exception as e:  # noqa: BLE001
            logger.error("[main] target '{}' 실행 실패: {}", tid, e)
    await _process_strategy_memos(store)


def _daily_maintenance(store: FirestoreStore) -> None:
    s = get_settings()
    for tid in store.list_target_ids():
        try:
            store.cleanup_old(tid, s.window_days)
            generate_report(tid, store, "daily")
        except Exception as e:  # noqa: BLE001
            logger.error("[main] '{}' 정리/보고 실패: {}", tid, e)


def _weekly_report(store: FirestoreStore) -> None:
    for tid in store.list_target_ids():
        try:
            generate_report(tid, store, "weekly")
        except Exception as e:  # noqa: BLE001
            logger.error("[main] '{}' 주간보고 실패: {}", tid, e)


async def main() -> None:
    s = get_settings()
    if not s.has_firebase_credentials():
        raise RuntimeError(
            "Firebase 인증 정보 없음 — FIREBASE_CREDENTIALS_JSON(Railway) 또는 "
            f"FIREBASE_CREDENTIALS_PATH 파일({s.firebase_credentials_path})을 설정하세요."
        )
    store = FirestoreStore(s)
    store.connect()

    scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        _collect_all_targets,
        CronTrigger(minute="0,30", timezone="Asia/Seoul"),
        args=[store],
        id="collect",
    )
    scheduler.add_job(_daily_maintenance, CronTrigger(hour=0, minute=10), args=[store], id="daily")
    scheduler.add_job(_morning_briefing, CronTrigger(hour=6, minute=0, timezone="Asia/Seoul"), args=[store], id="briefing_am")
    scheduler.add_job(_daily_maintenance, CronTrigger(hour=18, minute=0), args=[store], id="report_pm")
    scheduler.add_job(
        _weekly_report, CronTrigger(day_of_week="sat", hour=18, minute=0, timezone="Asia/Seoul"), args=[store], id="weekly"
    )
    scheduler.start()
    logger.info("[main] 스케줄러 시작: {}분 주기 수집", s.collect_interval_minutes)

    # 텔레그램 봇 백그라운드 스레드로 실행
    import threading
    from .telegram_bot import run_bot as _run_bot
    bot_thread = threading.Thread(target=_run_bot, daemon=True, name="telebot")
    bot_thread.start()
    logger.info("[main] 텔레그램 봇 스레드 시작")

    # 시작 즉시 1회 수집
    await _collect_all_targets(store)

    stop = asyncio.Event()
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:  # Windows
                pass
    except RuntimeError:
        pass
    await stop.wait()
    scheduler.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("[main] 종료")
