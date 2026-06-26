import { useEffect, useRef, useState } from "react";
import { useReports, deleteReport } from "../lib/data";
import { fmtDate } from "../lib/ui";
import { useAuth } from "../auth";
import type { Report } from "../types";

/** 전당대회까지 D-day */
function dday() {
  const target = new Date("2026-08-17T00:00:00+09:00");
  return Math.ceil((target.getTime() - Date.now()) / 86400000);
}

/** 마크다운 → HTML 렌더러 */
function ReportBody({ text }: { text: string }) {
  const bold = (s: string) =>
    s.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
      part.startsWith("**") && part.endsWith("**") ? (
        <strong key={i}>{part.slice(2, -2)}</strong>
      ) : (
        <span key={i}>{part}</span>
      )
    );

  const lines = text.split("\n");
  const nodes: React.ReactNode[] = [];
  let tableRows: string[] = [];
  let inTable = false;

  const flushTable = () => {
    if (!tableRows.length) return;
    const [header, , ...body] = tableRows;
    nodes.push(
      <div key={`tbl-${nodes.length}`} className="overflow-x-auto my-3">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-navy text-white">
              {(header || "").split("|").filter(Boolean).map((cell, i) => (
                <th key={i} className="px-3 py-2 text-left font-semibold border border-navy/30 whitespace-nowrap">
                  {cell.trim()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((row, ri) => (
              <tr key={ri} className={ri % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                {row.split("|").filter(Boolean).map((cell, ci) => (
                  <td key={ci} className="px-3 py-2 border border-gray-200 text-gray-700">
                    {bold(cell.trim())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
    tableRows = [];
    inTable = false;
  };

  lines.forEach((line, i) => {
    // ===SECTIONX=== 구분자 제거
    if (/^===.*===$/.test(line.trim())) return;
    if (line.trim() === "---") {
      nodes.push(<hr key={i} className="border-gray-200 my-3" />);
      return;
    }
    if (line.startsWith("|")) {
      inTable = true;
      tableRows.push(line);
      return;
    }
    if (inTable) flushTable();

    if (line.startsWith("# ")) {
      nodes.push(
        <h1 key={i} className="text-2xl font-black text-navy mt-4 mb-1 border-b-2 border-navy pb-1">
          {bold(line.slice(2))}
        </h1>
      );
    } else if (line.startsWith("## ")) {
      nodes.push(
        <h2 key={i} className="text-base font-bold text-navy mt-5 mb-2 flex items-center gap-2">
          <span className="inline-block w-1 h-4 bg-brand rounded" />
          {bold(line.slice(3))}
        </h2>
      );
    } else if (line.startsWith("### ")) {
      nodes.push(
        <h3 key={i} className="text-sm font-bold text-gray-800 mt-3 mb-1">{bold(line.slice(4))}</h3>
      );
    } else if (line.startsWith("▶ ") || line.startsWith("▸ ")) {
      nodes.push(
        <div key={i} className="mt-3 flex items-start gap-1.5">
          <span className="text-brand font-bold mt-0.5 shrink-0">{line[0]}</span>
          <p className="text-sm text-gray-800 leading-relaxed">{bold(line.slice(2))}</p>
        </div>
      );
    } else if (line.startsWith("⚑ ") || line.startsWith("⚑")) {
      nodes.push(
        <div key={i} className="mt-2 ml-4 flex items-start gap-1.5 text-sm text-red-700 font-semibold">
          <span className="shrink-0">⚑</span>
          <span>{bold(line.replace(/^⚑\s*/, ""))}</span>
        </div>
      );
    } else if (line.match(/^\*\*.+\*\*$/)) {
      nodes.push(
        <p key={i} className="text-sm text-gray-600 italic mt-1">{bold(line)}</p>
      );
    } else if (line.startsWith("- ")) {
      nodes.push(
        <div key={i} className="ml-4 flex gap-2 text-sm text-gray-700">
          <span className="text-brand shrink-0">•</span>
          <span>{bold(line.slice(2))}</span>
        </div>
      );
    } else if (line.startsWith("*출처")) {
      nodes.push(
        <p key={i} className="text-xs text-gray-400 mt-6 pt-3 border-t border-gray-200">{line.replace(/\*/g, "")}</p>
      );
    } else if (!line.trim()) {
      nodes.push(<div key={i} className="h-1.5" />);
    } else {
      nodes.push(
        <p key={i} className="text-sm text-gray-800 leading-relaxed mt-1">{bold(line)}</p>
      );
    }
  });

  if (inTable) flushTable();
  return <div className="space-y-0.5">{nodes}</div>;
}

type TabType = "daily" | "strategy" | "weekly";

const TAB_META: Record<TabType, { label: string; color: string; desc: string }> = {
  daily:    { label: "동향 브리핑",   color: "bg-navy text-white",         desc: "매일 오전 6시 자동 발행" },
  strategy: { label: "전략 메모",     color: "bg-purple-700 text-white",   desc: "현안 발생 시 즉시 생성" },
  weekly:   { label: "주간 보고서",   color: "bg-emerald-700 text-white",  desc: "매주 금요일 오후 6시 발행" },
};

export default function Reports() {
  const { data, loading } = useReports();
  const [tab, setTab] = useState<TabType>("daily");
  const [sel, setSel] = useState<Report | null>(null);
  const printRef = useRef<HTMLDivElement>(null);
  const { role } = useAuth();
  const isAdmin = role === "admin";

  const filtered = data.filter((r) => (r as any).type === tab || (!((r as any).type) && tab === "daily"));

  useEffect(() => {
    setSel(filtered[0] ?? null);
  }, [tab, data]);

  const handlePrint = () => {
    if (!printRef.current) return;
    const content = printRef.current.innerHTML;
    const win = window.open("", "_blank");
    if (!win) return;
    win.document.write(`
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<title>전당대회 동향 브리핑 D-${dday()}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', sans-serif; font-size: 11pt; color: #1a1a2e; line-height: 1.6; padding: 18mm 20mm; }
  h1 { font-size: 18pt; font-weight: 900; color: #1f3a5f; border-bottom: 2.5pt solid #1f3a5f; padding-bottom: 4pt; margin-bottom: 4pt; }
  h2 { font-size: 12pt; font-weight: 700; color: #173B63; margin-top: 14pt; margin-bottom: 6pt; border-left: 3pt solid #005BAC; padding-left: 6pt; }
  p, div { font-size: 10.5pt; margin-bottom: 2pt; }
  strong { font-weight: 700; }
  table { width: 100%; border-collapse: collapse; font-size: 10pt; margin: 8pt 0; }
  th { background: #1f3a5f; color: white; padding: 5pt 8pt; text-align: left; font-weight: 700; border: 0.5pt solid #ccc; }
  td { padding: 4pt 8pt; border: 0.5pt solid #ddd; }
  tr:nth-child(even) td { background: #f9f9f9; }
  .check { color: #c0392b; font-weight: 700; margin-left: 12pt; }
  .bullet { color: #e87722; font-weight: 700; }
  @page { margin: 18mm 20mm; size: A4; }
  @media print { body { padding: 0; } }
</style>
</head>
<body>
${content}
</body>
</html>`);
    win.document.close();
    setTimeout(() => win.print(), 500);
  };

  return (
    <div>
      {/* 헤더 */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">보고서</h1>
          <p className="mt-0.5 text-sm text-gray-500">8·17 전당대회 D-{dday()}</p>
        </div>
        {sel && (
          <button onClick={handlePrint}
            className="flex items-center gap-1.5 rounded-lg bg-navy px-4 py-2 text-sm font-semibold text-white hover:bg-navy/90 transition">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
            </svg>
            인쇄 / PDF
          </button>
        )}
      </div>

      {/* 탭 */}
      <div className="flex gap-2 mb-4">
        {(Object.entries(TAB_META) as [TabType, typeof TAB_META[TabType]][]).map(([key, meta]) => {
          const count = data.filter((r) => (r as any).type === key || (!((r as any).type) && key === "daily")).length;
          return (
            <button key={key} onClick={() => setTab(key)}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition ${
                tab === key ? meta.color + " shadow-sm" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}>
              {meta.label}
              <span className={`text-xs rounded-full px-1.5 py-0.5 ${tab === key ? "bg-white/20" : "bg-gray-300 text-gray-600"}`}>
                {count}
              </span>
            </button>
          );
        })}
      </div>
      <p className="text-xs text-gray-400 mb-4">{TAB_META[tab].desc}</p>

      {loading ? (
        <p className="py-16 text-center text-gray-400">불러오는 중…</p>
      ) : filtered.length === 0 ? (
        <div className="py-16 text-center">
          <p className="text-gray-400 mb-2">아직 {TAB_META[tab].label}가 없습니다.</p>
          {tab === "daily" && (
            <p className="text-xs text-gray-400">매일 오전 6시 자동 생성됩니다.</p>
          )}
          {tab === "strategy" && (
            <p className="text-xs text-gray-400">클러스터 상세에서 전략 분석 요청 버튼을 누르거나 자동 생성됩니다.</p>
          )}
          {tab === "weekly" && (
            <p className="text-xs text-gray-400">매주 금요일 오후 6시 자동 생성됩니다.</p>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-[240px_1fr]">
          {/* 목록 */}
          <aside className="space-y-2">
            {filtered.map((r) => (
              <div key={r.id} className="relative group">
                <button onClick={() => setSel(r)}
                  className={`block w-full rounded-lg border p-3 text-left text-sm transition ${
                    sel?.id === r.id
                      ? "border-brand bg-orange-50/40 shadow-sm"
                      : "border-gray-200 bg-white hover:border-gray-300"
                  }`}>
                  <div className="font-semibold text-gray-800">
                    {(r as any).topic
                      ? (r as any).topic
                      : tab === "weekly" ? "주간 보고서" : "동향 브리핑"}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">{fmtDate(r.generatedAt)}</div>
                  {r.totals && (
                    <div className="mt-1.5 flex gap-2 text-xs text-gray-500">
                      <span>이슈 {r.totals.uniqueIssues}</span>
                      <span className="text-grade-red font-semibold">알림 {r.totals.alerts}</span>
                      {(r as any).dday && (
                        <span className="ml-auto text-brand font-bold">D-{(r as any).dday}</span>
                      )}
                    </div>
                  )}
                </button>
                {isAdmin && (
                  <button
                    onClick={async (e) => {
                      e.stopPropagation();
                      if (!confirm("이 보고서를 삭제하시겠습니까?")) return;
                      await deleteReport(r.id!);
                      if (sel?.id === r.id) setSel(null);
                    }}
                    className="absolute top-2 right-2 hidden group-hover:flex items-center justify-center w-6 h-6 rounded bg-red-100 text-red-500 hover:bg-red-200 transition"
                    title="삭제">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>
            ))}
          </aside>

          {/* 본문 */}
          <div className="space-y-3">
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
              <div className={`${TAB_META[tab].color} px-6 py-3 flex items-center justify-between`}>
                <div>
                  <span className="text-xs opacity-70 font-medium tracking-wide uppercase">HOrizon0817</span>
                  <span className="mx-2 opacity-40">|</span>
                  <span className="text-sm font-semibold">{TAB_META[tab].label}</span>
                </div>
                <span className="font-bold text-sm opacity-80">D-{dday()}</span>
              </div>
              <div ref={printRef} className="p-6">
                {sel ? <ReportBody text={sel.bodyMarkdown} /> : null}
              </div>
            </div>

            {/* 텔레그램 발송용 요약 */}
            {sel && (sel as any).telegramText && (
              <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
                <div className="bg-gray-700 px-4 py-2.5 flex items-center justify-between">
                  <span className="text-xs font-semibold text-white">Telegram 발송 요약문</span>
                  <button
                    onClick={() => navigator.clipboard.writeText((sel as any).telegramText)}
                    className="text-[11px] text-gray-300 hover:text-white transition"
                  >
                    복사
                  </button>
                </div>
                <div className="p-4 bg-gray-50">
                  <pre className="text-xs text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
                    {(sel as any).telegramText}
                  </pre>
                </div>
              </div>
            )}

            {/* 발송 상태 */}
            {sel && (
              <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                <h3 className="text-xs font-semibold text-gray-500 mb-2">발송 상태</h3>
                <div className="flex gap-3 flex-wrap text-xs">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-green-accent" />
                    <span className="text-gray-700">Firestore 저장 완료</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <span className={(sel as any).telegramText ? "w-2 h-2 rounded-full bg-green-accent" : "w-2 h-2 rounded-full bg-gray-300"} />
                    <span className="text-gray-700">Telegram {(sel as any).telegramText ? "발송됨" : "미발송"}</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <span className={(sel as any).bodyMarkdown ? "w-2 h-2 rounded-full bg-green-accent" : "w-2 h-2 rounded-full bg-gray-300"} />
                    <span className="text-gray-700">PDF {(sel as any).bodyMarkdown ? "생성 가능" : "없음"}</span>
                  </span>
                  {(sel as any).model && (
                    <span className="text-gray-400">모델: {(sel as any).model}</span>
                  )}
                  {(sel as any).sourceIssueCount !== undefined && (
                    <span className="text-gray-400">사용 이슈: {(sel as any).sourceIssueCount}건</span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
