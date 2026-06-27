import { useMemo, useRef, useState } from "react";
import { usePolls } from "../lib/data";

const CANDIDATES_ORDER = ["김민석", "정청래", "송영길", "김용민"];
const CANDIDATES_ALL = ["정청래", "김민석", "송영길", "김용민", "김두관", "강훈식"];

const COLORS: Record<string, string> = {
  정청래: "#7950f2", 김민석: "#005BAC",
  송영길: "#e6a817", 김용민: "#6D5DF6", 김두관: "#0c8599", 강훈식: "#d6336c",
};
const DEFAULT_COLOR = "#9ca3af";

type Poll = {
  id: string;
  source?: string;
  title?: string;
  name?: string;
  org?: string;
  client?: string;
  regDate?: string;
  publishedAt?: any;
  savedAt?: any;
  url?: string;
  detailUrl?: string;
  candidates?: { name: string; pct: number }[];
  candidatesGeneral?: { name: string; pct: number }[];
  candidatesParty?: { name: string; pct: number }[];
  sampleGroup?: string;
  respondents?: string;
  imageUrl?: string;
  content?: string;
  // 신규 메타 필드
  pollster?: string;       // 조사기관
  media?: string;          // 의뢰 매체
  pollPeriod?: string;     // 조사기간
  sampleSize?: number;     // 표본 수
  marginOfError?: string;  // 오차범위
  surveyMethod?: string;   // 조사방법
};

function dateOf(p: Poll): string {
  const raw =
    p.regDate ||
    p.publishedAt?.toDate?.()?.toISOString() ||
    p.savedAt?.toDate?.()?.toISOString() ||
    "";
  return raw.slice(0, 10);
}

function getGeneralCands(p: Poll) {
  return p.candidatesGeneral ?? p.candidates ?? [];
}
function getPartyCands(p: Poll) {
  return p.candidatesParty ?? [];
}

// ── 트렌드 차트 ────────────────────────────────────────────────
function buildSeries(polls: Poll[], getCands: (p: Poll) => { name: string; pct: number }[]) {
  const byDate: Record<string, Record<string, number[]>> = {};
  for (const p of polls) {
    const d = dateOf(p);
    if (!d) continue;
    const seen = new Set<string>();
    for (const c of getCands(p)) {
      if (!CANDIDATES_ALL.includes(c.name) || seen.has(c.name)) continue;
      seen.add(c.name);
      if (!byDate[d]) byDate[d] = {};
      if (!byDate[d][c.name]) byDate[d][c.name] = [];
      byDate[d][c.name].push(c.pct);
    }
  }
  const dates = Object.keys(byDate).sort();
  const active = CANDIDATES_ALL.filter((n) => dates.some((d) => byDate[d][n]?.length));
  const series: Record<string, (number | null)[]> = {};
  for (const n of active) {
    series[n] = dates.map((d) => {
      const v = byDate[d][n];
      return v?.length ? Math.round((v.reduce((a, b) => a + b, 0) / v.length) * 10) / 10 : null;
    });
  }
  return { dates, active, series };
}

