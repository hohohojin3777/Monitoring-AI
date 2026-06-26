import { useMemo, useRef, useState } from "react";
// useState used in TrendChart hover
import { usePolls } from "../lib/data";

const CANDIDATES = ["이재명", "정청래", "김민석", "송영길", "김용민", "김두관", "강훈식"];
const COLORS: Record<string, string> = {
  이재명: "#1971c2", 정청래: "#e03131", 김민석: "#2f9e44",
  송영길: "#f08c00", 김용민: "#7950f2", 김두관: "#0c8599", 강훈식: "#d6336c",
};
const DEFAULT_COLOR = "#868e96";

type Poll = {
  id: string;
  source: "nesdc" | "news";
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
  candidatesGeneral?: { name: string; pct: number }[];  // 전국 일반 국민
  candidatesParty?: { name: string; pct: number }[];    // 민주당 지지층
  imageUrl?: string;
  content?: string;
};

function dateOf(p: Poll): string {
  const raw = p.regDate || p.publishedAt?.toDate?.()?.toISOString() || p.savedAt?.toDate?.()?.toISOString() || "";
  return raw.slice(0, 10);
}

function CandidateBar({ name, pct, max }: { name: string; pct: number; max: number }) {
  const color = COLORS[name] ?? DEFAULT_COLOR;
  return (
    <div className="flex items-center gap-2">
      <span className="w-14 shrink-0 text-right text-xs font-semibold text-gray-700">{name}</span>
      <div className="flex-1 overflow-hidden rounded-full bg-gray-100 h-5">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${(pct / max) * 100}%`, backgroundColor: color }}
        />
      </div>
      <span className="w-12 shrink-0 text-right text-sm font-bold" style={{ color }}>{pct}%</span>
    </div>
  );
}

function PollCard({ poll }: { poll: Poll }) {
  const rawCands = poll.candidatesGeneral ?? poll.candidates ?? [];
  const seen = new Set<string>();
  const candidates = rawCands.filter((c) => {
    if (!CANDIDATES.includes(c.name) || seen.has(c.name)) return false;
    seen.add(c.name);
    return true;
  });
  const max = candidates.length ? Math.max(...candidates.map((c) => c.pct)) : 100;
  const link = poll.detailUrl || poll.url;
  const label = poll.source === "nesdc" ? "NESDC 공식" : "뉴스";
  const labelColor = poll.source === "nesdc" ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-600";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 mb-1">
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${labelColor}`}>{label}</span>
            <span className="text-xs text-gray-400">{dateOf(poll)}</span>
            {(poll.org || poll.client) && (
              <span className="text-xs text-gray-400">· {poll.org || poll.client}</span>
            )}
          </div>
          <p className="text-sm font-semibold leading-snug text-gray-800">
            {poll.name || poll.title || "(제목 없음)"}
          </p>
        </div>
        {link && (
          <a href={link} target="_blank" rel="noreferrer"
            className="shrink-0 rounded-lg bg-brand px-3 py-1.5 text-xs font-bold text-white hover:opacity-80 transition">
            원문 ↗
          </a>
        )}
      </div>

      {candidates.length >= 2 && (
        <div className="mt-3 flex flex-col gap-1.5">
          {candidates
            .sort((a, b) => b.pct - a.pct)
            .map((c) => <CandidateBar key={c.name} name={c.name} pct={c.pct} max={max} />)}
        </div>
      )}

      {poll.imageUrl && (
        <a href={link} target="_blank" rel="noreferrer" className="mt-3 block">
          <img src={poll.imageUrl} alt={poll.title}
            className="w-full max-h-56 rounded-lg object-cover border border-gray-100"
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
        </a>
      )}

      {!candidates.length && poll.content && (
        <p className="mt-2 text-xs text-gray-500 line-clamp-3">{poll.content}</p>
      )}
    </div>
  );
}

// 각 poll 에서 일반/지지층 후보 데이터 추출
function getGeneralCandidates(p: Poll) {
  return p.candidatesGeneral ?? p.candidates ?? [];
}
function getPartyCandidates(p: Poll) {
  return p.candidatesParty ?? [];
}

// 날짜별 후보 평균 집계 헬퍼
function buildSeries(polls: Poll[], getCandidates: (p: Poll) => { name: string; pct: number }[]) {
  const byDate: Record<string, Record<string, number[]>> = {};
  for (const p of polls) {
    const d = dateOf(p);
    if (!d) continue;
    const seenInPoll = new Set<string>();
    for (const c of getCandidates(p)) {
      if (!CANDIDATES.includes(c.name) || seenInPoll.has(c.name)) continue;
      seenInPoll.add(c.name);
      if (!byDate[d]) byDate[d] = {};
      if (!byDate[d][c.name]) byDate[d][c.name] = [];
      byDate[d][c.name].push(c.pct);
    }
  }
  const dates = Object.keys(byDate).sort();
  const active = CANDIDATES.filter((n) => dates.some((d) => byDate[d][n]?.length));
  const series: Record<string, (number | null)[]> = {};
  for (const n of active) {
    series[n] = dates.map((d) => {
      const v = byDate[d][n];
      return v?.length ? Math.round((v.reduce((a, b) => a + b, 0) / v.length) * 10) / 10 : null;
    });
  }
  return { dates, active, series };
}

