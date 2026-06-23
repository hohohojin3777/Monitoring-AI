import { useEffect, useState } from "react";
import { useReports } from "../lib/data";
import { fmtDate } from "../lib/ui";
import type { Report } from "../types";

/** 아주 작은 마크다운 렌더러 (#, ##, -, **bold**) */
function Markdown({ text }: { text: string }) {
  const bold = (s: string) =>
    s.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
      part.startsWith("**") && part.endsWith("**") ? (
        <strong key={i}>{part.slice(2, -2)}</strong>
      ) : (
        <span key={i}>{part}</span>
      )
    );
  return (
    <div className="space-y-1 text-sm leading-relaxed text-gray-800">
      {text.split("\n").map((line, i) => {
        if (line.startsWith("# "))
          return <h2 key={i} className="mt-2 text-lg font-bold">{bold(line.slice(2))}</h2>;
        if (line.startsWith("## "))
          return <h3 key={i} className="mt-3 font-semibold">{bold(line.slice(3))}</h3>;
        if (line.startsWith("- "))
          return <div key={i} className="pl-3">• {bold(line.slice(2))}</div>;
        if (line.startsWith("  - "))
          return <div key={i} className="pl-7 text-gray-500">– {bold(line.slice(4))}</div>;
        if (!line.trim()) return <div key={i} className="h-1" />;
        return <p key={i}>{bold(line)}</p>;
      })}
    </div>
  );
}

export default function Reports() {
  const { data, loading } = useReports();
  const [sel, setSel] = useState<Report | null>(null);
  useEffect(() => {
    if (!sel && data.length) setSel(data[0]);
  }, [data, sel]);

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-900">통합 보고서</h1>
      <p className="mt-0.5 text-sm text-gray-500">
        매일 오전 8시·오후 6시 일일 보고서, 매주 월요일 주간 동향 보고서가 자동 생성됩니다.
      </p>

      {loading ? (
        <p className="py-16 text-center text-gray-400">불러오는 중…</p>
      ) : data.length === 0 ? (
        <p className="py-16 text-center text-gray-400">아직 생성된 보고서가 없습니다.</p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-[260px_1fr]">
          <aside className="space-y-2">
            {data.map((r) => (
              <button
                key={r.id}
                onClick={() => setSel(r)}
                className={`block w-full rounded-lg border p-3 text-left text-sm ${
                  sel?.id === r.id ? "border-brand bg-orange-50/40" : "border-gray-200 bg-white"
                }`}
              >
                <div className="font-semibold">
                  {r.type === "weekly" ? "주간" : "일일"} 보고서
                </div>
                <div className="text-xs text-gray-400">{fmtDate(r.generatedAt)}</div>
                {r.totals && (
                  <div className="mt-1 text-xs text-gray-500">
                    언급 {r.totals.mentions} · 이슈 {r.totals.uniqueIssues} · 알림{" "}
                    <span className="text-grade-red">{r.totals.alerts}</span>
                  </div>
                )}
              </button>
            ))}
          </aside>
          <article className="rounded-lg border border-gray-200 bg-white p-5">
            {sel ? <Markdown text={sel.bodyMarkdown} /> : null}
          </article>
        </div>
      )}
    </div>
  );
}
