import { useMemo, useState } from "react";
import { useClusters } from "../lib/data";
import type { Cluster } from "../types";

// ── 후보 색상 (디자인시스템) ───────────────────────────────────
const C = {
  김민석: { text: "text-[#005BAC]", bar: "bg-[#005BAC]", border: "border-[#005BAC]", light: "bg-blue-50", badge: "bg-blue-100 text-[#005BAC]" },
  정청래: { text: "text-[#7950f2]", bar: "bg-[#7950f2]", border: "border-[#7950f2]", light: "bg-purple-50", badge: "bg-purple-100 text-purple-700" },
  송영길: { text: "text-[#e6a817]", bar: "bg-[#e6a817]", border: "border-[#e6a817]", light: "bg-yellow-50", badge: "bg-yellow-100 text-yellow-700" },
  김용민: { text: "text-[#6D5DF6]", bar: "bg-[#6D5DF6]", border: "border-[#6D5DF6]", light: "bg-indigo-50", badge: "bg-indigo-100 text-indigo-700" },
} as const;
type Cand = keyof typeof C;
const CANDS: Cand[] = ["김민석", "정청래", "송영길", "김용민"];

// ── 알려진 지지 세력 (수동 큐레이션) ─────────────────────────
const KNOWN: Record<Cand, { 의원: string[]; 유튜버: string[]; 단체: string[] }> = {
  김민석: {
    의원:  ["정성호", "전해철", "홍익표", "이원욱", "조응천", "최재성", "김영진", "강득구"],
    유튜버: ["이동형TV", "뷰리핑", "흑백여의도", "뉴스다이브"],
    단체:  ["민주평화국민연대", "더좋은민주당"],
  },
  정청래: {
    의원:  ["박규환", "민형배", "서영교", "양이원영", "최민희", "추미애"],
    유튜버: ["뉴스공장", "매불쇼", "알릴레오", "정치읽어주는여자"],
    단체:  ["친명연대", "개딸(개혁의딸)"],
  },
  송영길: {
    의원:  ["우원식", "설훈", "이상민"],
    유튜버: ["열린공감TV", "참세상"],
    단체:  ["송영길지지모임"],
  },
  김용민: {
    의원:  ["박은정", "김남국"],
    유튜버: ["민트TV"],
    단체:  [],
  },
};

// ── 탐지 로직 ────────────────────────────────────────────────
const SUPPORT_KW = ["지지", "편", "지원", "응원", "찍겠", "뽑겠", "밀어", "찍자", "당대표로", "원팀", "연대", "선언"];
const OPPOSE_KW  = ["반대", "비판", "낙선", "사퇴", "탈락"];
const NON_MINJU  = new Set([
  "한동훈","이준석","안철수","윤석열","오세훈","홍준표","원희룡","나경원",
  "황교안","유승민","김기현","이재오","권성동","주호영","국민의힘","개혁신당",
]);

function detectCamp(c: Cluster): Cand | null {
  const text = `${c.title} ${c.summary ?? ""}`;
  const mentioned = CANDS.filter((n) => text.includes(n));
  if (!mentioned.length) return null;
  if (mentioned.length === 1) return mentioned[0];
  for (const kw of SUPPORT_KW) {
    const idx = text.indexOf(kw);
    if (idx < 0) continue;
    const nearby = text.slice(Math.max(0, idx - 10), idx + 10);
    const found = CANDS.find((n) => nearby.includes(n));
    if (found) return found;
  }
  const safe = mentioned.filter((n) => {
    const idx = text.indexOf(n);
    const nearby = text.slice(Math.max(0, idx - 5), idx + 12);
    return !OPPOSE_KW.some((k) => nearby.includes(k));
  });
  return safe.length === 1 ? safe[0] : null;
}

function detectMultiCamp(c: Cluster): Cand[] {
  const text = `${c.title} ${c.summary ?? ""}`;
  return CANDS.filter((n) => text.includes(n));
}

