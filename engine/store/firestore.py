"""Firestore 저장소 — 엔진(Admin SDK)이 클라우드 공유 DB 에 읽고 쓴다.

경로는 모두 targets/{targetId} 하위. 데이터 모델은 docs/DATA_MODEL.md 참고.
firebase_admin 클라이언트는 동기이므로, 호출부(async)에서 필요 시 asyncio.to_thread 로 감싼다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from loguru import logger

from ..analysis.cluster import Cluster
from ..collectors.base import RawItem
from ..config import Settings, get_settings
from ..models import Target

_BATCH_LIMIT = 450  # Firestore 배치 최대 500, 여유


class FirestoreStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._db = None

    def connect(self):
        if self._db is not None:
            return self._db
        import os

        import firebase_admin
        from firebase_admin import credentials, firestore

        emulator = os.environ.get("FIRESTORE_EMULATOR_HOST")
        if not firebase_admin._apps:
            if emulator:
                # 에뮬레이터: 실제 인증서 불필요 (로컬 개발·테스트)
                firebase_admin.initialize_app(
                    options={"projectId": self._s.firebase_project_id or "demo-monitoring"}
                )
                logger.info("[firestore] 에뮬레이터 연결: {}", emulator)
            else:
                if self._s.firebase_credentials_json:
                    import json
                    cert_dict = json.loads(self._s.firebase_credentials_json)
                    cred = credentials.Certificate(cert_dict)
                    logger.info("[firestore] JSON 환경변수로 연결")
                else:
                    from pathlib import Path
                    cred_path = self._s.firebase_credentials_path
                    if not os.path.isabs(cred_path):
                        cred_path = str(Path(__file__).parent.parent / cred_path)
                    cred = credentials.Certificate(cred_path)
                    logger.info("[firestore] 파일 경로로 연결: {}", cred_path)
                firebase_admin.initialize_app(cred)
                logger.info("[firestore] 연결 완료")
        self._db = firestore.client()
        return self._db

    # ── target ────────────────────────────────────────────────
    def get_target(self, target_id: str) -> Target | None:
        snap = self.connect().collection("targets").document(target_id).get()
        if not snap.exists:
            return None
        return Target.from_doc(target_id, snap.to_dict())

    def list_target_ids(self) -> list[str]:
        return [d.id for d in self.connect().collection("targets").stream()]

    def _target_ref(self, target_id: str):
        return self.connect().collection("targets").document(target_id)

    # ── 최근 item id (중복 방지) ───────────────────────────────
    def recent_item_ids(self, target_id: str, days: int = 30) -> set[str]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        q = (
            self._target_ref(target_id)
            .collection("items")
            .where("collectedAt", ">=", since)
        )
        return {d.id for d in q.stream()}

    # ── 활성 클러스터 로드 ─────────────────────────────────────
    def load_active_clusters(self, target_id: str, window_days: int = 30) -> list[Cluster]:
        since = datetime.now(timezone.utc) - timedelta(days=window_days)
        q = (
            self._target_ref(target_id)
            .collection("clusters")
            .where("lastSeen", ">=", since)
        )
        clusters: list[Cluster] = []
        for d in q.stream():
            data = d.to_dict()
            clusters.append(
                Cluster(
                    cluster_id=d.id,
                    title=data.get("title", ""),
                    rep_text=data.get("repText", data.get("title", "")),
                    first_seen=_as_dt(data.get("firstSeen")),
                    last_seen=_as_dt(data.get("lastSeen")),
                    latest_published_at=_as_dt(data["latestPublishedAt"]) if data.get("latestPublishedAt") else None,
                    first_published_at=_as_dt(data["firstPublishedAt"]) if data.get("firstPublishedAt") else None,
                    status=data.get("status", "active"),
                    item_ids=data.get("itemIds", []) or [],
                    grade=data.get("grade", "none"),
                    patterns=data.get("patterns", []) or [],
                    filter_tag=data.get("filterTag", "전체"),
                    reactivated=data.get("reactivated", False),
                    summary=data.get("summary", ""),
                    stats=data.get("stats", {}) or {},
                    latest_article_title=data.get("latestArticleTitle", ""),
                    latest_article_url=data.get("latestArticleUrl", ""),
                    representative_title=data.get("representativeTitle", ""),
                    representative_url=data.get("representativeUrl", ""),
                    published_at_missing=data.get("publishedAtMissing", False),
                    needs_time_review=data.get("needsTimeReview", False),
                    cluster_confidence=data.get("clusterConfidence", 1.0),
                )
            )
        return clusters

    def load_cluster_items(self, target_id: str, cluster_id: str) -> list[RawItem]:
        """채점용 — 해당 클러스터에 이미 저장된 item 들을 RawItem 으로 복원."""
        q = (
            self._target_ref(target_id)
            .collection("items")
            .where("clusterId", "==", cluster_id)
        )
        return [_doc_to_item(d.to_dict()) for d in q.stream()]

    # ── 쓰기 ───────────────────────────────────────────────────
    def save_items(self, target_id: str, items: list[RawItem]) -> None:
        self._batched(
            self._target_ref(target_id).collection("items"),
            [(it.item_id, _item_doc(it)) for it in items],
            merge=True,
        )

    def save_rejected(self, target_id: str, items: list[RawItem]) -> None:
        self._batched(
            self._target_ref(target_id).collection("rejected"),
            [(it.item_id, _item_doc(it)) for it in items],
            merge=True,
        )

    def save_clusters(self, target_id: str, clusters: list[Cluster]) -> None:
        self._batched(
            self._target_ref(target_id).collection("clusters"),
            [(c.cluster_id, _cluster_doc(c)) for c in clusters],
            merge=True,
        )

    def add_alert(self, target_id: str, alert: dict) -> None:
        self._target_ref(target_id).collection("alerts").add(alert)

    def save_polls(self, target_id: str, polls: list[dict]) -> None:
        """poll master 저장 — dedupeKey 기반 upsert.

        - 같은 dedupeKey = 같은 여론조사 → sourceArticles 배열 누적
        - manualVerified=true 문서는 핵심 수치 덮어쓰기 금지
        - candidatesGeneral: 더 많은 쪽으로 보완
        - 수치 충돌 시 needsReview=true
        """
        import hashlib
        from google.cloud.firestore_v1 import ArrayUnion

        coll = self._target_ref(target_id).collection("polls")
        db = self.connect()
        batch = db.batch()
        n = 0
        now = datetime.now(timezone.utc)

        for p in polls:
            dedup_key = p.get("dedupeKey")
            if not dedup_key:
                key = p.get("url") or str(p.get("pollster", "")) + str(p.get("pollStartDate", ""))
                dedup_key = hashlib.sha256(key.encode()).hexdigest()[:16]

            doc_ref = coll.document(dedup_key)
            existing_snap = doc_ref.get()

            # 수동 검증 보호
            if existing_snap.exists and existing_snap.to_dict().get("manualVerified"):
                arts = p.get("sourceArticles") or ([p["sourceArticle"]] if p.get("sourceArticle") else [])
                if arts:
                    doc_ref.set({"sourceArticles": ArrayUnion(arts), "updatedAt": now}, merge=True)
                continue

            # 저장 문서 구성 (sourceArticle 단일 키 제거)
            doc = {k: v for k, v in p.items()
                   if v is not None and k not in ("sourceArticle",)}
            doc["savedAt"]   = doc.get("savedAt") or now
            doc["updatedAt"] = now

            # candidatesGeneral/Party 없으면 기존 보존
            if not doc.get("candidatesGeneral"):
                doc.pop("candidatesGeneral", None)
            if not doc.get("candidatesParty"):
                doc.pop("candidatesParty", None)

            # 충돌 검사 — 기존 수치와 새 수치가 다르면 needsReview
            if existing_snap.exists:
                ex = existing_snap.to_dict()
                ex_cands = {c["name"]: c["pct"] for c in ex.get("candidatesGeneral", [])}
                new_cands = {c["name"]: c["pct"] for c in doc.get("candidatesGeneral", [])}
                if ex_cands and new_cands and ex_cands != new_cands:
                    diff = any(abs(ex_cands.get(n, 0) - new_cands.get(n, 0)) > 0.5
                               for n in set(ex_cands) | set(new_cands))
                    if diff:
                        doc["needsReview"] = True
                        logger.debug("[store] poll 수치 충돌 needsReview: {}", dedup_key)

            # sourceArticles ArrayUnion
            arts = p.get("sourceArticles") or ([p["sourceArticle"]] if p.get("sourceArticle") else [])
            if arts:
                doc["sourceArticles"] = ArrayUnion(arts)

            batch.set(doc_ref, doc, merge=True)
            n += 1
            if n % _BATCH_LIMIT == 0:
                batch.commit()
                batch = db.batch()

        if n % _BATCH_LIMIT:
            batch.commit()
        logger.info("[store] polls {}건 저장 (poll master 병합)", n)

    def save_report(self, target_id: str, report_id: str, report: dict) -> None:
        self._target_ref(target_id).collection("reports").document(report_id).set(report)

    def save_authors(self, target_id: str, authors: list[dict]) -> None:
        """작성자 영향력 누적 — postCount/targetMentions/score 를 Increment 로 합산."""
        if not authors:
            return
        from firebase_admin import firestore as fa

        db = self.connect()
        coll = self._target_ref(target_id).collection("authors")
        batch = db.batch()
        n = 0
        for a in authors:
            aid = a.get("authorId")
            if not aid:
                continue
            batch.set(
                coll.document(aid),
                {
                    "authorId": aid,
                    "name": a["name"],
                    "mainPlatform": a["mainPlatform"],
                    "postCount": fa.Increment(a["postCount"]),
                    "targetMentions": fa.Increment(a["targetMentions"]),
                    "score": fa.Increment(a["score"]),
                    "updatedAt": a.get("updatedAt"),
                },
                merge=True,
            )
            n += 1
            if n >= _BATCH_LIMIT:
                batch.commit()
                batch = db.batch()
                n = 0
        if n:
            batch.commit()

    def save_keyword_trend(self, target_id: str, date_key: str, doc: dict) -> None:
        self._target_ref(target_id).collection("keywordTrend").document(date_key).set(doc)

    # ── 보고서용 기간 조회 ─────────────────────────────────────
    def count_items_since(self, target_id: str, since: datetime) -> int:
        q = (
            self._target_ref(target_id)
            .collection("items")
            .where("collectedAt", ">=", since)
        )
        return sum(1 for _ in q.stream())

    def alerts_since(self, target_id: str, since: datetime) -> list[dict]:
        q = (
            self._target_ref(target_id)
            .collection("alerts")
            .where("createdAt", ">=", since)
        )
        return [d.to_dict() for d in q.stream()]

    # ── monitored_accounts ────────────────────────────────────
    def _account_ref(self, account_id: str):
        return self.connect().collection("monitored_accounts").document(account_id)

    def upsert_monitored_account(self, account_id: str, doc: dict) -> None:
        self._account_ref(account_id).set(doc, merge=True)

    def update_account_status(
        self,
        account_id: str,
        *,
        status: str,
        last_collected_at: datetime | None = None,
        last_success_at: datetime | None = None,
        last_error: str | None = None,
        failure_reason: str | None = None,
        next_retry_at: datetime | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        patch: dict = {"status": status, "updatedAt": now}
        if last_collected_at is not None:
            patch["lastCollectedAt"] = last_collected_at
        if last_success_at is not None:
            patch["lastSuccessAt"] = last_success_at
        if last_error is not None:
            patch["lastError"] = last_error
            patch["lastErrorAt"] = now
        if failure_reason is not None:
            patch["failureReason"] = failure_reason
        if next_retry_at is not None:
            patch["nextRetryAt"] = next_retry_at
        self._account_ref(account_id).set(patch, merge=True)

    def get_monitored_accounts(self, enabled_only: bool = True) -> list[dict]:
        q = self.connect().collection("monitored_accounts")
        if enabled_only:
            q = q.where("enabled", "==", True)
        return [{"id": d.id, **d.to_dict()} for d in q.stream()]

    def save_sns_alert(self, account_id: str, name: str, reason: str, extra: dict | None = None) -> None:
        doc = {
            "type": "sns_missing",
            "accountId": account_id,
            "accountName": name,
            "reason": reason,
            "createdAt": datetime.now(timezone.utc),
            **(extra or {}),
        }
        self.connect().collection("monitored_accounts").document(account_id).collection("alerts").add(doc)

    # ── cleanup ────────────────────────────────────────────────
    def cleanup_old(self, target_id: str, window_days: int = 30) -> int:
        since = datetime.now(timezone.utc) - timedelta(days=window_days)
        removed = 0
        for coll in ("items", "rejected"):
            q = self._target_ref(target_id).collection(coll).where("collectedAt", "<", since)
            db = self.connect()
            batch = db.batch()
            n = 0
            for d in q.stream():
                batch.delete(d.reference)
                n += 1
                removed += 1
                if n >= _BATCH_LIMIT:
                    batch.commit()
                    batch = db.batch()
                    n = 0
            if n:
                batch.commit()
        # 오래된 클러스터는 archived 로
        cq = self._target_ref(target_id).collection("clusters").where("lastSeen", "<", since)
        for d in cq.stream():
            d.reference.set({"status": "archived"}, merge=True)
        logger.info("[firestore] cleanup: {}건 삭제", removed)
        return removed

    def _batched(self, coll_ref, pairs: list[tuple[str, dict]], merge: bool = False) -> None:
        if not pairs:
            return
        db = self.connect()
        batch = db.batch()
        n = 0
        for doc_id, data in pairs:
            batch.set(coll_ref.document(doc_id), data, merge=merge)
            n += 1
            if n >= _BATCH_LIMIT:
                batch.commit()
                batch = db.batch()
                n = 0
        if n:
            batch.commit()


def _as_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _item_doc(it: RawItem) -> dict:
    return {
        "platform": it.platform,
        "sourceType": it.source_type,
        "url": it.url,
        "canonicalUrl": it.canonical,
        "title": it.title,
        "content": it.content[:2000],
        "author": it.author,
        "authorId": it.author_id,
        "publishedAt": it.published_at,
        "collectedAt": it.collected_at,
        "metrics": it.metrics,
        "keyword": it.keyword,
        "matchedEntities": it.matched_entities,
        "sentiment": it.sentiment or "neutral",
        "clusterId": it.cluster_id,
        "rejected": it.rejected,
        "rejectReason": it.reject_reason,
        "imageUrl": it.image_url or "",
    }


def _doc_to_item(data: dict) -> RawItem:
    return RawItem(
        platform=data.get("platform", ""),
        source_type=data.get("sourceType", ""),
        url=data.get("url", ""),
        title=data.get("title", ""),
        content=data.get("content", ""),
        author=data.get("author", ""),
        author_id=data.get("authorId", ""),
        published_at=data.get("publishedAt"),
        collected_at=data.get("collectedAt"),
        metrics=data.get("metrics", {}) or {},
        keyword=data.get("keyword", ""),
        matched_entities=data.get("matchedEntities", []) or [],
        sentiment=data.get("sentiment", "neutral"),
        cluster_id=data.get("clusterId"),
    )


def _cluster_doc(c: Cluster) -> dict:
    now = datetime.now(timezone.utc)
    doc: dict = {
        "title": c.title,
        "repText": c.rep_text[:1000],
        "summary": c.summary,
        "firstSeen": c.first_seen,
        "lastSeen": c.last_seen,
        "latestPublishedAt": c.latest_published_at,
        "clusterUpdatedAt": now,
        "updatedAt": now,
        "status": c.status,
        "grade": c.grade,
        "patterns": c.patterns,
        "filterTag": c.filter_tag,
        "reactivated": c.reactivated,
        "itemIds": c.item_ids[:500],
        "itemCount": len(c.item_ids),
        "stats": c.stats,
    }
    # 최신 기사 필드 — 값이 있을 때만 저장 (기존 값 덮어쓰지 않음)
    if c.latest_article_title:
        doc["latestArticleTitle"] = c.latest_article_title
    if c.latest_article_url:
        doc["latestArticleUrl"] = c.latest_article_url
    if c.representative_title:
        doc["representativeTitle"] = c.representative_title
    if c.representative_url:
        doc["representativeUrl"] = c.representative_url
    if c.first_published_at:
        doc["firstPublishedAt"] = c.first_published_at
    if c.published_at_missing:
        doc["publishedAtMissing"] = True
        doc["needsTimeReview"] = True
    if c.cluster_confidence < 1.0:
        doc["clusterConfidence"] = c.cluster_confidence
    return doc
