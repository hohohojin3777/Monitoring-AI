import { useMemo, useState } from "react";
import { useClusters } from "../lib/data";
import type { Cluster } from "../types";

// ── 후보 색상 ────────────────────────────────────────────────
const C = {
  김민석: { bg: "bg-emerald-50", border: "border-emerald-500", text: "text-emerald-700", bar: "bg-emerald-500", badge: "bg-emerald-100 text-emerald-700" },
  정청래: { bg: "bg-red-50",     border: "border-red-500",     text: "text-red-700",     bar: "bg-red-500",     badge: "bg-red-100 text-red-700" },
  송영길: { bg: "bg-orange-50",  border: "border-orange-500",  text: "text-orange-700",  bar: "bg-orange-500",  badge: "bg-orange-100 text-orange-700" },
  김용민: { bg: "bg-violet-50",  border: "border-violet-500",  text: "text-violet-700",  bar: "bg-violet-500",  badge: "bg-violet-100 text-violet-700" },
} as const;
type Cand = keyof typeof C;
const CANDS: Cand[] = ["김민석", "정청래", "송영길", "김용민"];

// ── 알려진 지지 세력 (수동 큐레이션 + 클러스터 자동 보강) ─────
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

// ── 클러스터에서 지지 후보 추출 ──────────────────────────────
const SUPPORT_KW = ["지지", "편", "지원", "응원", "찍겠", "뽑겠", "밀어", "찍자", "당대표로", "후보로", "원팀", "연대"];
const OPPOSE_KW  = ["반대", "비판", "낙선", "사퇴", "탈락"];

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
  // 반대 표현 붙은 후보 제외
  const safe = mentioned.filter((n) => {
    const idx = text.indexOf(n);
    const nearby = text.slice(Math.max(0, idx - 5), idx + 12);
    return !OPPOSE_KW.some((k) => nearby.includes(k));
  });
  return safe.length === 1 ? safe[0] : null;
}

// 민주당이 아닌 인물 — 자동 추출에서 제외
const NON_MINJU = new Set([
  "한동훈", "이준석", "안철수", "윤석열", "오세훈", "홍준표", "원희룡", "나경원",
  "황교안", "유승민", "김기현", "이재오", "권성동", "주호영", "국민의힘", "개혁신당",
]);

// 클러스터에서 자동으로 인물/단체 추출
function extractEntities(clusters: Cluster[], camp: Cand): { 의원: string[]; 유튜버: string[]; 기타: string[] } {
  const 의원Set = new Set<string>();
  const 유튜버Set = new Set<string>();
  const 기타Set = new Set<string>();

  // 알려진 의원 이름 패턴 (2~3글자 한국 이름)
  const 의원Keywords = ["의원", "前의원", "전의원", "국회의원"];
  const 유튜버Keywords = ["TV", "tv", "채널", "유튜브", "방송", "쇼"];

  for (const c of clusters) {
    if (detectCamp(c) !== camp) continue;
    const text = `${c.title} ${c.summary ?? ""}`;
    // 의원 추출
    의원Keywords.forEach((kw) => {
      const re = new RegExp(`([가-힣]{2,4})\\s*${kw}`, "g");
      let m;
      while ((m = re.exec(text)) !== null) {
        const name = m[1];
        if (!CANDS.includes(name as Cand) && name.length >= 2 && !NON_MINJU.has(name)) 의원Set.add(name);
      }
    });
    // 유튜버/채널 추출
    유튜버Keywords.forEach((kw) => {
      const re = new RegExp(`([가-힣a-zA-Z]{2,10})${kw}`, "gi");
      let m;
      while ((m = re.exec(text)) !== null) {
        유튜버Set.add(m[0]);
      }
    });
  }
  // known 항목 제외 (이미 표시됨)
  const knownAll = new Set([...KNOWN[camp].의원, ...KNOWN[camp].유튜버, ...KNOWN[camp].단체]);
  return {
    의원:   [...의원Set].filter((n) => !knownAll.has(n)).slice(0, 8),
    유튜버:  [...유튜버Set].filter((n) => !knownAll.has(n)).slice(0, 6),
    기타:   [...기타Set].slice(0, 4),
  };
}