function TrendChart({
  polls, title, getCands,
}: {
  polls: Poll[]; title: string; getCands: (p: Poll) => { name: string; pct: number }[];
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const withData = polls.filter((p) => getCands(p).some((c) => CANDIDATES_ALL.includes(c.name)));
  const { dates, active, series } = useMemo(() => buildSeries(withData, getCands), [withData]);

  if (!active.length) {
    return (
      <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-sm text-gray-400">
        {title} — 데이터 없음
      </div>
    );
  }

  const H = 160; const PAD_L = 36; const PAD_R = 12;
  const W = Math.max(dates.length * 70, 320);
  const INNER_W = W - PAD_L - PAD_R;
  const xOf = (i: number) => PAD_L + (dates.length < 2 ? INNER_W / 2 : (i / (dates.length - 1)) * INNER_W);
  const yOf = (pct: number) => H - (pct / 100) * H;

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    if (dates.length === 1) { setHoverIdx(0); return; }
    const relX = e.clientX - rect.left - PAD_L;
    const step = INNER_W / (dates.length - 1);
    const idx = Math.round(relX / step);
    setHoverIdx(Math.max(0, Math.min(idx, dates.length - 1)));
  };

  const hoverData = hoverIdx !== null
    ? active.map((n) => ({ name: n, pct: series[n][hoverIdx] })).filter((d) => d.pct !== null)
    : [];

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-bold text-gray-700">{title}</h3>
      {hoverIdx !== null && hoverData.length > 0 && (
        <div className="mb-2 flex flex-wrap items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs">
          <span className="font-semibold text-gray-500">{dates[hoverIdx]?.slice(5)}</span>
          {hoverData.sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0)).map((d) => (
            <span key={d.name} className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: COLORS[d.name] ?? DEFAULT_COLOR }} />
              <span className="text-gray-700">{d.name}</span>
              <span className="font-bold" style={{ color: COLORS[d.name] ?? DEFAULT_COLOR }}>{d.pct}%</span>
            </span>
          ))}
        </div>
      )}
      <div style={{ minWidth: W }} className="overflow-x-auto">
        <svg
          ref={svgRef} width={W} height={H + 24}
          className="overflow-visible cursor-crosshair"
          onMouseMove={handleMouseMove} onMouseLeave={() => setHoverIdx(null)}
        >
          {[0, 25, 50, 75, 100].map((v) => (
            <g key={v}>
              <line x1={PAD_L} y1={yOf(v)} x2={W - PAD_R} y2={yOf(v)} stroke="#f1f3f5" strokeWidth={1} />
              <text x={PAD_L - 4} y={yOf(v) + 4} textAnchor="end" fontSize={9} fill="#adb5bd">{v}%</text>
            </g>
          ))}
          {active.map((name) => {
            const pts = series[name];
            const color = COLORS[name] ?? DEFAULT_COLOR;
            const pathParts: string[] = [];
            let prev: { x: number; y: number } | null = null;
            pts.forEach((val, i) => {
              if (val === null) { prev = null; return; }
              const x = xOf(i); const y = yOf(val);
              if (prev) pathParts.push(`M${prev.x},${prev.y}L${x},${y}`);
              prev = { x, y };
            });
            return (
              <g key={name}>
                <path d={pathParts.join(" ")} stroke={color} strokeWidth={2.5} fill="none" strokeLinejoin="round" />
                {pts.map((val, i) =>
                  val !== null ? (
                    <circle key={i} cx={xOf(i)} cy={yOf(val)} r={hoverIdx === i ? 6 : 4}
                      fill={color} stroke="white" strokeWidth={1.5} />
                  ) : null
                )}
              </g>
            );
          })}
          {hoverIdx !== null && (
            <line x1={xOf(hoverIdx)} y1={0} x2={xOf(hoverIdx)} y2={H}
              stroke="#ced4da" strokeWidth={1} strokeDasharray="4 3" />
          )}
          {dates.map((d, i) => (
            <text key={d} x={xOf(i)} y={H + 16} textAnchor="middle" fontSize={9} fill="#adb5bd">
              {d.slice(5)}
            </text>
          ))}
        </svg>
        <div className="mt-2 flex flex-wrap gap-3">
          {active.map((name) => (
            <span key={name} className="flex items-center gap-1 text-xs font-medium text-gray-700">
              <span className="inline-block h-2 w-4 rounded-full" style={{ backgroundColor: COLORS[name] ?? DEFAULT_COLOR }} />
              {name}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── KPI 카드 ──────────────────────────────────────────────────
function KpiCard({ label, value, sub, color = "text-navy" }: {
  label: string; value: string; sub?: string; color?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-xs text-gray-500 font-medium">{label}</p>
      <p className={`text-2xl font-black mt-1 ${color}`}>{value}</p>
      {sub && <p className="text-[11px] text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── 메인 ──────────────────────────────────────────────────────
export default function Polls() {
  const { data: allPolls, loading } = usePolls();
  const [view, setView] = useState<"table" | "cards">("table");

  const polls: Poll[] = useMemo(() => {
    return (allPolls as Poll[])
      .filter(
        (p) =>
          !p.url?.includes("blog.naver.com") &&
          !p.url?.includes("blog.daum") &&
          ((p.candidates ?? []).some((c) => CANDIDATES_ALL.includes(c.name)) ||
            (p.candidatesGeneral ?? []).some((c) => CANDIDATES_ALL.includes(c.name)))
      )
      .sort((a, b) => dateOf(b).localeCompare(dateOf(a)));
  }, [allPolls]);

  // 최신 김민석 지지율
  const latestKim = useMemo(() => {
    for (const p of polls) {
      const cands = getGeneralCands(p);
      const found = cands.find((c) => c.name === "김민석");
      if (found) return { pct: found.pct, date: dateOf(p), org: p.org || p.client || p.name || "" };
    }
    return null;
  }, [polls]);

  // 이전 조사 김민석 지지율 (두 번째 조사)
  const prevKim = useMemo(() => {
    let count = 0;
    for (const p of polls) {
      const cands = getGeneralCands(p);
      const found = cands.find((c) => c.name === "김민석");
      if (found) {
        count++;
        if (count === 2) return found.pct;
      }
    }
    return null;
  }, [polls]);

  const kimChange = latestKim && prevKim !== null ? latestKim.pct - prevKim : null;

  return (
    <div className="space-y-5">
      {/* 헤더 */}
      <div>
        <h1 className="text-xl font-bold text-gray-900">여론조사</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          전당대회 당대표 후보 지지율 — 일반여론조사 30% · 권리당원 여론조사 70% 반영
        </p>
      </div>

      {/* KPI 카드 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard
          label="최근 김민석 지지율"
          value={latestKim ? `${latestKim.pct}%` : "-"}
          sub={latestKim ? `${latestKim.date} · ${latestKim.org}` : "데이터 없음"}
          color={latestKim ? "text-brand" : "text-gray-400"}
        />
        <KpiCard
          label="전 조사 대비"
          value={
            kimChange !== null
              ? `${kimChange > 0 ? "▲" : kimChange < 0 ? "▼" : "─"} ${Math.abs(kimChange).toFixed(1)}%p`
              : "-"
          }
          sub="직전 조사 기준"
          color={
            kimChange !== null
              ? kimChange > 0 ? "text-green-accent" : kimChange < 0 ? "text-danger-red" : "text-gray-500"
              : "text-gray-400"
          }
        />
        <KpiCard
          label="총 여론조사 수"
          value={`${polls.length}건`}
          sub="수치 확인된 조사"
          color="text-navy"
        />
        <KpiCard
          label="최신 조사일"
          value={polls[0] ? dateOf(polls[0]).slice(5).replace("-", "/") : "-"}
          sub={polls[0] ? (polls[0].org || polls[0].client || "") : "데이터 없음"}
          color="text-navy"
        />
      </div>

      {/* 뷰 전환 */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setView("table")}
          className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
            view === "table" ? "bg-navy text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          표 보기
        </button>
        <button
          onClick={() => setView("cards")}
          className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
            view === "cards" ? "bg-navy text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          카드 보기
        </button>
        <span className="ml-auto text-sm text-gray-400">{polls.length}건</span>
      </div>

      {loading ? (
        <p className="py-12 text-center text-sm text-gray-400">불러오는 중...</p>
      ) : polls.length === 0 ? (
        <p className="py-12 text-center text-sm text-gray-400">여론조사 데이터가 없습니다.</p>
      ) : view === "table" ? (
        <>
          {/* ── 테이블 뷰 ── */}
          <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-navy text-white">
                    {["조사기간", "조사기관", "의뢰 매체", "조사대상", "표본", "오차범위", "김민석", "정청래", "송영길", "김용민", "1위", "원문"].map(
                      (h) => (
                        <th
                          key={h}
                          className="px-3 py-3 text-left text-xs font-semibold whitespace-nowrap"
                        >
                          {h}
                        </th>
                      )
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {polls.map((p) => {
                    const cands = getGeneralCands(p);
                    const get = (name: string) => cands.find((c) => c.name === name)?.pct;
                    const top = [...cands]
                      .filter((c) => CANDIDATES_ALL.includes(c.name))
                      .sort((a, b) => b.pct - a.pct)[0];
                    const link = p.detailUrl || p.url;
                    const kim = get("김민석");
                    return (
                      <tr key={p.id} className="hover:bg-gray-50 transition">
                        <td className="px-3 py-2.5 text-xs text-gray-600 whitespace-nowrap font-mono">
                          {p.pollPeriod || dateOf(p) || "-"}
                        </td>
                        <td className="px-3 py-2.5 text-xs text-gray-700 whitespace-nowrap">
                          <p className="font-semibold">{p.pollster || p.org || p.client || "-"}</p>
                        </td>
                        <td className="px-3 py-2.5 text-xs text-gray-500 whitespace-nowrap">
                          {p.media || p.name || "-"}
                        </td>
                        <td className="px-3 py-2.5 text-xs text-gray-500 whitespace-nowrap">
                          {p.sampleGroup || p.respondents || "-"}
                        </td>
                        <td className="px-3 py-2.5 text-xs text-gray-400 whitespace-nowrap">
                          {p.sampleSize ? `${p.sampleSize.toLocaleString()}명` : "-"}
                        </td>
                        <td className="px-3 py-2.5 text-xs text-gray-400 whitespace-nowrap">
                          {p.marginOfError || "-"}
                        </td>
                        <td className={`px-3 py-2.5 text-sm font-black whitespace-nowrap ${
                          kim !== undefined ? "text-brand" : "text-gray-300"
                        }`}>
                          {kim !== undefined ? `${kim}%` : "-"}
                        </td>
                        {["정청래", "송영길", "김용민"].map((name) => {
                          const val = get(name);
                          return (
                            <td key={name} className="px-3 py-2.5 text-xs text-gray-600 whitespace-nowrap">
                              {val !== undefined ? `${val}%` : <span className="text-gray-300">-</span>}
                            </td>
                          );
                        })}
                        <td className="px-3 py-2.5 text-xs font-bold whitespace-nowrap"
                          style={{ color: COLORS[top?.name ?? ""] ?? DEFAULT_COLOR }}>
                          {top?.name ?? "-"}
                          {top && <span className="ml-1 text-gray-400 font-normal">({top.pct}%)</span>}
                        </td>
                        <td className="px-3 py-2.5">
                          {link ? (
                            <a href={link} target="_blank" rel="noreferrer"
                              className="text-xs text-brand hover:underline whitespace-nowrap">
                              원문 ↗
                            </a>
                          ) : (
                            <span className="text-xs text-gray-300">-</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* 그래프 */}
          <TrendChart
            polls={polls}
            title="📈 김민석 지지율 추이 (일반여론조사)"
            getCands={getGeneralCands}
          />
          <TrendChart
            polls={polls}
            title="📈 민주당 지지층 기준 지지율 추이"
            getCands={getPartyCands}
          />

          <p className="text-xs text-gray-400 text-center">
            * 수치가 확인된 조사만 표시됩니다. 기사 제목만 있는 경우 수치란은 비워집니다.
          </p>
        </>
      ) : (
        <>
          {/* ── 카드 뷰 ── */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {polls.map((p) => {
              const cands = getGeneralCands(p);
              const filtered = cands.filter((c) => CANDIDATES_ORDER.includes(c.name));
              const max = filtered.length ? Math.max(...filtered.map((c) => c.pct)) : 100;
              const link = p.detailUrl || p.url;
              return (
                <div key={p.id} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <p className="text-xs text-gray-400">{dateOf(p)} · {p.org || p.client || "-"}</p>
                      <p className="text-sm font-semibold text-gray-800 leading-snug mt-0.5">
                        {p.name || p.title || "(제목 없음)"}
                      </p>
                    </div>
                    {link && (
                      <a href={link} target="_blank" rel="noreferrer"
                        className="shrink-0 rounded-lg bg-brand px-3 py-1.5 text-xs font-bold text-white hover:opacity-80">
                        원문 ↗
                      </a>
                    )}
                  </div>
                  {filtered.length >= 2 && (
                    <div className="space-y-1.5 mt-3">
                      {[...filtered].sort((a, b) => b.pct - a.pct).map((c) => (
                        <div key={c.name} className="flex items-center gap-2">
                          <span className="w-14 shrink-0 text-right text-xs font-semibold text-gray-700">{c.name}</span>
                          <div className="flex-1 h-5 rounded-full bg-gray-100 overflow-hidden">
                            <div className="h-full rounded-full"
                              style={{ width: `${(c.pct / max) * 100}%`, backgroundColor: COLORS[c.name] ?? DEFAULT_COLOR }} />
                          </div>
                          <span className="w-12 shrink-0 text-right text-sm font-bold"
                            style={{ color: COLORS[c.name] ?? DEFAULT_COLOR }}>
                            {c.pct}%
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
