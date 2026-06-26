"""텔레그램 봇 — 보고서 PDF 전송, RED 알림, 명령어 처리.

실행:
    python -m engine.telegram_bot
"""
from __future__ import annotations

import asyncio
import io
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from loguru import logger
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from .config import get_settings
from .store import FirestoreStore

JEONDAE_DATE = datetime(2026, 8, 17, tzinfo=timezone.utc)
DASHBOARD_URL = "https://horizon-dc3c6.web.app"

# 한글 버튼 → 내부 액션 매핑
MENU_ACTIONS = {
    "📊 오늘 브리핑": "report",
    "🚨 현재 경보": "alerts",
    "📈 지지율": "polls",
    "📅 D-day": "dday",
    "ℹ️ 명령어": "help",
}

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📊 오늘 브리핑"), KeyboardButton("🚨 현재 경보")],
        [KeyboardButton("📈 지지율"), KeyboardButton("📅 D-day")],
        [KeyboardButton("ℹ️ 명령어")],
    ],
    resize_keyboard=True,
)


# ── PDF 생성 ──────────────────────────────────────────────────

def _md_to_html_body(text: str) -> str:
    """마크다운 → HTML body."""
    lines = text.split("\n")
    out: list[str] = []
    in_table = False
    table_rows: list[str] = []

    def flush_table():
        nonlocal in_table
        if not table_rows:
            return
        header = table_rows[0]
        body_rows = table_rows[2:]
        cols = [c.strip() for c in header.split("|") if c.strip()]
        out.append('<div class="tbl-wrap"><table><thead><tr>')
        for c in cols:
            out.append(f"<th>{_inline(c)}</th>")
        out.append("</tr></thead><tbody>")
        for ri, row in enumerate(body_rows):
            cells = [c.strip() for c in row.split("|")]
            cells = [c for c in cells if c]
            if not cells:
                continue
            cls = ' class="even"' if ri % 2 else ""
            out.append(f"<tr{cls}>")
            for c in cells:
                out.append(f"<td>{_inline(c)}</td>")
            out.append("</tr>")
        out.append("</tbody></table></div>")
        table_rows.clear()
        in_table = False

    def _inline(s: str) -> str:
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)

    for line in lines:
        s = line.strip()

        if s.startswith("|"):
            in_table = True
            table_rows.append(s)
            continue
        if in_table:
            flush_table()

        if re.match(r"^===.*===$", s):
            continue
        elif s == "---":
            out.append('<hr class="div"/>')
        elif s.startswith("# "):
            out.append(f"<h1>{_inline(s[2:])}</h1>")
        elif s.startswith("## "):
            out.append(f"<h2>{_inline(s[3:])}</h2>")
        elif s.startswith("### "):
            out.append(f"<h3>{_inline(s[4:])}</h3>")
        elif s.startswith("▶ ") or s.startswith("▸ "):
            out.append(f'<div class="bline"><span class="bl">{s[0]}</span><span>{_inline(s[2:])}</span></div>')
        elif s.startswith("⚑"):
            out.append(f'<div class="chk">{_inline(s)}</div>')
        elif s.startswith("- "):
            out.append(f'<div class="li"><span class="dot">•</span><span>{_inline(s[2:])}</span></div>')
        elif s.startswith("*출처"):
            out.append(f'<p class="src">{s.replace("*","")}</p>')
        elif not s:
            out.append('<div class="sp"></div>')
        else:
            out.append(f"<p>{_inline(s)}</p>")

    if in_table:
        flush_table()
    return "\n".join(out)


def markdown_to_pdf(markdown_text: str, title: str = "전당대회 동향 브리핑") -> bytes:
    """마크다운 → Playwright PDF."""
    dday = (JEONDAE_DATE - datetime.now(timezone.utc)).days
    html_body = _md_to_html_body(markdown_text)

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/>
<title>{title} D-{dday}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:'Apple SD Gothic Neo','Malgun Gothic','NanumGothic',sans-serif;
       font-size:10.5pt; color:#1a1a2e; line-height:1.65; padding:14mm 18mm; }}