// 시계열 트렌드 차트 (hover 툴팁 지원)
function TrendChart({ polls, title, getCandidates }: {
  polls: Poll[];
  title: string;
  getCandidates: (p: Poll) => { name: string; pct: number }[];
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const withData = polls.filter((p) => getCandidates(p).some((c) => CANDIDATES.includes(c.name)));
  const { dates, active, series } = useMemo(() => buildSeries(withData, getCandidates), [withData]);

  if (withData.length < 1 || !active.length) return (
    <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-sm text-gray-400">
      {title} — 데이터 없음
    </div>
  );

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
      <h2 className="mb-3 text-sm font-bold text-gray-800">📈 {title}</h2>

      {/* hover 툴팁 — overflow 컨테이너 밖에 위치 */}
      {hoverIdx !== null && hoverData.length > 0 && (
        <div className="mb-2 flex flex-wrap items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs">
          <span className="font-semibold text-gray-500">{dates[hoverIdx]?.slice(5)}</span>
          {hoverData
            .sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0))
            .map((d) => (
              <span key={d.name} className="flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: COLORS[d.name] ?? DEFAULT_COLOR }} />
                <span className="text-gray-700">{d.name}</span>
                <span className="font-bold" style={{ color: COLORS[d.name] ?? DEFAULT_COLOR }}>{d.pct}%</span>
              </span>
            ))}
        </div>
      )}

      <div style={{ minWidth: W }} className="overflow-x-auto">
        {/* SVG 차트 */}
        <svg
          ref={svgRef}
          width={W} height={H + 24}
          className="overflow-visible cursor-crosshair"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverIdx(null)}
        >
          {/* 격자선 */}
          {[0, 25, 50, 75, 100].map((v) => (
            <g key={v}>
              <line x1={PAD_L} y1={yOf(v)} x2={W - PAD_R} y2={yOf(v)} stroke="#f1f3f5" strokeWidth={1} />
              <text x={PAD_L - 4} y={yOf(v) + 4} textAnchor="end" fontSize={9} fill="#adb5bd">{v}%</text>
            </g>
          ))}

          {/* 꺾은선 + 점 */}
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
                {pts.map((val, i) => val !== null ? (
                  <circle key={i} cx={xOf(i)} cy={yOf(val)} r={hoverIdx === i ? 6 : 4}
                    fill={color} stroke="white" strokeWidth={1.5} />
                ) : null)}
              </g>
            );
          })}

          {/* hover 세로선 */}
          {hoverIdx !== null && (
            <line x1={xOf(hoverIdx)} y1={0} x2={xOf(hoverIdx)} y2={H}
              stroke="#ced4da" strokeWidth={1} strokeDasharray="4 3" />
          )}

          {/* X축 날짜 */}
          {dates.map((d, i) => (
            <text key={d} x={xOf(i)} y={H + 16} textAnchor="middle" fontSize={9} fill="#adb5bd">{d.slice(5)}</text>
          ))}
        </svg>

        {/* 범례 */}
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

export default function Polls() {
  const { data: allPolls, loading } = usePolls();

  const polls: Poll[] = useMemo(() => {
    const list = allPolls as Poll[];
    return list
      .filter((p) => p.source !== "nesdc" && !p.url?.includes("blog.naver.com") && !p.url?.includes("blog.daum"))
      .filter((p) => (p.candidates ?? []).some((c) => CANDIDATES.includes(c.name)) ||
        (p.candidatesGeneral ?? []).some((c) => CANDIDATES.includes(c.name)))
      .sort((a, b) => dateOf(b).localeCompare(dateOf(a)));
  }, [allPolls]);

  const withData = useMemo(() => polls.filter((p) => (getGeneralCandidates(p)).length >= 1 || (getPartyCandidates(p)).length >= 1), [polls]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-gray-900">여론조사 동향</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          전당대회 당대표 후보 지지율 — 일반여론조사 30% · 권리당원 여론조사 70% 반영
        </p>
      </div>

      {/* 트렌드 차트 — 일반 / 민주당 지지층 */}
      <TrendChart polls={withData} title="시기별 지지율 추이 (일반여론조사 — 전국 성인)" getCandidates={getGeneralCandidates} />
      <TrendChart polls={withData} title="시기별 지지율 추이 (민주당 지지층)" getCandidates={getPartyCandidates} />

      <div className="flex justify-end">
        <span className="text-sm text-gray-400">{polls.length}건</span>
      </div>

      {/* 목록 */}
      {loading ? (
        <p className="py-12 text-center text-sm text-gray-400">불러오는 중...</p>
      ) : polls.length === 0 ? (
        <p className="py-12 text-center text-sm text-gray-400">여론조사 데이터가 없습니다.</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {polls.map((p) => <PollCard key={p.id} poll={p} />)}
        </div>
      )}
    </div>
  );
}
