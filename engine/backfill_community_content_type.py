"""기존 sourceType=community 클러스터에 communityContentType 백필.

분류 기준:
- commentId / parentPostId 있으면 → comment
- detectedLinks/sharedUrl/articleUrl 이 뉴스 도메인이면 → shared_news
- title/text가 있고 구조가 게시글이면 → original_post
- 판단 불가 → unknown

사용:
    python engine/backfill_community_content_type.py --dry-run
    python engine/backfill_community_content_type.py --apply [--limit 500]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

_NEWS_DOMAINS = {
    "news.naver.com", "news.daum.net", "news.nate.com",
    "news.google.com", "yna.co.kr", "yonhapnews.co.kr",
    "chosun.com", "joongang.co.kr", "donga.com", "hani.co.kr",
    "khan.co.kr", "ohmynews.com", "pressian.com", "newsis.com",
    "newspim.com", "edaily.co.kr", "sbs.co.kr", "kbs.co.kr",
    "mbc.co.kr", "jtbc.co.kr", "ytn.co.kr", "tvchosun.com",
    "munhwa.com", "seoul.co.kr", "imaeil.com", "busan.com",
    "cbs.co.kr", "etoday.co.kr", "mt.co.kr", "sedaily.com",
    "hankyung.com", "mk.co.kr", "etnews.com", "zdnet.co.kr",
}

_NEWS_URL_RE = re.compile(
    r"https?://(?:www\.)?"
    r"(?:news\.naver\.com|news\.daum\.net|v\.daum\.net|news\.nate\.com|"
    r"n\.news\.naver\.com|[a-z0-9.-]+\.co\.kr/news|[a-z0-9.-]+\.com/news|"
    r"yna\.co\.kr|yonhapnews\.co\.kr)",
    re.IGNORECASE,
)


def _is_news_url(url: str) -> bool:
    if not url:
        return False
    try:
        host = urlparse(url).netloc.lstrip("www.")
        return host in _NEWS_DOMAINS or bool(_NEWS_URL_RE.search(url))
    except Exception:
        return False


def _classify(d: dict) -> tuple[str, float, str]:
    """(communityContentType, confidence, reason) 반환."""

    # 1) 댓글 판단
    if d.get("commentId") or d.get("parentPostId") or d.get("parentUrl"):
        return "comment", 0.95, "commentId/parentPostId/parentUrl 필드 존재"

    # 2) 뉴스공유 판단
    news_signals = 0
    news_reason_parts = []
    for field in ("sharedUrl", "articleUrl"):
        val = d.get(field, "")
        if _is_news_url(val):
            news_signals += 2
            news_reason_parts.append(f"{field}={val[:50]}")
    for link in (d.get("detectedLinks") or []):
        if _is_news_url(link):
            news_signals += 1
            news_reason_parts.append(f"detectedLink={link[:50]}")
    # 제목이 기사 형태 (언론사명 포함)
    title = d.get("title", "") or ""
    text = d.get("text", d.get("content", "")) or ""
    if news_signals >= 2:
        return "shared_news", min(0.9, 0.6 + news_signals * 0.1), "뉴스 URL 감지: " + " / ".join(news_reason_parts[:2])

    # 3) original_post 판단
    has_title = bool(title and len(title.strip()) >= 5)
    has_text = bool(text and len(text.strip()) >= 20)
    has_post_id = bool(d.get("postId"))
    if has_title and has_text:
        conf = 0.80 + (0.05 if has_post_id else 0)
        return "original_post", conf, "제목+본문 있는 게시글"
    if has_title or has_post_id:
        return "original_post", 0.60, "제목 또는 postId로 원글 추정"

    # 4) unknown
    return "unknown", 0.30, "분류 근거 부족 — title/text/링크 부족"


def _connect_firestore():
    cred_path = os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS",
        str(Path(__file__).parent / "serviceAccountKey.json"),
    )
    import firebase_admin
    from firebase_admin import credentials, firestore as fs
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(cred_path))
    return fs.client()


def run(dry_run: bool, target_id: str = "minju-jeondaehoe", limit: int = 500) -> None:
    db = _connect_firestore()
    tref = db.collection("targets").document(target_id)

    # sourceType=community인 클러스터만 조회
    # Firestore where + limit
    clusters = list(
        tref.collection("clusters")
        .where("sourceType", "==", "community")
        .limit(limit)
        .stream()
    )
    print(f"\n커뮤니티 클러스터: {len(clusters)}건\n")

    counts: dict[str, int] = {"original_post": 0, "comment": 0, "shared_news": 0, "unknown": 0}
    samples: dict[str, list[str]] = {"original_post": [], "comment": [], "shared_news": [], "unknown": []}
    updates: list[tuple] = []

    for snap in clusters:
        d = snap.to_dict() or {}
        ctype, conf, reason = _classify(d)
        counts[ctype] += 1
        if len(samples[ctype]) < 5:
            samples[ctype].append(f"[{snap.id[:8]}] {d.get('title','')[:50]} → {ctype} ({reason[:40]})")

        # 이미 설정된 건 건너뜀 (단, unknown이면 재분류 허용)
        existing = d.get("communityContentType", "")
        if existing and existing != "unknown":
            continue

        patch = {
            "communityContentType": ctype,
            "classificationConfidence": conf,
            "classificationReason": reason,
            "reclassifiedAt": datetime.now(timezone.utc),
            "reclassifiedBy": "backfill_community_content_type",
        }
        if existing:
            patch["previousCommunityContentType"] = existing
        updates.append((tref.collection("clusters").document(snap.id), patch))

    print("── 분류 결과 ─────────────────────────────────────────────")
    for k, v in counts.items():
        print(f"  {k:20s}: {v}건")
    print(f"\n  업데이트 대상: {len(updates)}건\n")

    for ctype in ("original_post", "comment", "shared_news", "unknown"):
        if samples[ctype]:
            print(f"── {ctype} 샘플 ───────────────────────────")
            for s in samples[ctype]:
                print(f"  {s}")
    print()

    if dry_run:
        print("[DRY-RUN] Firestore 미반영. --apply로 실제 반영.")
        return

    batch_size = 400
    updated = 0
    for i in range(0, len(updates), batch_size):
        batch = db.batch()
        for ref, patch in updates[i : i + batch_size]:
            batch.update(ref, patch)
        batch.commit()
        updated += len(updates[i : i + batch_size])
        print(f"  배치 커밋: {updated}/{len(updates)}")

    print(f"\n[APPLY 완료] {updated}건 communityContentType 백필")
    unknown_cnt = counts["unknown"]
    if unknown_cnt:
        print(f"  unknown {unknown_cnt}건 — 확인필요 탭에서 수동 재분류 가능")


def _cli():
    parser = argparse.ArgumentParser(description="커뮤니티 클러스터 communityContentType 백필")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--target", default="minju-jeondaehoe")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        parser.print_help()
        sys.exit(1)
    run(dry_run=not args.apply, target_id=args.target, limit=args.limit)


if __name__ == "__main__":
    _cli()
