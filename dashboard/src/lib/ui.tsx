import type { Timestamp } from "firebase/firestore";
import type { Grade } from "../types";

export const GRADE_META: Record<Grade, { label: string; dot: string; chip: string }> = {
  red:    { label: "위기", dot: "bg-grade-red",    chip: "bg-danger-red/10 text-danger-red border border-danger-red/30" },
  orange: { label: "주의", dot: "bg-grade-orange", chip: "bg-warning-orange/10 text-warning-orange border border-warning-orange/30" },
  yellow: { label: "관찰", dot: "bg-grade-yellow", chip: "bg-yellow-50 text-yellow-700 border border-yellow-300" },
  none:   { label: "일반", dot: "bg-gray-300",     chip: "bg-gray-100 text-gray-500 border border-gray-200" },
};

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
