"""candidates.py 기준으로 Firestore targets/minju-jeondaehoe keywords/entities 동기화.

사용:
    python engine/update_target_keywords.py --dry-run   # 변경 내용만 출력
    python engine/update_target_keywords.py --apply     # 실제 Firestore 업데이트
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# 엔진 패키지 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.candidates import CANDIDATE_CONFIGS

# ── 공통 전당대회 키워드 ──────────────────────────────────────────
COMMON_KEYWORDS: list[str] = [
    "민주당 전당대회", "민주당 당대표", "전당대회", "전국당원대회", "권리당원",
    "예비경선", "컷오프", "결선투표", "최고위원", "당대표 후보", "당권",
    "친명", "비명", "반명", "당정관계", "검찰개혁", "책임론", "쇄신론",
    "통합론", "안정론", "개혁론",
    "8.17 전당대회", "817 전당대회", "지지선언", "더불어민주당",
]

# ── 프레임 키워드 ────────────────────────────────────────────────
FRAME_KEYWORDS: list[str] = [
    "책임론", "쇄신론", "통합론", "안정론", "개혁론",
    "검찰개혁", "강성당원", "친명", "비명", "반명",
    "당정일체", "당정관계", "관리형", "확장성", "실용",
    "개혁강성", "친명주류비판", "지방선거책임",
]

# ── 보조 보존 키워드 (legacy/데이터 보존용) ──────────────────────
LEGACY_KEYWORDS: list[str] = [
    "이재명", "염태영", "조승래",
    "지방선거 책임론", "6.3 지방선거 책임론", "당 쇄신",
    "친문", "친청", "당정일체", "강성 당원",
]

# ── 메인 후보 키워드 패턴 생성 ───────────────────────────────────
def _candidate_keywords(name: str) -> list[str]:
    return [
        name,
        f"{name} 당대표",
        f"{name} 전당대회",
        f"{name} 민주당 당대표",
        f"{name} 출마",
        f"{name} 캠프",
    ]


def build_new_keywords() -> tuple[list[str], dict]:
    """새 keywords 목록과 분류 메타데이터 반환."""
    main_cands = [c for c in CANDIDATE_CONFIGS if c.current_candidate and c.candidate_group == "party_leader_main"]
    legacy_cands = [c for c in CANDIDATE_CONFIGS if not c.current_candidate]

    candidate_keywords: list[str] = []
    for c in main_cands:
        candidate_keywords.extend(_candidate_keywords(c.name))

    # 구 후보(former_or_potential)는 이름 단어만 보조로 추가
    legacy_cand_keywords: list[str] = [c.name for c in legacy_cands]

    # 중복 제거, 순서 유지
    seen: set[str] = set()
    merged: list[str] = []
    for kw in (COMMON_KEYWORDS + candidate_keywords + legacy_cand_keywords + LEGACY_KEYWORDS):
        if kw not in seen:
            seen.add(kw)
            merged.append(kw)

    meta = {
        "candidateKeywords": candidate_keywords,
        "commonKeywords": COMMON_KEYWORDS,
        "frameKeywords": FRAME_KEYWORDS,
        "legacyCandidateKeywords": legacy_cand_keywords,
    }
    return merged, meta


def build_new_entities() -> list[dict]:
    """새 entities 목록 반환."""
    entities = []
    for c in CANDIDATE_CONFIGS:
        if c.current_candidate:
            role = "당대표 후보"
        elif c.candidate_group == "former_or_potential":
            role = "기타/과거 언급"
        else:
            role = "기타"
        entities.append({
            "name": c.name,
            "role": role,
            "aliases": list(c.aliases),
        })
    # 기타 주요 인물 추가
    extras = [
        {"name": "이재명", "role": "대표", "aliases": ["이재명"]},
        {"name": "염태영", "role": "최고위원 후보", "aliases": ["염태영"]},
        {"name": "조승래", "role": "최고위원 후보", "aliases": ["조승래"]},
    ]
    existing_names = {e["name"] for e in entities}
    for ex in extras:
        if ex["name"] not in existing_names:
            entities.append(ex)
    return entities


def _connect_firestore():
    cred_path = os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS",
        str(Path(__file__).parent / "serviceAccountKey.json"),
    )
    import firebase_admin
    from firebase_admin import credentials, firestore as fs
    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    return fs.client()


def run(dry_run: bool, target_id: str = "minju-jeondaehoe") -> None:
    new_keywords, meta = build_new_keywords()
    new_entities = build_new_entities()

    main_cands = [c for c in CANDIDATE_CONFIGS if c.current_candidate]
    former_cands = [c for c in CANDIDATE_CONFIGS if not c.current_candidate]

    print("\n" + "═" * 60)
    print("  HORIZON0817 — Firestore keyword 동기화")
    print("═" * 60)
    print(f"\n[candidates.py 기준]")
    print(f"  currentCandidate 후보: {[c.name for c in main_cands]}")
    print(f"  former_or_potential  : {[c.name for c in former_cands]}")

    # Firestore 현재 상태 조회
    db = _connect_firestore()
    ref = db.collection("targets").document(target_id)
    doc = ref.get().to_dict() or {}
    old_keywords: list[str] = doc.get("keywords", [])
    old_entities: list[dict] = doc.get("entities", [])

    added = [k for k in new_keywords if k not in old_keywords]
    removed = [k for k in old_keywords if k not in new_keywords]

    print(f"\n[키워드 변경 요약]")
    print(f"  현재 Firestore keywords : {len(old_keywords)}개")
    print(f"  새 keywords             : {len(new_keywords)}개")
    print(f"  추가될 키워드 ({len(added)}개)  : {added if added else '없음'}")
    print(f"  제거될 키워드 ({len(removed)}개) : {removed if removed else '없음'}")

    print(f"\n[엔티티 변경 요약]")
    old_entity_names = [e.get("name") for e in old_entities]
    new_entity_names = [e.get("name") for e in new_entities]
    print(f"  현재 entities: {old_entity_names}")
    print(f"  새 entities  : {new_entity_names}")

    print(f"\n[후보별 메인 키워드]")
    for kw in meta["candidateKeywords"]:
        print(f"  • {kw}")

    if dry_run:
        print("\n[DRY-RUN] Firestore 업데이트 없음. --apply로 실제 반영.")
        print("═" * 60 + "\n")
        return

    # ── 실제 업데이트 (merge) ────────────────────────────────────
    now = datetime.now(timezone.utc)
    update_data = {
        # 백업
        "previousKeywords": old_keywords,
        "previousEntities": old_entities,
        "lastSyncedAt": now,
        # 새 데이터
        "keywords": new_keywords,
        "entities": new_entities,
        "candidateKeywords": meta["candidateKeywords"],
        "commonKeywords": meta["commonKeywords"],
        "frameKeywords": meta["frameKeywords"],
        "updatedAt": now,
        "updatedBy": "update_target_keywords.py",
    }
    ref.update(update_data)

    print(f"\n[APPLY 완료] Firestore targets/{target_id} 업데이트됨")
    print(f"  keywords: {len(old_keywords)}개 → {len(new_keywords)}개")
    print(f"  entities: {len(old_entities)}개 → {len(new_entities)}개")
    print(f"  백업 필드: previousKeywords, previousEntities, lastSyncedAt")
    print("═" * 60 + "\n")


def _cli() -> None:
    parser = argparse.ArgumentParser(description="candidates.py → Firestore keyword 동기화")
    parser.add_argument("--dry-run", action="store_true", help="변경 내용만 출력, Firestore 미반영")
    parser.add_argument("--apply", action="store_true", help="Firestore 실제 업데이트")
    parser.add_argument("--target", default="minju-jeondaehoe", help="Firestore target ID")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.print_help()
        sys.exit(1)

    run(dry_run=not args.apply, target_id=args.target)


if __name__ == "__main__":
    _cli()
