"""기존 Firestore clusters/items의 sourceType을 URL/도메인 기준으로 재분류.

사용:
    python engine/backfill_sourcetype.py --dry-run
    python engine/backfill_sourcetype.py --apply
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── 도메인 → sourceType 매핑 ────────────────────────────────────
NEWS_DOMAINS = {
    "news.naver.com", "n.news.naver.com",
    "news.daum.net", "v.daum.net",
    "news.nate.com",
    # 주요 언론사
    "hani.co.kr", "khan.co.kr", "ohmynews.com", "pressian.com",
    "newsis.com", "yonhapnews.co.kr", "yna.co.kr",
    "chosun.com", "joongang.co.kr", "joins.com", "donga.com",
    "kmib.co.kr", "kookmin.com", "hankyung.com", "mk.co.kr",
    "sedaily.com", "etoday.co.kr", "etnews.com",
    "mediatoday.co.kr", "newstapa.org", "sisain.co.kr",
    "huffingtonpost.kr", "huffpost.com",
    "sbs.co.kr", "kbs.co.kr", "mbc.co.kr", "jtbc.co.kr", "ytn.co.kr",
    "news1.kr", "뉴스1.kr",
}

VIDEO_DOMAINS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "youtu.be",
}

SNS_DOMAINS = {
    "facebook.com", "www.facebook.com", "m.facebook.com",
    "x.com", "twitter.com", "www.x.com",
    "instagram.com", "www.instagram.com",
    "threads.net", "www.threads.net",
}

COMMUNITY_DOMAINS = {
    "dcinside.com", "www.dcinside.com", "m.dcinside.com",
    "fmkorea.com", "www.fmkorea.com",
    "clien.net", "www.clien.net",
    "ruliweb.com", "bbs.ruliweb.com",
    "ppomppu.co.kr", "www.ppomppu.co.kr",
    "bobaedream.co.kr", "www.bobaedream.co.kr",
    "mlbpark.com", "www.mlbpark.com",
    "pann.nate.com",
    "todayhumor.co.kr", "www.todayhumor.co.kr",
    "ddanzi.com", "www.ddanzi.com",
    "theqoo.net", "m.theqoo.net",
    "cafe.naver.com",
}

OFFICIAL_DOMAINS = {
    "theminjoo.kr", "www.theminjoo.kr",
    "nec.go.kr", "www.nec.go.kr",
    "assembly.go.kr", "www.assembly.go.kr",
    "president.go.kr",
}

PLATFORM_SOURCE_MAP = {
    "naver_news": "news", "daum_news": "news", "google_news": "news",
    "rss": "news", "nate_news": "news",
    "youtube": "video",
    "facebook": "sns", "x": "sns", "twitter": "sns",
    "instagram": "sns", "threads": "sns",
    "dcinside": "community", "fmkorea": "community", "clien": "community",
    "ruliweb": "community", "ppomppu": "community", "bobaedream": "community",
    "naver_cafe": "community", "mlbpark": "community", "natepan": "community",
    "todayhumor": "community", "ddanzi": "community", "theqoo": "community",
    "official": "official", "theminjoo": "official",
}


def classify_url(url: str) -> str | None:
    if not url:
        return None
    try:
        domain = urlparse(url).netloc.lower().lstrip("www.")
        if any(d in domain for d in VIDEO_DOMAINS):
            return "video"
        if any(d == domain or domain.endswith("." + d) for d in NEWS_DOMAINS):
            return "news"
        if any(d == domain or domain.endswith("." + d) for d in SNS_DOMAINS):
            return "sns"
        if any(d == domain or domain.endswith("." + d) for d in COMMUNITY_DOMAINS):
            return "community"
        if any(d == domain or domain.endswith("." + d) for d in OFFICIAL_DOMAINS):
            return "official"
    except Exception:
        pass
    return None


def classify_platforms(platforms: list[str]) -> str:
    votes: dict[str, int] = {}
    for p in platforms:
        st = PLATFORM_SOURCE_MAP.get(p)
        if st:
            votes[st] = votes.get(st, 0) + 1
    if not votes:
        return "unknown"
    # 영상이 하나라도 있으면 video, SNS/뉴스와 섞였으면 혼재 → unknown
    if "video" in votes and len(votes) > 1:
        return "unknown"
    return max(votes, key=lambda k: votes[k])


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

    clusters = list(tref.collection("clusters").limit(limit).stream())
    print(f"\n클러스터 {len(clusters)}개 조회")

    stats = {"skipped": 0, "already_set": 0, "reclassified": 0, "unknown": 0}
    changes: list[dict] = []

    for snap in clusters:
        d = snap.to_dict() or {}
        current_st = d.get("sourceType")
        platforms: list[str] = (d.get("stats") or {}).get("platforms", [])

        # sourceType 이미 설정된 경우 (manual reclassify된 것은 건드리지 않음)
        if current_st and d.get("reclassifiedBy") == "manual":
            stats["skipped"] += 1
            continue

        # platform 기반 추론
        new_st = classify_platforms(platforms)

        # URL 기반으로 한 번 더 검증 (source 필드가 있으면)
        source_url = d.get("source") or d.get("url") or ""
        url_st = classify_url(source_url)
        if url_st and new_st == "unknown":
            new_st = url_st

        if current_st == new_st:
            stats["already_set"] += 1
            continue

        if new_st == "unknown":
            stats["unknown"] += 1
        else:
            stats["reclassified"] += 1

        changes.append({
            "id": snap.id,
            "title": d.get("title", "")[:40],
            "prev": current_st or "없음",
            "new": new_st,
            "platforms": platforms,
        })

    print(f"\n[변경 대상 {len(changes)}개 / 이미 설정 {stats['already_set']}개 / 스킵 {stats['skipped']}개]")
    print(f"  → news 등 재분류: {stats['reclassified']}개, unknown: {stats['unknown']}개\n")

    for ch in changes[:20]:
        print(f"  [{ch['prev']} → {ch['new']}] {ch['title']} ({ch['platforms']})")
    if len(changes) > 20:
        print(f"  ... 외 {len(changes) - 20}개")

    if dry_run:
        print("\n[DRY-RUN] Firestore 미반영. --apply로 실제 반영.")
        return

    now = datetime.now(timezone.utc)
    batch_size = 400
    updated = 0
    for i in range(0, len(changes), batch_size):
        batch = db.batch()
        for ch in changes[i:i + batch_size]:
            ref = tref.collection("clusters").document(ch["id"])
            batch.update(ref, {
                "sourceType": ch["new"],
                "previousSourceType": ch["prev"] if ch["prev"] != "없음" else None,
                "reclassifiedAt": now,
                "reclassifiedBy": "backfill_sourcetype.py",
            })
        batch.commit()
        updated += len(changes[i:i + batch_size])
        print(f"  배치 커밋: {updated}/{len(changes)}")

    print(f"\n[APPLY 완료] {updated}개 클러스터 sourceType 업데이트됨")


def _cli():
    parser = argparse.ArgumentParser(description="Firestore cluster sourceType 백필")
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