function hasSupport(c: Cluster): boolean {
  const text = `${c.title} ${c.summary ?? ""}`;
  return SUPPORT_KW.some((kw) => text.includes(kw));
}

function extractMPNames(text: string): string[] {
  const re = /([가-힣]{2,4})\s*(의원|전의원|前의원|국회의원)/g;
  const found: string[] = [];
  let m;
  while ((m = re.exec(text)) !== null) {
    const name = m[1];
    if (!CANDS.includes(name as Cand) && !NON_MINJU.has(name)) found.push(name);
  }
  return [...new Set(found)];
}

// ── 날짜 유틸 ────────────────────────────────────────────────
function clusterDate(c: Cluster): Date {
  const ts = (c as any).publishedAt ?? (c as any).createdAt ?? (c as any).updatedAt;
  if (!ts) return new Date(0);
  if (ts?.toDate) return ts.toDate();
  return new Date(ts);
}

// ── 하위 컴포넌트 ────────────────────────────────────────────
function Tag({ label, soft }: { label: string; soft?: boolean }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
      soft ? "bg-gray-100 text-gray-400 italic" : "bg-white border border-gray-200 text-gray-700"
    }`}>
      {label}
    </span>
  );
}

function TrendBadge({ diff }: { diff: number }) {
  if (diff === 0) return <span className="text-xs text-gray-400">±0</span>;
  const up = diff > 0;
  return (
    <span className={`text-xs font-bold ${up ? "text-[#00A86B]" : "text-[#E53935]"}`}>
      {up ? "▲" : "▼"}{Math.abs(diff)}
    </span>
  );
}

function CampCard({ cand, clusters, thisWeekMap, lastWeekMap }: {
  cand: Cand;
  clusters: Cluster[];
  thisWeekMap: Record<string, number>;
  lastWeekMap: Record<string, number>;
}) {
  const col = C[cand];
  const [expanded, setExpanded] = useState(false);

  const campClusters = useMemo(
    () => clusters.filter((c) => detectCamp(c) === cand),
    [clusters, cand]
  );

  const supportClusters = useMemo(
    () => campClusters.filter(hasSupport).slice(0, 3),
    [campClusters]
  );

  const autoMP = useMemo(() => {
    const known = new Set(KNOWN[cand].의원);
    const names = new Set<string>();
    campClusters.forEach((c) => {
      extractMPNames(`${c.title} ${c.summary ?? ""}`).forEach((n) => {
        if (!known.has(n)) names.add(n);
      });
    });
    return [...names].slice(0, 6);
  }, [campClusters, cand]);

  const thisW = thisWeekMap[cand] ?? 0;
  const lastW = lastWeekMap[cand] ?? 0;
  const diff  = thisW - lastW;
  const known = KNOWN[cand];
  const displayClusters = expanded ? campClusters.slice(0, 10) : campClusters.slice(0, 3);

  return (
    <div className={`rounded-2xl border-2 ${col.border} bg-white overflow-hidden shadow-sm`}>
      <div className={`px-5 py-3 ${col.light} border-b ${col.border}`}>
        <div className="flex items-center justify-between">
          <h2 className={`text-base font-black ${col.text}`}>{cand} 진영</h2>
          <div className="flex items-center gap-2">
            <TrendBadge diff={diff} />
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${col.badge}`}>
              {campClusters.length}건
            </span>
          </div>
        </div>
        <div className="mt-0.5 text-[11px] text-gray-500">
          이번주 {thisW}건 · 지난주 {lastW}건
        </div>
      </div>

      <div className="p-4 space-y-3">
        <div className="space-y-2.5">
          {known.의원.length > 0 && (
            <div>
              <div className="text-[11px] font-bold text-gray-400 mb-1.5">🏛 확인된 지지 의원</div>
              <div className="flex flex-wrap gap-1">
                {known.의원.map((n) => <Tag key={n} label={n} />)}
                {autoMP.map((n) => <Tag key={n} label={n} soft />)}
              </div>
            </div>
          )}

          {known.유튜버.length > 0 && (
            <div>
              <div className="text-[11px] font-bold text-gray-400 mb-1.5">📺 유튜버·미디어</div>
              <div className="flex flex-wrap gap-1">
                {known.유튜버.map((n) => <Tag key={n} label={n} />)}
              </div>
            </div>
          )}

          {known.단체.length > 0 && (
            <div>
              <div className="text-[11px] font-bold text-gray-400 mb-1.5">🤝 단체·세력</div>
              <div className="flex flex-wrap gap-1">
                {known.단체.map((n) => <Tag key={n} label={n} />)}
              </div>
            </div>
          )}
        </div>

        {supportClusters.length > 0 && (
          <div>
            <div className="text-[11px] font-bold text-[#005BAC] mb-1.5">⚡ 최근 지지 동향</div>
            <div className="space-y-1">
              {supportClusters.map((c) => (
                <a
                  key={c.id}
                  href={`/clusters/${c.id}`}
                  className="block rounded-lg bg-blue-50 border border-blue-100 px-3 py-2 text-xs text-gray-700 hover:bg-blue-100 transition line-clamp-2"
                >
                  {c.title}
                </a>
              ))}
            </div>
          </div>
        )}

        {campClusters.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <div className="text-[11px] font-bold text-gray-400">📌 관련 이슈</div>
              {campClusters.length > 3 && (
                <button
                  onClick={() => setExpanded(!expanded)}
                  className="text-[11px] text-[#005BAC] hover:underline"
                >
                  {expanded ? "접기" : `+${campClusters.length - 3}건 더보기`}
                </button>
              )}
            </div>
            <div className="space-y-1">
              {displayClusters.map((c) => (
                <a
                  key={c.id}
                  href={`/clusters/${c.id}`}
                  className="block rounded-lg bg-gray-50 border border-gray-100 px-3 py-2 text-xs text-gray-600 hover:bg-gray-100 transition line-clamp-1"
                >
                  {c.title}
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── 합종연횡 시그널 ───────────────────────────────────────────
function AllianceSignal({ clusters }: { clusters: Cluster[] }) {
  const signals = useMemo(() => {
    return clusters
      .map((c) => ({ c, camps: detectMultiCamp(c) }))
      .filter(({ camps }) => camps.length >= 2)
      .slice(0, 8);
  }, [clusters]);

  if (!signals.length) return null;

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
      <div className="text-sm font-bold text-amber-800 mb-3">⚡ 합종연횡·갈등 시그널</div>
      <div className="space-y-2">
        {signals.map(({ c, camps }) => (
          <a
            key={c.id}
            href={`/clusters/${c.id}`}
            className="flex items-start gap-2 rounded-lg bg-white border border-amber-100 px-3 py-2 hover:bg-amber-50 transition"
          >
            <div className="flex gap-1 mt-0.5 shrink-0">
              {camps.map((cand) => (
                <span key={cand} className={`inline-block w-1.5 h-4 rounded-full ${C[cand].bar}`} />
              ))}
            </div>
            <span className="text-xs text-gray-700 line-clamp-2">{c.title}</span>
          </a>
        ))}
      </div>
    </div>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────────
export default function Allies() {
  const { data, loading } = useClusters();
  const [view, setView] = useState<"main" | "all">("main");

  const now = useMemo(() => new Date(), []);
  const weekAgo     = useMemo(() => new Date(now.getTime() - 7 * 86400000), [now]);
  const twoWeekAgo  = useMemo(() => new Date(now.getTime() - 14 * 86400000), [now]);

  const { counts, thisWeekMap, lastWeekMap } = useMemo(() => {
    const counts: Record<string, number> = {};
    const thisWeekMap: Record<string, number> = {};
    const lastWeekMap: Record<string, number> = {};
    for (const c of data) {
      const camp = detectCamp(c);
      if (!camp) continue;
      counts[camp] = (counts[camp] ?? 0) + 1;
      const d = clusterDate(c);
      if (d >= weekAgo) thisWeekMap[camp] = (thisWeekMap[camp] ?? 0) + 1;
      else if (d >= twoWeekAgo) lastWeekMap[camp] = (lastWeekMap[camp] ?? 0) + 1;
    }
    return { counts, thisWeekMap, lastWeekMap };
  }, [data, weekAgo, twoWeekAgo]);

  const total = Object.values(counts).reduce((s, v) => s + v, 0) || 1;
  const main2: Cand[] = ["김민석", "정청래"];
  const sub2:  Cand[] = ["송영길", "김용민"];

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">세력지도</h1>
          <p className="mt-0.5 text-sm text-gray-500">후보별 지지 세력 · 주간 트렌드 · 연대 신호</p>
        </div>
        <div className="flex gap-1 text-xs">
          <button
            onClick={() => setView("main")}
            className={`px-3 py-1.5 rounded-lg border transition ${view === "main" ? "bg-navy text-white border-navy" : "bg-white text-gray-500 border-gray-200"}`}
          >
            2강 비교
          </button>
          <button
            onClick={() => setView("all")}
            className={`px-3 py-1.5 rounded-lg border transition ${view === "all" ? "bg-navy text-white border-navy" : "bg-white text-gray-500 border-gray-200"}`}
          >
            전체 후보
          </button>
        </div>
      </div>

      {/* 세력 판세 요약 바 */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="text-xs font-bold text-gray-500 mb-3">세력 판세 (온라인 언급 비중)</div>
        <div className="space-y-2">
          {CANDS.filter((n) => counts[n]).map((name) => {
            const pct  = Math.round(((counts[name] ?? 0) / total) * 100);
            const diff = (thisWeekMap[name] ?? 0) - (lastWeekMap[name] ?? 0);
            return (
              <div key={name} className="flex items-center gap-3">
                <span className={`w-14 shrink-0 text-right text-xs font-bold ${C[name].text}`}>{name}</span>
                <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                  <div
                    className={`h-4 rounded-full ${C[name].bar} transition-all duration-700`}
                    style={{ width: `${Math.max(pct, 1)}%` }}
                  />
                </div>
                <span className="w-8 shrink-0 text-right">
                  <TrendBadge diff={diff} />
                </span>
                <span className="w-20 shrink-0 text-xs text-gray-400 text-right">{counts[name]}건 ({pct}%)</span>
              </div>
            );
          })}
        </div>
        <div className="mt-2 text-[11px] text-gray-400">▲▼ 이번주 vs 지난주 증감</div>
      </div>

      {loading ? (
        <p className="py-12 text-center text-gray-400">불러오는 중…</p>
      ) : (
        <>
          {view === "main" ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {main2.map((c) => (
                  <CampCard key={c} cand={c} clusters={data} thisWeekMap={thisWeekMap} lastWeekMap={lastWeekMap} />
                ))}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {sub2.map((c) => (
                  <CampCard key={c} cand={c} clusters={data} thisWeekMap={thisWeekMap} lastWeekMap={lastWeekMap} />
                ))}
              </div>
            </>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {CANDS.map((c) => (
                <CampCard key={c} cand={c} clusters={data} thisWeekMap={thisWeekMap} lastWeekMap={lastWeekMap} />
              ))}
            </div>
          )}

          <AllianceSignal clusters={data} />
        </>
      )}

      <p className="text-xs text-gray-400">
        * 흰 배지: 확인된 지지 인사 / 회색 이탤릭: 클러스터 자동 추출 (미확인) / ⚡ 지지 키워드 감지
      </p>
    </div>
  );
}