// ── 하위 컴포넌트 ────────────────────────────────────────────
function Tag({ label, soft }: { label: string; soft?: boolean }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${soft ? "bg-gray-100 text-gray-500" : "bg-white border border-gray-200 text-gray-700"}`}>
      {label}
    </span>
  );
}

function CampCard({ cand, clusters }: { cand: Cand; clusters: Cluster[] }) {
  const col = C[cand];
  const campClusters = useMemo(() => clusters.filter((c) => detectCamp(c) === cand).slice(0, 5), [clusters, cand]);
  const auto = useMemo(() => extractEntities(clusters, cand), [clusters, cand]);
  const known = KNOWN[cand];
  const total = clusters.filter((c) => detectCamp(c) === cand).length;

  return (
    <div className={`rounded-2xl border-2 ${col.border} ${col.bg} overflow-hidden`}>
      {/* 헤더 */}
      <div className={`px-5 py-4 border-b-2 ${col.border} bg-white/60`}>
        <div className="flex items-center justify-between">
          <h2 className={`text-lg font-black ${col.text}`}>{cand} 진영</h2>
          <span className={`rounded-full px-3 py-1 text-xs font-bold ${col.badge}`}>
            언급 {total}건
          </span>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* 지지 세력 분류 */}
        <div className="space-y-3">
          {/* 국회의원 */}
          {(known.의원.length > 0 || auto.의원.length > 0) && (
            <div>
              <div className="text-xs font-bold text-gray-500 mb-1.5">🏛 국회의원</div>
              <div className="flex flex-wrap gap-1.5">
                {known.의원.map((n) => <Tag key={n} label={n} />)}
                {auto.의원.map((n) => <Tag key={n} label={n} soft />)}
              </div>
            </div>
          )}

          {/* 유튜버/미디어 */}
          {(known.유튜버.length > 0 || auto.유튜버.length > 0) && (
            <div>
              <div className="text-xs font-bold text-gray-500 mb-1.5">📺 유튜버·미디어</div>
              <div className="flex flex-wrap gap-1.5">
                {known.유튜버.map((n) => <Tag key={n} label={n} />)}
                {auto.유튜버.map((n) => <Tag key={n} label={n} soft />)}
              </div>
            </div>
          )}

          {/* 단체 */}
          {known.단체.length > 0 && (
            <div>
              <div className="text-xs font-bold text-gray-500 mb-1.5">🤝 단체·세력</div>
              <div className="flex flex-wrap gap-1.5">
                {known.단체.map((n) => <Tag key={n} label={n} />)}
              </div>
            </div>
          )}
        </div>

        {/* 최근 동향 */}
        {campClusters.length > 0 && (
          <div>
            <div className="text-xs font-bold text-gray-500 mb-2">📌 최근 동향</div>
            <div className="space-y-1.5">
              {campClusters.map((c) => (
                <a
                  key={c.id}
                  href={`/clusters/${c.id}`}
                  className="block rounded-lg bg-white/70 border border-white px-3 py-2 text-xs text-gray-700 hover:bg-white transition line-clamp-2"
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

// ── 메인 페이지 ───────────────────────────────────────────────
export default function Allies() {
  const { data, loading } = useClusters();
  const [view, setView] = useState<"2col" | "4col">("2col");

  // 후보별 언급 카운트
  const counts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const c of data) {
      const camp = detectCamp(c);
      if (camp) m[camp] = (m[camp] ?? 0) + 1;
    }
    return m;
  }, [data]);

  const total = Object.values(counts).reduce((s, v) => s + v, 0) || 1;

  // 주요 2강 (김민석, 정청래)
  const main2: Cand[] = ["김민석", "정청래"];
  const sub2: Cand[] = ["송영길", "김용민"];

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">지지세력 분석</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            후보별 지지 세력 — 국회의원 · 유튜버 · 단체 분류
          </p>
        </div>
        <div className="flex gap-1 text-xs">
          <button onClick={() => setView("2col")} className={`px-3 py-1.5 rounded-lg border transition ${view === "2col" ? "bg-navy text-white border-navy" : "bg-white text-gray-500 border-gray-200"}`}>2강 비교</button>
          <button onClick={() => setView("4col")} className={`px-3 py-1.5 rounded-lg border transition ${view === "4col" ? "bg-navy text-white border-navy" : "bg-white text-gray-500 border-gray-200"}`}>전체 후보</button>
        </div>
      </div>

      {/* 언급 비중 요약 바 */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="text-xs font-bold text-gray-500 mb-3">온라인 언급 비중 (최근 수집 기준)</div>
        <div className="space-y-2">
          {CANDS.filter((n) => counts[n]).map((name) => {
            const pct = Math.round(((counts[name] ?? 0) / total) * 100);
            return (
              <div key={name} className="flex items-center gap-3">
                <span className={`w-14 shrink-0 text-right text-xs font-bold ${C[name].text}`}>{name}</span>
                <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                  <div className={`h-4 rounded-full ${C[name].bar} transition-all duration-700`} style={{ width: `${Math.max(pct, 1)}%` }} />
                </div>
                <span className="w-20 shrink-0 text-xs text-gray-500 text-right">{counts[name]}건 ({pct}%)</span>
              </div>
            );
          })}
        </div>
      </div>

      {loading ? (
        <p className="py-12 text-center text-gray-400">불러오는 중…</p>
      ) : (
        <>
          {/* 2강 비교 뷰 */}
          {view === "2col" && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {main2.map((cand) => <CampCard key={cand} cand={cand} clusters={data} />)}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {sub2.map((cand) => <CampCard key={cand} cand={cand} clusters={data} />)}
              </div>
            </>
          )}

          {/* 전체 4분할 뷰 */}
          {view === "4col" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {CANDS.map((cand) => <CampCard key={cand} cand={cand} clusters={data} />)}
            </div>
          )}
        </>
      )}

      <p className="text-xs text-gray-400">
        * 흰 배지: 확인된 지지 인사 / 회색 배지: 클러스터 자동 추출 (미확인)
      </p>
    </div>
  );
}
