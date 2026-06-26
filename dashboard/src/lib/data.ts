import { useEffect, useState } from "react";
import {
  collection,
  doc,
  onSnapshot,
  query,
  where,
  orderBy,
  limit as fbLimit,
  setDoc,
  updateDoc,
  deleteDoc,
  serverTimestamp,
  arrayUnion,
  type QueryConstraint,
} from "firebase/firestore";
import { db, DEFAULT_TARGET } from "../firebase";
import type {
  Ack,
  Alert,
  Cluster,
  CampResponse,
  Item,
  Report,
  TargetConfig,
} from "../types";

const T = DEFAULT_TARGET;
const base = () => collection(db, "targets", T);

function useCollection<T>(
  path: string[],
  constraints: QueryConstraint[],
  deps: unknown[] = []
): { data: T[]; loading: boolean } {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const ref = collection(db, "targets", T, ...path);
    const unsub = onSnapshot(
      query(ref, ...constraints),
      (snap) => {
        setData(snap.docs.map((d) => ({ id: d.id, ...d.data() }) as T));
        setLoading(false);
      },
      () => setLoading(false)
    );
    return unsub;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, loading };
}

// ── 조회 훅 ──────────────────────────────────────────────────
export function useClusters() {
  return useCollection<Cluster>(["clusters"], [orderBy("lastSeen", "desc"), fbLimit(1000)]);
}

export function useCluster(id: string) {
  const [data, setData] = useState<Cluster | null>(null);
  useEffect(() => {
    return onSnapshot(doc(db, "targets", T, "clusters", id), (d) =>
      setData(d.exists() ? ({ id: d.id, ...d.data() } as Cluster) : null)
    );
  }, [id]);
  return data;
}

export function useClusterItems(clusterId: string) {
  return useCollection<Item>(
    ["items"],
    [where("clusterId", "==", clusterId), fbLimit(200)],
    [clusterId]
  );
}

export function usePolls() {
  return useCollection<any>(
    ["polls"],
    [orderBy("savedAt", "desc"), fbLimit(500)],
    []
  );
}

export function useResponses(clusterId: string) {
  return useCollection<CampResponse>(
    ["clusters", clusterId, "responses"],
    [orderBy("createdAt", "desc")],
    [clusterId]
  );
}

export function useAcks(clusterId: string) {
  return useCollection<Ack & { id: string }>(
    ["clusters", clusterId, "acks"],
    [],
    [clusterId]
  );
}

export function useAlerts() {
  return useCollection<Alert>(["alerts"], [orderBy("createdAt", "desc"), fbLimit(100)]);
}

export function useReports() {
  return useCollection<Report>(["reports"], [orderBy("generatedAt", "desc"), fbLimit(60)]);
}

export function useAuthors() {
  return useCollection<{ id: string; name: string; mainPlatform: string; score: number; postCount: number; targetMentions: number; tendency?: string; totalViews?: number; authorId?: string }>(
    ["authors"],
    [orderBy("score", "desc"), fbLimit(100)]
  );
}

export function useRejected() {
  return useCollection<Item & { rejectReason: string }>(
    ["rejected"],
    [orderBy("collectedAt", "desc"), fbLimit(200)]
  );
}

export function useKeywordTrend() {
  return useCollection<{ id: string; date: string; top: { word: string; count: number }[] }>(
    ["keywordTrend"],
    [orderBy("date", "desc"), fbLimit(1)]
  );
}

// ── target 설정 (키워드·소스 상시 편집) ─────────────────────
export function useTarget() {
  const [data, setData] = useState<TargetConfig | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    return onSnapshot(doc(db, "targets", T), (d) => {
      setData(d.exists() ? (d.data() as TargetConfig) : null);
      setLoading(false);
    });
  }, []);
  return { data, loading };
}

export async function saveTarget(patch: Partial<TargetConfig>) {
  await updateDoc(doc(db, "targets", T), patch as Record<string, unknown>);
}

// ── 뮤테이션 (대응 워크플로우) ───────────────────────────────
export async function publishResponse(
  clusterId: string,
  payload: Omit<CampResponse, "id" | "createdAt">,
  uid: string
) {
  const ref = doc(base(), "clusters", clusterId, "responses", "main");
  await setDoc(
    ref,
    { ...payload, createdBy: uid, createdAt: serverTimestamp(), updatedAt: serverTimestamp() },
    { merge: true }
  );
}

export async function setClusterStatus(clusterId: string, status: Cluster["status"]) {
  await updateDoc(doc(base(), "clusters", clusterId), { status });
}

export async function deleteReport(reportId: string) {
  await deleteDoc(doc(db, "targets", T, "reports", reportId));
}

/** 현안 전략 분석 요청 (관리자 전용) */
export async function requestStrategyMemo(topic: string, clusterIds: string[]) {
  const ref = doc(collection(db, "targets", T, "strategyRequests"));
  await setDoc(ref, {
    topic,
    clusterIds,
    status: "pending",
    requestedAt: serverTimestamp(),
  });
  return ref.id;
}

/** 전략 분석 요청 취소 (pending 상태만) */
export async function cancelStrategyRequest(requestId: string) {
  await deleteDoc(doc(db, "targets", T, "strategyRequests", requestId));
}

/** 회원 확인(읽음) 기록 */
export async function recordAck(clusterId: string, uid: string, displayName: string) {
  await setDoc(
    doc(base(), "clusters", clusterId, "acks", uid),
    { uid, displayName, readAt: serverTimestamp(), status: "read" },
    { merge: true }
  );
}

/** 회원이 대응 링크 클릭 → 클릭 기록(+대응 상태) */
export async function recordLinkClick(clusterId: string, uid: string, displayName: string, url: string) {
  await setDoc(
    doc(base(), "clusters", clusterId, "acks", uid),
    {
      uid,
      displayName,
      clickedLinks: arrayUnion(url),
      status: "acted",
      readAt: serverTimestamp(),
    },
    { merge: true }
  );
}
