import { useMemo, useState } from "react";
import { useAuthors, type AuthorDoc } from "../lib/data";
import { Chip, platformLabel } from "../lib/ui";
import { CANDIDATE_RELATION_FILTERS } from "../lib/candidates";

// ── 분류 메타 ─────────────────────────────────────────────────
const POLITICAL_ALIGNMENT = ["민주성향", "보수성향", "진보성향", "중도·불명"] as const;
const LEE_RELATION        = ["친명", "반명", "비명", "친문", "확인 필요"] as const;
const CANDIDATE_RELATION  = CANDIDATE_RELATION_FILTERS;

const ALIGN_CHIP: Record<string, string> = {
  "민주성향": "bg-blue-100 text-blue-700",
  "보수성향": "bg-red-100 text-red-700",
  "진보성향": "bg-green-100 text-green-700",
  "중도·불명": "bg-gray-100 text-gray-500",
};

const LEE_CHIP: Record<string, string> = {
  "친명":     "bg-purple-100 text-purple-700",
  "반명":     "bg-orange-100 text-orange-700",
  "비명":     "bg-yellow-100 text-yellow-700",
  "친문":     "bg-indigo-100 text-indigo-700",
  "확인 필요": "bg-gray-100 text-gray-400",
};

const CAND_CHIP: Record<string, string> = {
  "친김민석":  "bg-[#005BAC]/10 text-[#005BAC]",
  "반김민석":  "bg-red-50 text-red-500",
  "친정청래":  "bg-purple-100 text-purple-700",
  "반정청래":  "bg-red-50 text-red-500",
  "친송영길":  "bg-yellow-100 text-yellow-700",
  "반송영길":  "bg-red-50 text-red-500",
  "친고민정":  "bg-teal-100 text-teal-700",
  "반고민정":  "bg-red-50 text-red-500",
  "관망":      "bg-gray-100 text-gray-500",
  "확인 필요": "bg-gray-100 text-gray-400",
};

const GRADE_CHIP: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  mid:  "bg-orange-100 text-orange-700",
  low:  "bg-gray-100 text-gray-600",
};
const GRADE_LABEL: Record<string, string> = {
  high: "고영향", mid: "중영향", low: "저영향",
};
const CONF_CHIP: Record<string, string> = {
  manual:  "bg-green-100 text-green-700",
  auto:    "bg-yellow-100 text-yellow-700",
  unknown: "bg-gray-100 text-gray-400",
};
const CONF_LABEL: Record<string, string> = {
  manual: "수동검증", auto: "자동분류", unknown: "미분류",
};