h1 {{ font-size:16pt; font-weight:900; color:#1f3a5f;
     border-bottom:2.5pt solid #1f3a5f; padding-bottom:5pt; margin-bottom:5pt; margin-top:6pt; }}
h2 {{ font-size:11pt; font-weight:700; color:#1f3a5f;
     margin-top:13pt; margin-bottom:4pt;
     border-left:3pt solid #e87722; padding-left:7pt; }}
h3 {{ font-size:10.5pt; font-weight:700; color:#333; margin-top:7pt; margin-bottom:3pt; }}
p {{ font-size:10pt; margin-bottom:3pt; }}
strong {{ font-weight:700; }}
.tbl-wrap {{ margin:6pt 0; }}
table {{ width:100%; border-collapse:collapse; font-size:9.5pt; }}
th {{ background:#1f3a5f; color:#fff; padding:5pt 7pt;
     text-align:left; font-weight:700; border:0.5pt solid #aaa; }}
td {{ padding:4pt 7pt; border:0.5pt solid #ddd; vertical-align:top; }}
tr.even td {{ background:#f7f9fc; }}
.bline {{ display:flex; gap:5pt; margin:3pt 0; font-size:10pt; }}
.bl {{ color:#e87722; font-weight:700; flex-shrink:0; }}
.chk {{ color:#c0392b; font-weight:700; font-size:10pt; margin:3pt 0 3pt 10pt; }}
.li {{ display:flex; gap:5pt; margin:1pt 0 1pt 10pt; font-size:10pt; }}
.dot {{ color:#e87722; font-weight:700; flex-shrink:0; }}
.sp {{ height:4pt; }}
.src {{ font-size:8.5pt; color:#888; margin-top:12pt; padding-top:5pt; border-top:0.5pt solid #ddd; }}
hr.div {{ border:none; border-top:0.5pt solid #ddd; margin:7pt 0; }}
@page {{ margin:14mm 18mm; size:A4; }}
</style></head>
<body>{html_body}</body></html>"""

    # HTML을 임시 파일로 저장 후 Playwright로 PDF 변환
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", encoding="utf-8", delete=False) as f:
        f.write(html)
        html_path = f.name

    pdf_path = html_path.replace(".html", ".pdf")
    try:
        # subprocess로 실행 — LaunchAgent 환경에서도 안정적
        venv_python = str(Path(sys.executable))
        script = f"""
import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"])
    page = browser.new_page()
    page.goto("file://{html_path}", wait_until="domcontentloaded")
    page.pdf(path="{pdf_path}", format="A4", print_background=True)
    browser.close()
"""
        result = subprocess.run(
            [venv_python, "-c", script],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.warning("Playwright 오류: {}", result.stderr[:500])
            raise RuntimeError(result.stderr)

        return Path(pdf_path).read_bytes()

    except Exception as e:
        logger.warning("PDF 생성 실패: {} — 텍스트 fallback", e)
        # 텍스트 fallback: fpdf2
        try:
            from fpdf import FPDF
            FONT_CANDIDATES = [
                "/System/Library/Fonts/AppleSDGothicNeo.ttc",
                "/Library/Fonts/AppleSDGothicNeo.ttc",
            ]
            font_path = next((p for p in FONT_CANDIDATES if Path(p).exists()), None)
            pdf = FPDF()
            pdf.add_page()
            if font_path:
                try:
                    pdf.add_font("KR", fname=font_path, uni=True)
                    pdf.set_font("KR", size=10)
                except Exception:
                    pdf.set_font("Helvetica", size=10)
            else:
                pdf.set_font("Helvetica", size=10)
            for line in markdown_text.split("\n"):
                s = line.strip()
                if not s or re.match(r"^===.*===$", s) or s == "---":
                    pdf.ln(2)
                    continue
                clean = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
                clean = re.sub(r"^[#▶▸⚑\-•]+\s*", "", clean)
                try:
                    pdf.multi_cell(0, 5, clean[:300])
                except Exception:
                    pass
            return bytes(pdf.output())
        except Exception as fe:
            logger.error("fpdf2 fallback도 실패: {}", fe)
            return b""
    finally:
        Path(html_path).unlink(missing_ok=True)
        Path(pdf_path).unlink(missing_ok=True)


# ── Firestore 조회 ────────────────────────────────────────────

def _get_latest_report(store: FirestoreStore, target_id: str, report_type: str = "daily") -> dict | None:
    try:
        docs = (
            store.connect()
            .collection("targets").document(target_id)
            .collection("reports")
            .order_by("generatedAt", direction="DESCENDING")
            .limit(10)
            .stream()
        )
        for doc in docs:
            d = doc.to_dict()
            if d.get("type") == report_type:
                return d
    except Exception as e:
        logger.warning("보고서 조회 실패: {}", e)
    return None


def _get_red_alerts(store: FirestoreStore, target_id: str) -> list[dict]:
    alerts = []
    try:
        for doc in (
            store.connect()
            .collection("targets").document(target_id)
            .collection("clusters")
            .where("grade", "in", ["red", "orange"])
            .order_by("lastSeen", direction="DESCENDING")
            .limit(10)
            .stream()
        ):
            alerts.append(doc.to_dict())
    except Exception as e:
        logger.warning("경보 조회 실패: {}", e)
    return alerts


# ── 응답 공통 ─────────────────────────────────────────────────

async def _send_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = get_settings()
    store = FirestoreStore(s)
    store.connect()
    await update.message.reply_text("📄 보고서 생성 중...", reply_markup=MAIN_KEYBOARD)
    report = _get_latest_report(store, "minju-jeondaehoe", "daily")
    if not report:
        await update.message.reply_text("❌ 보고서가 없습니다. 오전 6시에 자동 생성됩니다.", reply_markup=MAIN_KEYBOARD)
        return
    body = report.get("bodyMarkdown", "")
    generated_at = report.get("generatedAt")
    date_str = generated_at.strftime("%Y%m%d") if generated_at else "latest"
    pdf_bytes = markdown_to_pdf(body, "전당대회 동향 브리핑")
    dday = (JEONDAE_DATE - datetime.now(timezone.utc)).days
    await ctx.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(pdf_bytes),
        filename=f"브리핑_{date_str}.pdf",
        caption=f"📊 전당대회 동향 브리핑 | D-{dday}\n🔗 {DASHBOARD_URL}",
    )


async def _send_alerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = get_settings()
    store = FirestoreStore(s)
    alerts = _get_red_alerts(store, "minju-jeondaehoe")
    if not alerts:
        await update.message.reply_text("✅ 현재 RED/ORANGE 이슈 없음", reply_markup=MAIN_KEYBOARD)
        return
    lines = [f"🚨 <b>현재 주요 경보</b>\n"]
    for d in alerts:
        grade = d.get("grade", "")
        emoji = "🔴" if grade == "red" else "🟠"
        title = d.get("title", "")[:50]
        posts = (d.get("stats") or {}).get("posts", d.get("itemCount", 0))
        lines.append(f"{emoji} {title} ({posts}건)")
    lines.append(f"\n🔗 {DASHBOARD_URL}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=MAIN_KEYBOARD)


async def _send_polls(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = get_settings()
    store = FirestoreStore(s)
    try:
        docs = list(
            store.connect()
            .collection("targets").document("minju-jeondaehoe")
            .collection("polls")
            .order_by("savedAt", direction="DESCENDING")
            .limit(3)
            .stream()
        )
    except Exception:
        await update.message.reply_text("❌ 여론조사 조회 실패", reply_markup=MAIN_KEYBOARD)
        return
    if not docs:
        await update.message.reply_text("여론조사 데이터 없음", reply_markup=MAIN_KEYBOARD)
        return
    lines = ["📊 <b>최신 여론조사</b>\n"]
    shown = 0
    for doc in docs:
        d = doc.to_dict()
        raw_cands = d.get("candidatesGeneral") or d.get("candidates") or []
        # 중복 후보 제거 (이름 기준 첫 번째만)
        seen_names: set = set()
        cands = []
        for c in raw_cands:
            if c["name"] not in seen_names:
                seen_names.add(c["name"])
                cands.append(c)
        # 수치 없는 기사는 제외
        if not cands:
            continue
        title = d.get("title", "")[:40]
        date = str(d.get("publishedAt", ""))[:10]
        lines.append(f"<b>{title}</b> ({date})")
        for c in sorted(cands, key=lambda x: -x.get("pct", 0))[:5]:
            lines.append(f"  {c['name']} {c['pct']}%")
        lines.append("")
        shown += 1
        if shown >= 3:
            break
    if shown == 0:
        await update.message.reply_text("여론조사 수치 데이터 없음", reply_markup=MAIN_KEYBOARD)
        return
    lines.append(f"🔗 {DASHBOARD_URL}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=MAIN_KEYBOARD)


async def _send_dday(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    dday = (JEONDAE_DATE - datetime.now(timezone.utc)).days
    await update.message.reply_text(
        f"🗓 8·17 전당대회까지 <b>D-{dday}</b>\n🔗 {DASHBOARD_URL}",
        parse_mode="HTML", reply_markup=MAIN_KEYBOARD,
    )


async def _send_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ <b>HOrizon0817 모니터링 봇</b>\n\n"
        "아래 버튼을 누르거나 명령어를 입력하세요:\n\n"
        "📊 <b>오늘 브리핑</b> — 최신 동향 브리핑 PDF\n"
        "🚨 <b>현재 경보</b> — RED/ORANGE 이슈 목록\n"
        "📈 <b>지지율</b> — 최신 여론조사 현황\n"
        "📅 <b>D-day</b> — 전당대회까지 남은 날\n\n"
        f"🔗 대시보드: {DASHBOARD_URL}",
        parse_mode="HTML", reply_markup=MAIN_KEYBOARD,
    )


# ── 명령어 핸들러 ─────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _send_help(update, ctx)


async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _send_report(update, ctx)


async def cmd_alerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _send_alerts(update, ctx)


async def cmd_polls(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _send_polls(update, ctx)


async def cmd_dday(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _send_dday(update, ctx)


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """한글 버튼 텍스트 → 액션 매핑."""
    text = (update.message.text or "").strip()
    action = MENU_ACTIONS.get(text)
    if action == "report":
        await _send_report(update, ctx)
    elif action == "alerts":
        await _send_alerts(update, ctx)
    elif action == "polls":
        await _send_polls(update, ctx)
    elif action == "dday":
        await _send_dday(update, ctx)
    elif action == "help":
        await _send_help(update, ctx)


# ── 외부 호출 함수 ────────────────────────────────────────────

async def push_report_pdf(target_id: str = "minju-jeondaehoe"):
    """최신 보고서를 PDF로 전송."""
    s = get_settings()
    if not s.telegram_bot_token or not s.telegram_chat_id:
        return
    store = FirestoreStore(s)
    store.connect()
    report = _get_latest_report(store, target_id, "daily")
    if not report:
        return
    body = report.get("bodyMarkdown", "")
    generated_at = report.get("generatedAt")
    date_str = generated_at.strftime("%Y%m%d") if generated_at else "latest"
    dday = (JEONDAE_DATE - datetime.now(timezone.utc)).days
    pdf_bytes = markdown_to_pdf(body, "전당대회 동향 브리핑")
    from telegram import Bot
    bot = Bot(token=s.telegram_bot_token)
    async with bot:
        await bot.send_document(
            chat_id=s.telegram_chat_id,
            document=io.BytesIO(pdf_bytes),
            filename=f"브리핑_{date_str}.pdf",
            caption=f"📊 전당대회 동향 브리핑 | D-{dday} | {date_str[:4]}.{date_str[4:6]}.{date_str[6:]}\n🔗 {DASHBOARD_URL}",
        )
    logger.info("보고서 PDF 전송 완료")


async def push_red_alert(grade: str, cluster_title: str, summary: str, posts: int):
    """RED/ORANGE 알림 즉시 전송."""
    s = get_settings()
    if not s.telegram_bot_token or not s.telegram_chat_id:
        return
    emoji = "🔴" if grade == "red" else "🟠"
    grade_label = "위기" if grade == "red" else "경고"
    text = (
        f"{emoji} <b>[{grade_label} 알림]</b>\n\n"
        f"<b>{cluster_title}</b>\n"
        f"{summary}\n\n"
        f"📌 관련 게시물 {posts}건\n"
        f"🔗 {DASHBOARD_URL}"
    )
    from telegram import Bot
    bot = Bot(token=s.telegram_bot_token)
    async with bot:
        await bot.send_message(chat_id=s.telegram_chat_id, text=text, parse_mode="HTML")
    logger.info("RED 알림 전송: {}", cluster_title)


# ── 봇 실행 ──────────────────────────────────────────────────

def run_bot():
    s = get_settings()
    if not s.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 없음")
    app = Application.builder().token(s.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("polls", cmd_polls))
    app.add_handler(CommandHandler("dday", cmd_dday))
    # 한글 버튼 텍스트 처리
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("텔레그램 봇 시작")
    import threading as _threading
    if _threading.current_thread() is _threading.main_thread():
        app.run_polling(drop_pending_updates=True)
    else:
        app.run_polling(drop_pending_updates=True, stop_signals=None)


if __name__ == "__main__":
    run_bot()
