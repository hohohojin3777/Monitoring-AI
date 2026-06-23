import { useKeywordTrend } from "../lib/data";

export default function Keywords() {
  const { data, loading } = useKeywordTrend();
  const top = data[0]?.top ?? [];
  const max = top.reduce((m, t) => Math.max(m, t.count), 1);

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-900">키워드 동향</h1>
      <p className="mt-0.5 text-sm text-gray-500">
        모니터링 대상과 함께 등장한 키워드 — 일일 빈도 Top 20 (매일 자동 갱신)
      </p>
      <div className="mt-4 rounded-lg border border-gray-200 bg-white p-5">
        {loading ? (
          <p className="py-12 text-center text-gray-400">불러오는 중…</p>
        ) : top.length === 0 ? (
          <p className="py-12 text-center text-gray-400">아직 동반 키워드 데이터가 없습니다.</p>
        ) : (
          <ul className="space-y-2">
            {top.map((t, i) => (
              <li key={t.word} className="flex items-center gap-3">
                <span className="w-6 text-right text-xs text-gray-400">{i + 1}</span>
                <span className="w-28 truncate font-medium text-gray-800">{t.word}</span>
                <div className="h-3 flex-1 rounded bg-gray-100">
                  <div
                    className="h-3 rounded bg-brand"
                    style={{ width: `${(t.count / max) * 100}%` }}
                  />
                </div>
                <span className="w-10 text-right text-xs text-gray-500">{t.count}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