function gradeOf(score: number) {
  return score >= 20 ? "high" : score >= 8 ? "mid" : "low";
}
function fmtNum(n: number) {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}만`;
  if (n >= 1000)  return `${(n / 1000).toFixed(1)}천`;
  return String(n);
}

// ── 필터 타입 ─────────────────────────────────────────────────
type FilterState = {
  alignment: string;
  leeRelation: string;
  candidateRelation: string;
  needsReview: boolean;
  missingCollection: boolean;
};

const INIT_FILTER: FilterState = {
  alignment: "전체",
  leeRelation: "전체",
  candidateRelation: "전체",
  needsReview: false,
  missingCollection: false,
};

// ── 행 확장 ──────────────────────────────────────────────────
function AuthorRow({ a }: { a: AuthorDoc }) {
  const [expanded, setExpanded] = useState(false);
  const grade = gradeOf(a.score);
  const align = a.politicalAlignment ?? a.tendency ?? "중도·불명";
  const leeRel = a.leeRelation ?? "확인 필요";
  const candRel = a.candidateRelation ?? "확인 필요";
  const conf = a.classificationConfidence ?? "unknown";
  const frames = a.mainFrames ?? [];
  const ytUrl = a.mainPlatform === "youtube" && a.authorId?.startsWith("UC")
    ? `https://www.youtube.com/channel/${a.authorId}` : null;

  return (
    <>
      <tr
        className="hover:bg-gray-50 transition cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
      >
        <td className="px-4 py-3">
          <Chip className={GRADE_CHIP[grade]}>{GRADE_LABEL[grade]}</Chip>
        </td>
        <td className="px-4 py-3 font-medium">
          {ytUrl ? (
            <a href={ytUrl} target="_blank" rel="noreferrer"
              className="text-blue-600 hover:underline"
              onClick={(e) => e.stopPropagation()}
            >{a.name}</a>
          ) : a.name}
        </td>
        <td className="px-4 py-3">
          <Chip className={ALIGN_CHIP[align] ?? "bg-gray-100 text-gray-500"}>{align}</Chip>
        </td>
        <td className="px-4 py-3">
          <Chip className={LEE_CHIP[leeRel] ?? "bg-gray-100 text-gray-400"}>{leeRel}</Chip>
        </td>
        <td className="px-4 py-3">
          <Chip className={CAND_CHIP[candRel] ?? "bg-gray-100 text-gray-400"}>{candRel}</Chip>
        </td>
        <td className="px-4 py-3">
          <Chip className={CONF_CHIP[conf]}>{CONF_LABEL[conf]}</Chip>
        </td>
        <td className="px-4 py-3 text-gray-500 text-xs">{platformLabel(a.mainPlatform)}</td>
        <td className="px-4 py-3 text-right font-bold text-gray-800">{a.score}</td>
        <td className="px-4 py-3 text-right text-gray-500 text-xs">{fmtNum(a.totalViews ?? 0)}</td>
        <td className="px-4 py-3 text-right text-gray-500 text-xs">{a.postCount}</td>
        <td className="px-4 py-3 text-center text-xs">
          {a.needsReview && <span className="text-yellow-600 font-bold">확인필요</span>}
          {a.missingCollection && <span className="text-red-500 font-bold ml-1">미수집</span>}
        </td>
        <td className="px-3 py-3 text-gray-300 text-xs">{expanded ? "▲" : "▼"}</td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50">
          <td colSpan={12} className="px-6 py-3">
            <div className="space-y-2 text-xs">
              {/* 주요 프레임 */}
              {frames.length > 0 && (
                <div className="flex flex-wrap items-center gap-1">
                  <span className="text-gray-400 font-semibold shrink-0">주요 프레임:</span>
                  {frames.map((f) => (
                    <span key={f} className="rounded bg-slate-100 border border-slate-200 px-2 py-0.5 text-slate-600">{f}</span>
                  ))}
                </div>
              )}
              {/* 분류 주의 문구 */}
              <p className="text-gray-400 italic">
                민주성향 ≠ 친명 ≠ 친김민석. 각 축은 독립적으로 판단하며, 자동분류 confidence가 낮으면 수동 검증이 필요합니다.
              </p>
              {/* 기존 계열 */}
              {(a as any).faction && (
                <div className="text-gray-400">계열: <span className="text-gray-600">{(a as any).faction}</span></div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ── 메인 ─────────────────────────────────────────────────────
export default function Authors() {
  const { data, loading } = useAuthors();
  const [filters, setFilters] = useState<FilterState>(INIT_FILTER);
  const [sortBy, setSortBy] = useState<"score" | "views" | "posts">("score");

  const filtered = useMemo(() => {
    let list = [...data];
    if (filters.alignment !== "전체")
      list = list.filter((a) => (a.politicalAlignment ?? a.tendency ?? "중도·불명") === filters.alignment);
    if (filters.leeRelation !== "전체")
      list = list.filter((a) => (a.leeRelation ?? "확인 필요") === filters.leeRelation);
    if (filters.candidateRelation !== "전체")
      list = list.filter((a) => (a.candidateRelation ?? "확인 필요") === filters.candidateRelation);
    if (filters.needsReview)
      list = list.filter((a) => a.needsReview);
    if (filters.missingCollection)
      list = list.filter((a) => a.missingCollection);
    if (sortBy === "score") list.sort((a, b) => b.score - a.score);
    else if (sortBy === "views") list.sort((a, b) => (b.totalViews ?? 0) - (a.totalViews ?? 0));
    else list.sort((a, b) => b.postCount - a.postCount);
    return list;
  }, [data, filters, sortBy]);

  function setFilter<K extends keyof FilterState>(key: K, val: FilterState[K]) {
    setFilters((prev) => ({ ...prev, [key]: val }));
  }

  const needsReviewCount = data.filter((a) => a.needsReview).length;
  const missingCount     = data.filter((a) => a.missingCollection).length;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-gray-900">작성자 영향력</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          4축 분류 — 정치성향 / 친명관계 / 후보관계 / 주요프레임 (민주성향 ≠ 친명 ≠ 친김민석)
        </p>
      </div>

      {/* 필터 패널 */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3 shadow-sm">
        {/* 정치성향 */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-gray-400 w-20 shrink-0">정치성향</span>
          {["전체", ...POLITICAL_ALIGNMENT].map((v) => (
            <button key={v} onClick={() => setFilter("alignment", v)}
              className={`rounded-full px-3 py-1 text-xs font-semibold border transition ${
                filters.alignment === v
                  ? "bg-gray-800 text-white border-gray-800"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}>
              {v}
            </button>
          ))}
        </div>
        {/* 친명관계 */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-gray-400 w-20 shrink-0">친명관계</span>
          {["전체", ...LEE_RELATION].map((v) => (
            <button key={v} onClick={() => setFilter("leeRelation", v)}
              className={`rounded-full px-3 py-1 text-xs font-semibold border transition ${
                filters.leeRelation === v
                  ? "bg-gray-800 text-white border-gray-800"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}>
              {v}
            </button>
          ))}
        </div>
        {/* 후보관계 */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-gray-400 w-20 shrink-0">후보관계</span>
          {["전체", ...CANDIDATE_RELATION].map((v) => (
            <button key={v} onClick={() => setFilter("candidateRelation", v)}
              className={`rounded-full px-3 py-1 text-xs font-semibold border transition ${
                filters.candidateRelation === v
                  ? "bg-gray-800 text-white border-gray-800"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}>
              {v}
            </button>
          ))}
        </div>
        {/* 특수 필터 */}
        <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-gray-100">
          <span className="text-xs font-bold text-gray-400 w-20 shrink-0">특수 필터</span>
          <button onClick={() => setFilter("needsReview", !filters.needsReview)}
            className={`rounded-full px-3 py-1 text-xs font-semibold border transition ${
              filters.needsReview
                ? "bg-yellow-500 text-white border-yellow-500"
                : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
            }`}>
            확인 필요 {needsReviewCount > 0 && `(${needsReviewCount})`}
          </button>
          <button onClick={() => setFilter("missingCollection", !filters.missingCollection)}
            className={`rounded-full px-3 py-1 text-xs font-semibold border transition ${
              filters.missingCollection
                ? "bg-red-500 text-white border-red-500"
                : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
            }`}>
            미수집 의심 {missingCount > 0 && `(${missingCount})`}
          </button>
          {/* 정렬 */}
          <div className="ml-auto flex items-center gap-1 text-xs text-gray-500">
            <span>정렬:</span>
            {(["score", "views", "posts"] as const).map((s) => (
              <button key={s} onClick={() => setSortBy(s)}
                className={`px-2 py-1 rounded transition ${
                  sortBy === s ? "bg-gray-200 font-bold text-gray-800" : "hover:bg-gray-100"
                }`}>
                {s === "score" ? "점수" : s === "views" ? "조회수" : "글수"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 결과 수 */}
      <div className="text-xs text-gray-400">
        {filtered.length}명 표시 (전체 {data.length}명) — 행 클릭 시 상세 프레임 확인
      </div>

      {/* 테이블 */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="w-full min-w-[900px] text-sm">
          <thead className="bg-gray-50 text-left text-xs text-gray-500">
            <tr>
              <th className="px-4 py-3">등급</th>
              <th className="px-4 py-3">작성자</th>
              <th className="px-4 py-3">정치성향</th>
              <th className="px-4 py-3">친명관계</th>
              <th className="px-4 py-3">후보관계</th>
              <th className="px-4 py-3">분류신뢰도</th>
              <th className="px-4 py-3">플랫폼</th>
              <th className="px-4 py-3 text-right">점수</th>
              <th className="px-4 py-3 text-right">조회수</th>
              <th className="px-4 py-3 text-right">글수</th>
              <th className="px-4 py-3 text-center">상태</th>
              <th className="px-3 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading ? (
              <tr><td colSpan={12} className="px-4 py-12 text-center text-gray-400">불러오는 중…</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={12} className="px-4 py-12 text-center text-gray-400">해당 조건의 작성자가 없습니다.</td></tr>
            ) : filtered.map((a) => (
              <AuthorRow key={a.id} a={a} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-400">
        * 자동분류 confidence가 낮으면 수동 검증 필요. 수동검증값이 있으면 자동분류보다 우선 적용.
        민주성향이라고 해서 김민석 우호로 자동 분류하지 않습니다.
      </p>
    </div>
  );
}
