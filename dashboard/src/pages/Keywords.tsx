import { useKeywordTrend } from "../lib/data";

const BAR_COLORS = [
  "bg-blue-500", "bg-indigo-500", "bg-violet-500", "bg-purple-500",
  "bg-pink-500", "bg-rose-500", "bg-orange-500", "bg-amber-500",
  "bg-yellow-500", "bg-lime-500", "bg-green-500", "bg-teal-500",
  "bg-cyan-500", "bg-sky-500", "bg-blue-400", "bg-indigo-400",
  "bg-violet-400", "bg-purple-400", "bg-pink-400", "bg-rose-400",
];

export default function Keywords() {
  const { data, loading } = useKeywordTrend();
  const top = data[0]?.top ?? [];
  const date = data[0]?.date ?? "";
  const max = top.reduce((m, t) => Math.max(m, t.count), 1);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-gray-900">키워드 동향</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          모니터링 기사·게시글 제목에서 자주 등장한 키워드 Top 20 — 등록 키워드·인물명 제외, 조사 제거 후 집계
          {date && <span className="ml-2 text-gray-400">({date} 기준)</span>}
        </p>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        {loading ? (
          <p className="py-12 text-center text-gray-400">불러오는 중…</p>
        ) : top.length === 0 ? (
          <p className="py-12 text-center text-gray-400">
            아직 키워드 데이터가 없습니다.<br />
            <span className="text-xs">파이프라인 실행 후 자동 생성됩니다.</span>
          </p>
        ) : (
          <div className="space-y-2.5">
            {top.map((t, i) => (
              <div key={t.word} className="flex items-center gap-3">
                <span className="w-6 shrink-0 text-right text-xs font-bold text-gray-300">{i + 1}</span>
                <span className="w-24 shrink-0 truncate text-sm font-semibold text-gray-800">{t.word}</span>
                <div className="flex-1 overflow-hidden rounded-full bg-gray-100 h-4">
                  <div
                    className={`h-4 rounded-full ${BAR_COLORS[i % BAR_COLORS.length]} transition-all duration-500`}
                    style={{ width: `${Math.max((t.count / max) * 100, 4)}%` }}
                  />
                </div>
                <span className="w-10 shrink-0 text-right text-xs font-semibold text-gray-500">{t.count}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
