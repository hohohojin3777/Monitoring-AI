import { useMemo, useState } from "react";
import { useAuthors } from "../lib/data";
import { Chip, platformLabel } from "../lib/ui";

const TENDENCY_CHIP: Record<string, string> = {
  "민주성향":       "bg-blue-100 text-blue-700",
  "보수성향":       "bg-red-100 text-red-700",
  "중립/불명":      "bg-gray-100 text-gray-500",
  "미디어/커뮤니티": "bg-slate-100 text-slate-600",
};

const GRADE_CHIP: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  mid:  "bg-orange-100 text-orange-700",
  low:  "bg-gray-100 text-gray-600",
};

const GRADE_LABEL: Record<string, string> = {
  high: "고영향",
  mid:  "중영향",
  low:  "저영향",
};

function gradeOf(score: number) {
  return score >= 20 ? "high" : score >= 8 ? "mid" : "low";
}

function fmtNum(n: number) {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}만`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}천`;
  return String(n);
}

const TENDENCY_FILTERS = ["전체", "민주성향", "보수성향", "미디어/커뮤니티", "중립/불명"] as const;

export default function Authors() {
  const { data, loading } = useAuthors();
  const [filter, setFilter] = useState<string>("전체");
  const [sortBy, setSortBy] = useState<"score" | "views" | "posts">("score");

  const filtered = useMemo(() => {
    let list = [...data];
    if (filter !== "전체") list = list.filter((a) => (a.tendency ?? "중립/불명") === filter);
    if (sortBy === "score") list.sort((a, b) => b.score - a.score);
    else if (sortBy === "views") list.sort((a, b) => (b.totalViews ?? 0) - (a.totalViews ?? 0));
    else list.sort((a, b) => b.postCount - a.postCount);
    return list;
  }, [data, filter, sortBy]);

  const counts = useMemo(() => {
    const m: Record<string, number> = { 전체: data.length };
    for (const a of data) {
      const t = a.tendency ?? "중립/불명";
      m[t] = (m[t] ?? 0) + 1;
    }
    return m;
  }, [data]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-gray-900">작성자 영향력</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          민주당 성향 유튜버·공개 매체 작성자의 누적 영향력 분석
        </p>
      </div>

      {/* 성향 필터 */}
      <div className="flex flex-wrap gap-2">
        {TENDENCY_FILTERS.map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={`rounded-full px-3 py-1 text-sm font-semibold border transition ${
              filter === t
                ? "bg-navy text-white border-navy"
                : "bg-white text-gray-600 border-gray-200 hover:border-gray-300"
            }`}
          >
            {t}
            <span className="ml-1 text-xs opacity-60">{counts[t] ?? 0}</span>
          </button>
        ))}

        {/* 정렬 */}
        <div className="ml-auto flex items-center gap-1 text-xs text-gray-500">
          <span>정렬:</span>
          {(["score", "views", "posts"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSortBy(s)}
              className={`px-2 py-1 rounded transition ${
                sortBy === s ? "bg-gray-200 font-bold text-gray-800" : "hover:bg-gray-100"
              }`}
            >
              {s === "score" ? "점수" : s === "views" ? "조회수" : "글수"}
            </button>
          ))}
        </div>
      </div>

      {/* 테이블 */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="w-full min-w-[680px] text-sm">
          <thead className="bg-gray-50 text-left text-xs text-gray-500">
            <tr>
              <th className="px-4 py-3">등급</th>
              <th className="px-4 py-3">작성자</th>
              <th className="px-4 py-3">성향</th>
              <th className="px-4 py-3">계열</th>
              <th className="px-4 py-3">플랫폼</th>
              <th className="px-4 py-3 text-right">점수</th>
              <th className="px-4 py-3 text-right">조회수</th>
              <th className="px-4 py-3 text-right">글수</th>
              <th className="px-4 py-3 text-right">언급</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading ? (
              <tr><td colSpan={9} className="px-4 py-12 text-center text-gray-400">불러오는 중…</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={9} className="px-4 py-12 text-center text-gray-400">데이터가 없습니다.</td></tr>
            ) : filtered.map((a) => {
              const grade = gradeOf(a.score);
              const tendency = a.tendency ?? "중립/불명";
              const ytUrl = a.mainPlatform === "youtube" && a.authorId?.startsWith("UC")
                ? `https://www.youtube.com/channel/${a.authorId}`
                : null;
              return (
                <tr key={a.id} className="hover:bg-gray-50 transition">
                  <td className="px-4 py-3">
                    <Chip className={GRADE_CHIP[grade]}>{GRADE_LABEL[grade]}</Chip>
                  </td>
                  <td className="px-4 py-3 font-medium">
                    {ytUrl ? (
                      <a href={ytUrl} target="_blank" rel="noreferrer"
                        className="text-blue-600 hover:underline">{a.name}</a>
                    ) : a.name}
                  </td>
                  <td className="px-4 py-3">
                    <Chip className={TENDENCY_CHIP[tendency]}>{tendency}</Chip>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-600">{(a as any).faction ?? "-"}</td>
                  <td className="px-4 py-3 text-gray-500">{platformLabel(a.mainPlatform)}</td>
                  <td className="px-4 py-3 text-right font-bold text-gray-800">{a.score}</td>
                  <td className="px-4 py-3 text-right text-gray-500">{fmtNum(a.totalViews ?? 0)}</td>
                  <td className="px-4 py-3 text-right text-gray-500">{a.postCount}</td>
                  <td className="px-4 py-3 text-right text-gray-500">{a.targetMentions}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
