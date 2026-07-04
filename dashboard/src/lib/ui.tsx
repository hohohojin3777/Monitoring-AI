import type { Timestamp } from "firebase/firestore";
import type { Grade, IssueImportance, RiskLevel, ResponseLevel } from "../types";

export const GRADE_META: Record<Grade, { label: string; dot: string; chip: string }> = {
  red:    { label: "위기", dot: "bg-grade-red",    chip: "bg-danger-red/10 text-danger-red border border-danger-red/30" },
  orange: { label: "주의", dot: "bg-grade-orange", chip: "bg-warning-orange/10 text-warning-orange border border-warning-orange/30" },
  yellow: { label: "관찰", dot: "bg-grade-yellow", chip: "bg-yellow-50 text-yellow-700 border border-yellow-300" },
  none:   { label: "일반", dot: "bg-gray-300",     chip: "bg-gray-100 text-gray-500 border border-gray-200" },
};

// 3-레이어 배지 메타
export const IMPORTANCE_META: Record<IssueImportance, { chip: string }> = {
  핵심: { chip: "bg-blue-600 text-white border border-blue-700" },
  중요: { chip: "bg-blue-100 text-blue-700 border border-blue-300" },
  관찰: { chip: "bg-gray-100 text-gray-600 border border-gray-300" },
  일반: { chip: "bg-gray-50 text-gray-400 border border-gray-200" },
};

export const RISK_META: Record<RiskLevel, { chip: string }> = {
  긴급: { chip: "bg-red-600 text-white border border-red-700" },
  위기: { chip: "bg-danger-red/10 text-danger-red border border-danger-red/30" },
  주의: { chip: "bg-warning-orange/10 text-warning-orange border border-warning-orange/30" },
  없음: { chip: "" },
};

export const RESPONSE_META: Record<ResponseLevel, { chip: string }> = {
  즉시대응: { chip: "bg-red-100 text-red-700 border border-red-400" },
  대응필요: { chip: "bg-orange-100 text-orange-700 border border-orange-300" },
  보고필요: { chip: "bg-purple-100 text-purple-700 border border-purple-300" },
  모니터링: { chip: "bg-slate-100 text-slate-600 border border-slate-300" },
  무대응:   { chip: "" },
};

/** 카드 왼쪽 단일 배지 — 우선순위: 리스크 > 대응 > 중요도 */
export function resolveIssueBadge(
  riskLevel?: RiskLevel,
  responseLevel?: ResponseLevel,
  issueImportance?: IssueImportance,
  grade?: Grade,
): { label: string; chip: string; dot: string } {
  // 리스크 우선
  if (riskLevel === "긴급") return { label: "긴급", chip: RISK_META["긴급"].chip, dot: "bg-grade-red" };
  if (riskLevel === "위기") return { label: "위기", chip: RISK_META["위기"].chip, dot: "bg-grade-red" };
  if (riskLevel === "주의") return { label: "주의", chip: RISK_META["주의"].chip, dot: "bg-grade-orange" };
  // 대응 레벨
  if (responseLevel === "즉시대응") return { label: "즉시대응", chip: RESPONSE_META["즉시대응"].chip, dot: "bg-grade-red" };
  if (responseLevel === "대응필요") return { label: "대응필요", chip: RESPONSE_META["대응필요"].chip, dot: "bg-grade-orange" };
  if (responseLevel === "보고필요") return { label: "보고", chip: RESPONSE_META["보고필요"].chip, dot: "bg-purple-400" };
  // 중요도
  if (issueImportance === "핵심") return { label: "핵심", chip: IMPORTANCE_META["핵심"].chip, dot: "bg-blue-500" };
  if (issueImportance === "중요") return { label: "중요", chip: IMPORTANCE_META["중요"].chip, dot: "bg-blue-300" };
  if (issueImportance === "관찰") return { label: "관찰", chip: IMPORTANCE_META["관찰"].chip, dot: "bg-grade-yellow" };
  // 폴백: 기존 grade
  if (grade) return GRADE_META[grade] ? { ...GRADE_META[grade], dot: GRADE_META[grade].dot } : GRADE_META.none;
  return { label: "일반", chip: GRADE_META.none.chip, dot: "bg-gray-300" };
}

const PLATFORM_LABEL: Record<string, string> = {
  naver_news: "네이버뉴스",
  naver_blog: "블로그",
  naver_cafe: "카페",
  google_news: "구글뉴스",
  rss: "RSS",
  youtube: "유튜브",
  x: "X",
  dcinside: "디시",
  fmkorea: "펨코",
  clien: "클리앙",
};

export function platformLabel(p: string): string {
  return PLATFORM_LABEL[p] ?? p;
}

export function GradeDot({ grade }: { grade: Grade }) {
  const m = GRADE_META[grade] ?? GRADE_META.none;
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${m.dot}`} />;
}

export function Chip({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${className}`}>
      {children}
    </span>
  );
}

export function fmtDate(ts?: Timestamp | null): string {
  if (!ts) return "";
  try {
    const d = ts.toDate();
    return d.toLocaleString("ko-KR", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export function relTime(ts?: Timestamp | null): string {
  if (!ts) return "";
  try {
    const diff = Date.now() - ts.toDate().getTime();
    const h = Math.floor(diff / 3.6e6);
    if (h < 1) return "방금";
    if (h < 24) return `${h}시간 전`;
    return `${Math.floor(h / 24)}일 전`;
  } catch {
    return "";
  }
}
