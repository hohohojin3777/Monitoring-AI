"""특정 클러스터를 item 단위로 분리해 새 클러스터로 만드는 스크립트.

사용:
    python engine/split_cluster.py --cluster-id e9be4650 --dry-run
    python engine/split_cluster.py --cluster-id e9be4650 --apply

동작:
  1. 원본 클러스터의 items를 publishedAt 기준으로 그룹화
  2. 첫 번째 item → 원본 클러스터 유지 (seed item)
  3. 나머지 items → 각각 새 클러스터 ID 생성 (or 가장 가까운 기사끼리 묶기)
  4. 원본 클러스터 itemIds / stats 갱신
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


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


def _new_cluster_id(item_id: str) -> str:
    return hashlib.sha256(item_id.encode()).hexdigest()[:8]


def run(cluster_id: str, dry_run: bool, target_id: str = "minju-jeondaehoe") -> None:
    db = _connect_firestore()
    tref = db.collection("targets").document(target_id)
    cref = tref.collection("clusters").document(cluster_id)

    snap = cref.get()
    if not snap.exists:
        print(f"[ERROR] 클러스터 {cluster_id} 없음")
        return

    cdata = snap.to_dict() or {}
    print(f"\n원본 클러스터: [{cluster_id}]")
    print(f"  title: {cdata.get('title', '')}")
    print(f"  items: {len(cdata.get('itemIds', []))}\n")

    # items 조회
    items = list(
        tref.collection("items")
        .where("clusterId", "==", cluster_id)
        .stream()
    )
    print(f"items 서브컬렉션 조회: {len(items)}건\n")

    if not items:
        print("[WARN] items 없음. itemIds 기반으로 split 불가.")
        return

    # publishedAt 기준 정렬
    timed = []
    for it in items:
        d = it.to_dict() or {}
        pa = _to_dt(d.get("publishedAt"))
        timed.append((pa or datetime.min.replace(tzinfo=timezone.utc), d, it.id))

    timed.sort(key=lambda x: x[0])

    print("items 목록 (시간순):")
    for i, (pa, d, iid) in enumerate(timed):
        print(f"  [{i}] {iid[:8]} | {pa.isoformat() if pa != datetime.min.replace(tzinfo=timezone.utc) else 'no-time'}")
        print(f"       제목: {d.get('title','')[:70]}")
    print()

    if len(timed) < 2:
        print("[INFO] item이 1개뿐 — split 불필요")
        return

    # 분리 전략: 첫 번째 item → 원본 유지, 나머지 → 새 클러스터
    seed_pa, seed_d, seed_iid = timed[0]
    rest = timed[1:]

    print(f"[SPLIT 계획]")
    print(f"  원본 유지: {seed_iid[:8]} — {seed_d.get('title','')[:60]}")
    print(f"  분리 대상: {len(rest)}건")
    for pa, d, iid in rest:
        new_cid = _new_cluster_id(iid)
        print(f"    → 새 클러스터 {new_cid}: {d.get('title','')[:60]}")
    print()

    if dry_run:
        print("[DRY-RUN] 미반영. --apply로 실제 반영.")
        return

    now = datetime.now(timezone.utc)
    batch = db.batch()

    # 원본 클러스터: seed item만 남기도록 itemIds 수정
    seed_item_ids = [seed_iid]
    seed_stats = dict(cdata.get("stats") or {})
    seed_stats["itemCount"] = 1

    batch.update(cref, {
        "itemIds": seed_item_ids,
        "title": seed_d.get("title", cdata.get("title", "")),
        "latestArticleTitle": seed_d.get("title", ""),
        "latestArticleUrl": seed_d.get("url", ""),
        "representativeTitle": seed_d.get("title", ""),
        "representativeUrl": seed_d.get("url", ""),
        "latestPublishedAt": seed_pa if seed_pa != datetime.min.replace(tzinfo=timezone.utc) else None,
        "firstPublishedAt": seed_pa if seed_pa != datetime.min.replace(tzinfo=timezone.utc) else None,
        "stats": seed_stats,
        "splitFrom": None,
        "splitAt": now,
        "clusterUpdatedAt": now,
    })

    # 분리된 item들 → 새 클러스터 생성
    for pa, d, iid in rest:
        new_cid = _new_cluster_id(iid)
        new_cref = tref.collection("clusters").document(new_cid)

        new_doc = {
            "clusterId": new_cid,
            "title": d.get("title", ""),
            "repText": d.get("text", d.get("content", d.get("title", ""))),
            "status": "active",
            "itemIds": [iid],
            "grade": "none",
            "filterTag": "전체",
            "reactivated": False,
            "summary": "",
            "latestArticleTitle": d.get("title", ""),
            "latestArticleUrl": d.get("url", ""),
            "representativeTitle": d.get("title", ""),
            "representativeUrl": d.get("url", ""),
            "latestPublishedAt": pa if pa != datetime.min.replace(tzinfo=timezone.utc) else None,
            "firstPublishedAt": pa if pa != datetime.min.replace(tzinfo=timezone.utc) else None,
            "firstSeen": now,
            "lastSeen": now,
            "splitFrom": cluster_id,
            "splitAt": now,
            "clusterUpdatedAt": now,
            "stats": {
                "itemCount": 1,
                "platforms": [d.get("platform", "")] if d.get("platform") else [],
            },
        }
        batch.set(new_cref, new_doc)

        # item의 clusterId 갱신
        iref = tref.collection("items").document(iid)
        batch.update(iref, {"clusterId": new_cid, "clusterUpdatedAt": now})

    batch.commit()
    print(f"[APPLY 완료] 원본 {cluster_id} 유지 (1건) + 새 클러스터 {len(rest)}개 생성")


def _cli():
    parser = argparse.ArgumentParser(description="클러스터 item 분리")
    parser.add_argument("--cluster-id", required=True)
    parser.add_argument("--target", default="minju-jeondaehoe")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        parser.print_help()
        sys.exit(1)
    run(args.cluster_id, dry_run=not args.apply, target_id=args.target)


if __name__ == "__main__":
    _cli()
