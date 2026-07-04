"""기존 클러스터에 latestArticleTitle / latestArticleUrl / latestPublishedAt / firstPublishedAt 백필.

각 클러스터의 items 서브컬렉션을 조회해 가장 최신 publishedAt 기사의 title/url을 저장.

사용:
    python engine/backfill_latest_article.py --dry-run
    python engine/backfill_latest_article.py --apply [--limit 200]
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

NEWS_PLATFORMS = {
    "naver_news", "daum_news", "google_news", "rss", "nate_news",
}


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


def _to_dt(val) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    return None


def run(dry_run: bool, target_id: str = "minju-jeondaehoe", limit: int = 300) -> None:
    db = _connect_firestore()
    tref = db.collection("targets").document(target_id)

    clusters = list(tref.collection("clusters").limit(limit).stream())
    print(f"\n클러스터 {len(clusters)}개 조회\n")

    updates: list[tuple] = []   # (doc_ref, patch_dict)
    skipped = 0

    for snap in clusters:
        d = snap.to_dict() or {}

        # 이미 latestArticleTitle이 채워져 있으면 스킵
        if d.get("latestArticleTitle"):
            skipped += 1
            continue

        cluster_id = snap.id
        platforms: list[str] = (d.get("stats") or {}).get("platforms", [])

        # items 서브컬렉션에서 publishedAt 있는 것 조회
        items = list(
            tref.collection("items")
            .where("clusterId", "==", cluster_id)
            .limit(50)
            .stream()
        )

        if not items:
            # items가 없으면 cluster 자체의 title/lastSeen 사용
            patch: dict = {}
            existing_lpa = _to_dt(d.get("latestPublishedAt"))
            if not existing_lpa:
                patch["publishedAtMissing"] = True
                patch["needsTimeReview"] = True
            if d.get("title") and not d.get("latestArticleTitle"):
                patch["latestArticleTitle"] = d["title"]
                patch["representativeTitle"] = d["title"]
            if patch:
                updates.append((tref.collection("clusters").document(cluster_id), patch))
            continue

        # publishedAt 기준으로 정렬
        timed = []
        no_time = []
        for it in items:
            itd = it.to_dict() or {}
            pa = _to_dt(itd.get("publishedAt"))
            if pa:
                timed.append((pa, itd))
            else:
                no_time.append(itd)

        patch = {}

        if timed:
            timed.sort(key=lambda x: x[0], reverse=True)
            latest_pa, latest_item = timed[0]
            oldest_pa = timed[-1][0]

            patch["latestPublishedAt"] = latest_pa
            patch["firstPublishedAt"] = oldest_pa
            if latest_item.get("title"):
                patch["latestArticleTitle"] = latest_item["title"]
                patch["representativeTitle"] = latest_item["title"]
            if latest_item.get("url"):
                patch["latestArticleUrl"] = latest_item["url"]
                patch["representativeUrl"] = latest_item["url"]
        else:
            patch["publishedAtMissing"] = True
            patch["needsTimeReview"] = True
            # title 없으면 cluster title 사용
            if not d.get("latestArticleTitle"):
                patch["latestArticleTitle"] = d.get("title", "")
                patch["representativeTitle"] = d.get("title", "")

        patch["clusterUpdatedAt"] = datetime.now(timezone.utc)
        updates.append((tref.collection("clusters").document(cluster_id), patch))

    print(f"  백필 대상: {len(updates)}개 / 이미 완료: {skipped}개\n")
    for ref, patch in updates[:10]:
        lat = patch.get("latestArticleTitle", "")[:40]
        lpa = patch.get("latestPublishedAt", "없음")
        print(f"  [{ref.id[:8]}] title='{lat}' | publishedAt={lpa}")
    if len(updates) > 10:
        print(f"  ... 외 {len(updates) - 10}개")

    if dry_run:
        print("\n[DRY-RUN] Firestore 미반영. --apply로 실제 반영.")
        return

    # 배치 업데이트 (merge)
    now = datetime.now(timezone.utc)
    batch_size = 400
    updated = 0
    for i in range(0, len(updates), batch_size):
        batch = db.batch()
        for ref, patch in updates[i:i + batch_size]:
            patch["backfilledAt"] = now
            batch.update(ref, patch)
        batch.commit()
        updated += len(updates[i:i + batch_size])
        print(f"  배치 커밋: {updated}/{len(updates)}")

    print(f"\n[APPLY 완료] {updated}개 클러스터 latestArticleTitle/latestPublishedAt 백필됨")


def _cli():
    parser = argparse.ArgumentParser(description="cluster latestArticleTitle 백필")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--target", default="minju-jeondaehoe")
    parser.add_argument("--limit", type=int, default=300)
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        parser.print_help()
        sys.exit(1)
    run(dry_run=not args.apply, target_id=args.target, limit=args.limit)


if __name__ == "__main__":
    _cli()
