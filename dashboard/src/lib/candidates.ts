/**
 * 중앙 후보 설정 — 후보군 변경 시 이 파일만 수정하면 전체 반영됨
 */

export type CandidateId = string;

export interface CandidateConfig {
  name: CandidateId;
  displayName: string;
  color: string;
  currentCandidate: boolean;
  candidateGroup: "party_leader_main" | "former_or_potential" | "other";
  displayGroup: string;
  issueTracking: boolean;
  pollMainCandidate: boolean;
  dashboardMainCandidate: boolean;
  aliases: string[];
}

/** 전체 후보 목록 (순서 = 표시 순서) */
export const CANDIDATE_CONFIGS: CandidateConfig[] = [
  {
    name: "김민석",
    displayName: "김민석",
    color: "#005BAC",
    currentCandidate: true,
    candidateGroup: "party_leader_main",
    displayGroup: "당대표 핵심 후보",
    issueTracking: true,
    pollMainCandidate: true,
    dashboardMainCandidate: true,
    aliases: ["김민석"],
  },
  {
    name: "정청래",
    displayName: "정청래",
    color: "#7950f2",
    currentCandidate: true,
    candidateGroup: "party_leader_main",
    displayGroup: "당대표 핵심 후보",
    issueTracking: true,
    pollMainCandidate: true,
    dashboardMainCandidate: true,
    aliases: ["정청래"],
  },
  {
    name: "송영길",
    displayName: "송영길",
    color: "#e6a817",
    currentCandidate: true,
    candidateGroup: "party_leader_main",
    displayGroup: "당대표 핵심 후보",
    issueTracking: true,
    pollMainCandidate: true,
    dashboardMainCandidate: true,
    aliases: ["송영길"],
  },
  {
    name: "고민정",
    displayName: "고민정",
    color: "#0d9488",  // 틸(teal) 계열
    currentCandidate: true,
    candidateGroup: "party_leader_main",
    displayGroup: "당대표 핵심 후보",
    issueTracking: true,
    pollMainCandidate: true,
    dashboardMainCandidate: true,
    aliases: ["고민정"],
  },
  {
    name: "김용민",
    displayName: "김용민",
    color: "#9ca3af",  // 회색
    currentCandidate: false,
    candidateGroup: "former_or_potential",
    displayGroup: "기타/과거 언급",
    issueTracking: true,
    pollMainCandidate: false,
    dashboardMainCandidate: false,
    aliases: ["김용민"],
  },
  {
    name: "김두관",
    displayName: "김두관",
    color: "#0c8599",
    currentCandidate: false,
    candidateGroup: "other",
    displayGroup: "기타",
    issueTracking: false,
    pollMainCandidate: false,
    dashboardMainCandidate: false,
    aliases: ["김두관"],
  },
  {
    name: "강훈식",
    displayName: "강훈식",
    color: "#d6336c",
    currentCandidate: false,
    candidateGroup: "other",
    displayGroup: "기타",
    issueTracking: false,
    pollMainCandidate: false,
    dashboardMainCandidate: false,
    aliases: ["강훈식"],
  },
];

/** 대시보드 메인 후보 (순서 고정) */
export const MAIN_CANDIDATES = CANDIDATE_CONFIGS.filter((c) => c.dashboardMainCandidate);

/** 여론조사 메인 후보 */
export const POLL_MAIN_CANDIDATES = CANDIDATE_CONFIGS.filter((c) => c.pollMainCandidate);

/** 전체 후보 (이슈 추적 포함) */
export const ALL_CANDIDATES = CANDIDATE_CONFIGS;

/** 후보명 → 색상 맵 */
export const CANDIDATE_COLORS: Record<string, string> = Object.fromEntries(
  CANDIDATE_CONFIGS.map((c) => [c.name, c.color])
);

/** 대시보드 메인 후보명 배열 (순서 고정) */
export const MAIN_CANDIDATE_NAMES = MAIN_CANDIDATES.map((c) => c.name);

/** 여론조사 메인 후보명 배열 */
export const POLL_MAIN_CANDIDATE_NAMES = POLL_MAIN_CANDIDATES.map((c) => c.name);

/** 전체 후보명 배열 */
export const ALL_CANDIDATE_NAMES = ALL_CANDIDATES.map((c) => c.name);

/** Authors 페이지 candidateRelation 필터 목록 */
export const CANDIDATE_RELATION_FILTERS: string[] = [
  ...MAIN_CANDIDATE_NAMES.flatMap((n) => [`친${n}`, `반${n}`]),
  "관망",
  "확인 필요",
];

/** Allies 페이지용 색상 스타일 맵 */
export const CANDIDATE_STYLES: Record<string, {
  hex: string; text: string; bar: string; border: string; light: string; badge: string;
}> = {
  김민석: { hex: "#005BAC", text: "text-[#005BAC]", bar: "bg-[#005BAC]", border: "border-[#005BAC]", light: "bg-blue-50",   badge: "bg-blue-100 text-[#005BAC]" },
  정청래: { hex: "#7950f2", text: "text-[#7950f2]", bar: "bg-[#7950f2]", border: "border-[#7950f2]", light: "bg-purple-50", badge: "bg-purple-100 text-purple-700" },
  송영길: { hex: "#e6a817", text: "text-[#e6a817]", bar: "bg-[#e6a817]", border: "border-[#e6a817]", light: "bg-yellow-50", badge: "bg-yellow-100 text-yellow-700" },
  고민정: { hex: "#0d9488", text: "text-[#0d9488]", bar: "bg-[#0d9488]", border: "border-[#0d9488]", light: "bg-teal-50",   badge: "bg-teal-100 text-teal-700" },
  김용민: { hex: "#9ca3af", text: "text-gray-400",  bar: "bg-gray-400",  border: "border-gray-400",  light: "bg-gray-50",   badge: "bg-gray-100 text-gray-500" },
};
