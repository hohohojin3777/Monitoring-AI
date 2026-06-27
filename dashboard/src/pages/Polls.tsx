import { useMemo, useRef, useState, Fragment } from "react";
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
  pollster?: string;
  media?: string;
  pollPeriod?: string;
  sampleSize?: number;
  marginOfError?: string;
  surveyMethod?: string;
  // dedupeKey 병합 관련
  dedupeKey?: string;
  sourceArticles?: { title: string; url: string; publishedAt?: any; platform?: string }[];
  needsReview?: boolean;
  manualVerified?: boolean;
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

// ── 여론조사 테이블 (sourceArticles 펼침 + needsReview) ───────
function PollTable({ polls }: { polls: Poll[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const HEADERS = ["조사기간", "조사기관", "의뢰 매체", "조사대상", "표본", "오차범위",
    "김민석", "정청래", "송영길", "김용민", "1위", "원문기사", "확인상태"];

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-navy text-white">
              {HEADERS.map((h) => (
                <th key={h} className="px-3 py-3 text-left text-xs font-semibold whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {polls.map((p) => {
              const cands = getGeneralCands(p);
              const get = (name: string) => cands.find((c) => c.name === name)?.pct;
              const top = [...cands].filter((c) => CANDIDATES_ALL.includes(c.name)).sort((a, b) => b.pct - a.pct)[0];
              const link = p.detailUrl || p.url;
              const kim = get("김민석");
              const isExpanded = expanded.has(p.id);
              const articles = p.sourceArticles ?? (link ? [{ title: p.title ?? "", url: link }] : []);

              return (
                <Fragment key={p.id}>
                  <tr className="hover:bg-gray-50 transition">
                    <td className="px-3 py-2.5 text-xs text-gray-600 whitespace-nowrap font-mono">
                      {p.pollPeriod || dateOf(p) || "-"}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-gray-700 whitespace-nowrap font-semibold">
                      {p.pollster || p.org || p.client || "-"}
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
                    <td className={`px-3 py-2.5 text-sm font-black whitespace-nowrap ${kim !== undefined ? "text-brand" : "text-gray-300"}`}>
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
                    <td className="px-3 py-2.5 text-xs font-bold whitespace-nowrap" style={{ color: COLORS[top?.name ?? ""] ?? DEFAULT_COLOR }}>
                      {top?.name ?? "-"}{top && <span className="ml-1 text-gray-400 font-normal">({top.pct}%)</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      {articles.length > 0 ? (
                        <button onClick={() => toggle(p.id)} className="text-xs text-brand hover:underline whitespace-nowrap">
                          원문 {articles.length}건 {isExpanded ? "▲" : "▼"}
                        </button>
                      ) : <span className="text-xs text-gray-300">-</span>}
                    </td>
                    <td className="px-3 py-2.5 text-xs whitespace-nowrap">
                      {p.manualVerified && <span className="rounded bg-green-100 px-1.5 py-0.5 text-green-700 font-bold">수동검증</span>}
                      {p.needsReview && !p.manualVerified && <span className="rounded bg-yellow-100 px-1.5 py-0.5 text-yellow-700">확인필요</span>}
                      {!p.needsReview && !p.manualVerified && <span className="text-gray-300">-</span>}
                    </td>
                  </tr>
                  {isExpanded && articles.length > 0 && (
                    <tr className="bg-blue-50">
                      <td colSpan={HEADERS.length} className="px-6 py-3">
                        <div className="text-xs font-bold text-gray-500 mb-1.5">원문 기사 {articles.length}건</div>
                        <div className="space-y-1">
                          {articles.map((a, i) => (
                            <div key={i} className="flex items-center gap-2">
                              <a href={a.url} target="_blank" rel="noreferrer"
                                className="text-xs text-brand hover:underline truncate max-w-xl">
                                {a.title || a.url}
                              </a>
                              <span className="text-xs text-gray-400 shrink-0">
                                {a.publishedAt?.toDate?.()?.toISOString?.()?.slice(0, 10) ?? ""}
                              </span>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── 수동 입력/수정 폼 (자동 추출 보정용) ────────────────────────
function ManualPollForm({ editPoll, onClose }: { editPoll?: Poll; onClose: () => void }) {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    pollster: editPoll?.pollster ?? "",
    media: editPoll?.media ?? "",
    pollPeriod: editPoll?.pollPeriod ?? "",
    sampleGroup: editPoll?.sampleGroup ?? editPoll?.respondents ?? "",
    sampleSize: editPoll?.sampleSize?.toString() ?? "",
    marginOfError: editPoll?.marginOfError ?? "",
    surveyMethod: editPoll?.surveyMethod ?? "",
    kim: getGeneralCands(editPoll ?? {} as Poll).find((c) => c.name === "김민석")?.pct?.toString() ?? "",
    jcr: getGeneralCands(editPoll ?? {} as Poll).find((c) => c.name === "정청래")?.pct?.toString() ?? "",
    syg: getGeneralCands(editPoll ?? {} as Poll).find((c) => c.name === "송영길")?.pct?.toString() ?? "",
    kym: getGeneralCands(editPoll ?? {} as Poll).find((c) => c.name === "김용민")?.pct?.toString() ?? "",
    url: editPoll?.url ?? "",
  });

  function set(k: keyof typeof form, v: string) {
    setForm((prev) => ({ ...prev, [k]: v }));
  }

  async function handleSave() {
    const { savePollManual } = await import("../lib/data");
    setSaving(true);
    try {
      const candidatesGeneral = [
        { name: "김민석", pct: parseFloat(form.kim) },
        { name: "정청래", pct: parseFloat(form.jcr) },
        { name: "송영길", pct: parseFloat(form.syg) },
        { name: "김용민", pct: parseFloat(form.kym) },
      ].filter((c) => !isNaN(c.pct));

      await savePollManual(editPoll?.id ?? null, {
        pollster: form.pollster,
        media: form.media,
        pollPeriod: form.pollPeriod,
        sampleGroup: form.sampleGroup,
        sampleSize: form.sampleSize ? parseInt(form.sampleSize) : null,
        marginOfError: form.marginOfError,
        surveyMethod: form.surveyMethod,
        url: form.url,
        candidatesGeneral,
        hasData: candidatesGeneral.length >= 2,
        needsReview: false,
        source: "manual",
      });
      alert("저장됐습니다.");
      onClose();
    } catch (e) {
      alert("저장 실패: " + e);
    } finally {
      setSaving(false);
    }
  }

  const inputCls = "w-full rounded border border-gray-200 px-2.5 py-1.5 text-sm focus:outline-none focus:border-brand";
  const labelCls = "text-xs font-bold text-gray-500 mb-1";

  return (
    <div className="rounded-xl border border-brand/30 bg-blue-50 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-gray-800">
          {editPoll ? "여론조사 수정" : "여론조사 수동 입력"} — 자동 추출 보정용
        </h3>
        <button onClick={onClose} className="text-xs text-gray-400 hover:text-gray-600">✕ 닫기</button>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div><p className={labelCls}>조사기관 *</p><input className={inputCls} value={form.pollster} onChange={(e) => set("pollster", e.target.value)} placeholder="한국갤럽" /></div>
        <div><p className={labelCls}>의뢰 매체</p><input className={inputCls} value={form.media} onChange={(e) => set("media", e.target.value)} placeholder="KBS" /></div>
        <div><p className={labelCls}>조사기간</p><input className={inputCls} value={form.pollPeriod} onChange={(e) => set("pollPeriod", e.target.value)} placeholder="2026-06-20~2026-06-22" /></div>
        <div><p className={labelCls}>조사대상</p><input className={inputCls} value={form.sampleGroup} onChange={(e) => set("sampleGroup", e.target.value)} placeholder="전국 만18세 이상" /></div>
        <div><p className={labelCls}>표본 수</p><input className={inputCls} type="number" value={form.sampleSize} onChange={(e) => set("sampleSize", e.target.value)} placeholder="1000" /></div>
        <div><p className={labelCls}>오차범위</p><input className={inputCls} value={form.marginOfError} onChange={(e) => set("marginOfError", e.target.value)} placeholder="±3.1%p" /></div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div><p className={labelCls}>김민석 (%)</p><input className={inputCls} type="number" step="0.1" value={form.kim} onChange={(e) => set("kim", e.target.value)} /></div>
        <div><p className={labelCls}>정청래 (%)</p><input className={inputCls} type="number" step="0.1" value={form.jcr} onChange={(e) => set("jcr", e.target.value)} /></div>
        <div><p className={labelCls}>송영길 (%)</p><input className={inputCls} type="number" step="0.1" value={form.syg} onChange={(e) => set("syg", e.target.value)} /></div>
        <div><p className={labelCls}>김용민 (%)</p><input className={inputCls} type="number" step="0.1" value={form.kym} onChange={(e) => set("kym", e.target.value)} /></div>
      </div>
      <div><p className={labelCls}>원문 URL</p><input className={inputCls} value={form.url} onChange={(e) => set("url", e.target.value)} placeholder="https://..." /></div>
      <p className="text-xs text-gray-400">수동 입력 데이터는 manualVerified=true로 표시되며 자동 추출로 덮어쓰이지 않습니다.</p>
      <div className="flex gap-2">
        <button onClick={handleSave} disabled={saving || !form.pollster}
          className="rounded-lg bg-brand px-4 py-2 text-sm font-bold text-white hover:opacity-80 disabled:opacity-40">
          {saving ? "저장 중…" : "저장"}
        </button>
        <button onClick={onClose} className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">취소</button>
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
  const [showManualForm, setShowManualForm] = useState(false);

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
          label="최근 조사 1위"
          value={(() => {
            const top = polls[0] ? [...getGeneralCands(polls[0])].sort((a, b) => b.pct - a.pct)[0] : null;
            return top ? `${top.name} ${top.pct}%` : "-";
          })()}
          sub={polls[0]?.pollster || polls[0]?.org || ""}
          color="text-navy"
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

      {/* 수동 입력 폼 */}
      {showManualForm && <ManualPollForm onClose={() => setShowManualForm(false)} />}

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
        <button onClick={() => setShowManualForm((v) => !v)}
          className="rounded-lg border border-brand px-3 py-1.5 text-sm font-semibold text-brand hover:bg-brand/10">
          + 수동 입력
        </button>
      </div>

      {loading ? (
        <p className="py-12 text-center text-sm text-gray-400">불러오는 중...</p>
      ) : polls.length === 0 ? (
        <p className="py-12 text-center text-sm text-gray-400">여론조사 데이터가 없습니다.</p>
      ) : view === "table" ? (
        <>
          {/* ── 테이블 뷰 ── */}
          <PollTable polls={polls} />
          <p className="text-xs text-gray-400 text-center">
            * 중복 제거 기준: 조사기관 + 조사기간 + 조사대상 + 표본수. 원문 기사 N건은 클릭하면 펼쳐집니다.
          </p>

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
