import { useMemo, useState } from "react";
import { useClusters } from "../lib/data";
import type { Cluster } from "../types";
import { CANDIDATE_STYLES, MAIN_CANDIDATE_NAMES } from "../lib/candidates";

// ── 후보 색상 ─────────────────────────────────────────────────
const C = CANDIDATE_STYLES;
type Cand = string;
const CANDS: Cand[] = MAIN_CANDIDATE_NAMES;

// ── 알려진 지지 세력 ──────────────────────────────────────────
const KNOWN: Record<string, { 의원: string[]; 유튜버: string[]; 단체: string[] }> = {
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
    의원:  ["설훈", "이상민"],
    유튜버: ["열린공감TV", "참세상"],
    단체:  ["송영길지지모임"],
  },
  고민정: {
    의원:  [],
    유튜버: [],
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

function clusterDate(c: Cluster): Date {
  const ts = (c as any).publishedAt ?? (c as any).createdAt ?? (c as any).updatedAt;
  if (!ts) return new Date(0);
  if (ts?.toDate) return ts.toDate();
  return new Date(ts);
}

// ── 마인드맵 노드 정의 ────────────────────────────────────────
type NodeKey = "지지의원" | "우호가능" | "미디어" | "단체" | "지지동향" | "합종연횡" | "관련이슈" | "확인필요";

const NODE_META: { key: NodeKey; label: string; icon: string; angle: number }[] = [
  { key: "지지의원",  label: "확인된 지지 의원", icon: "🏛",  angle: 270 },
  { key: "우호가능",  label: "우호 가능 인물",   icon: "🤝",  angle: 315 },
  { key: "미디어",    label: "유튜버·미디어",    icon: "📺",  angle: 0   },
  { key: "단체",      label: "단체·세력",        icon: "🏢",  angle: 45  },
  { key: "지지동향",  label: "최근 지지 동향",   icon: "⚡",  angle: 90  },
  { key: "합종연횡",  label: "합종연횡 시그널",  icon: "🔀",  angle: 135 },
  { key: "관련이슈",  label: "관련 이슈",        icon: "📌",  angle: 180 },
  { key: "확인필요",  label: "확인 필요",        icon: "❓",  angle: 225 },
];

// SVG 좌표 (viewBox 0 0 400 340, 중앙 200,165, 반지름 120)
const CX = 200, CY = 165, R = 118;
function polar(angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: CX + R * Math.sin(rad), y: CY - R * Math.cos(rad) };
}

// 선 스타일
const LINE_STYLE: Record<NodeKey, { stroke: string; dash: string }> = {
  지지의원:  { stroke: "#374151", dash: ""          },
  우호가능:  { stroke: "#6b7280", dash: ""          },
  미디어:    { stroke: "#374151", dash: ""          },
  단체:      { stroke: "#374151", dash: ""          },
  지지동향:  { stroke: "#3b82f6", dash: "6,3"       },
  합종연횡:  { stroke: "#f59e0b", dash: "4,4"       },
  관련이슈:  { stroke: "#9ca3af", dash: ""          },
  확인필요:  { stroke: "#f59e0b", dash: "3,3"       },
};

// ── 마인드맵 SVG ─────────────────────────────────────────────
function MindmapSVG({
  cand,
  nodeCounts,
  selected,
  onSelect,
}: {
  cand: Cand;
  nodeCounts: Record<NodeKey, number>;
  selected: NodeKey | null;
  onSelect: (k: NodeKey) => void;
}) {
  const hex = C[cand].hex;

  return (
    <svg
      viewBox="0 0 400 330"
      className="w-full"
      style={{ maxHeight: 280 }}
    >
      {/* 관계선 */}
      {NODE_META.map(({ key, angle }) => {
        const { x, y } = polar(angle);
        const ls = LINE_STYLE[key];
        return (
          <line
            key={key}
            x1={CX} y1={CY}
            x2={x}  y2={y}
            stroke={ls.stroke}
            strokeWidth={selected === key ? 2 : 1}
            strokeDasharray={ls.dash}
            opacity={selected && selected !== key ? 0.25 : 0.7}
          />
        );
      })}

      {/* 중앙 후보 노드 */}
      <circle cx={CX} cy={CY} r={32} fill={hex} opacity={0.12} />
      <circle cx={CX} cy={CY} r={30} fill="white" stroke={hex} strokeWidth={2} />
      <text x={CX} y={CY - 5} textAnchor="middle" fontSize={13} fontWeight="bold" fill={hex}>
        {cand}
      </text>
      <text x={CX} y={CY + 11} textAnchor="middle" fontSize={9} fill="#6b7280">
        후보
      </text>

      {/* 주변 노드 */}
      {NODE_META.map(({ key, label, icon, angle }) => {
        const { x, y } = polar(angle);
        const count = nodeCounts[key] ?? 0;
        const isSelected = selected === key;
        const hasData = count > 0;

        return (
          <g
            key={key}
            onClick={() => onSelect(key)}
            style={{ cursor: "pointer" }}
          >
            <circle
              cx={x} cy={y} r={26}
              fill={isSelected ? hex : "white"}
              fillOpacity={isSelected ? 0.15 : 1}
              stroke={isSelected ? hex : hasData ? "#d1d5db" : "#e5e7eb"}
              strokeWidth={isSelected ? 2 : 1}
            />
            {/* 아이콘 */}
            <text x={x} y={y - 6} textAnchor="middle" fontSize={12}>
              {icon}
            </text>
            {/* 카운트 뱃지 */}
            {hasData && (
              <>
                <circle cx={x + 18} cy={y - 18} r={9} fill={hex} />
                <text x={x + 18} y={y - 14} textAnchor="middle" fontSize={8} fill="white" fontWeight="bold">
                  {count > 9 ? "9+" : count}
                </text>
              </>
            )}
            {/* 라벨 */}
            <text x={x} y={y + 8} textAnchor="middle" fontSize={7.5} fill={isSelected ? hex : "#374151"} fontWeight={isSelected ? "bold" : "normal"}>
              {label.length > 6 ? label.slice(0, 6) + "…" : label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ── 노드 상세 패널 ────────────────────────────────────────────
function NodeDetail({
  nodeKey,
  cand,
  known,
  autoMP,
  supportClusters,
  campClusters,
  allianceClusters,
  needsReviewItems,
}: {
  nodeKey: NodeKey;
  cand: Cand;
  known: { 의원: string[]; 유튜버: string[]; 단체: string[] };
  autoMP: string[];
  supportClusters: Cluster[];
  campClusters: Cluster[];
  allianceClusters: Cluster[];
  needsReviewItems: string[];
}) {
  const col = C[cand];

  const renderClusters = (list: Cluster[], limit = 5) => (
    <div className="space-y-1">
      {list.slice(0, limit).map((c) => (
        <a
          key={c.id}
          href={`/clusters/${c.id}`}
          className="block rounded-lg bg-gray-50 border border-gray-100 px-3 py-2 text-xs text-gray-700 hover:bg-gray-100 transition line-clamp-2"
        >
          {c.title}
        </a>
      ))}
      {list.length > limit && (
        <p className="text-xs text-gray-400 pl-1">+{list.length - limit}건 더 있음</p>
      )}
    </div>
  );

  const renderTags = (items: string[], badge?: string) => (
    <div className="flex flex-wrap gap-1">
      {items.map((n) => (
        <span key={n} className={`rounded px-2 py-0.5 text-xs font-medium border ${badge ?? "bg-white border-gray-200 text-gray-700"}`}>
          {n}
        </span>
      ))}
    </div>
  );

  switch (nodeKey) {
    case "지지의원":
      return (
        <div className="space-y-2">
          <div className="text-xs font-bold text-gray-500">확인된 지지 의원</div>
          {renderTags(known.의원, `${col.badge}`)}
          {autoMP.length > 0 && (
            <>
              <div className="text-[11px] text-gray-400">클러스터 자동 추출 (미확인)</div>
              {renderTags(autoMP, "bg-gray-50 border-gray-200 text-gray-500 italic")}
            </>
          )}
        </div>
      );
    case "우호가능":
      return (
        <div className="space-y-2">
          <div className="text-xs font-bold text-gray-500">우호 가능 인물 — 시그널 감지, 확정 지지 아님</div>
          {autoMP.length > 0
            ? renderTags(autoMP, "bg-yellow-50 border-yellow-200 text-yellow-700")
            : <p className="text-xs text-gray-400">탐지된 우호 가능 인물 없음</p>}
        </div>
      );
    case "미디어":
      return (
        <div className="space-y-2">
          <div className="text-xs font-bold text-gray-500">유튜버·미디어</div>
          {renderTags(known.유튜버, `${col.badge}`)}
        </div>
      );
    case "단체":
      return (
        <div className="space-y-2">
          <div className="text-xs font-bold text-gray-500">단체·세력</div>
          {known.단체.length > 0
            ? renderTags(known.단체, `${col.badge}`)
            : <p className="text-xs text-gray-400">등록된 단체 없음</p>}
        </div>
      );
    case "지지동향":
      return (
        <div className="space-y-2">
          <div className="text-xs font-bold text-gray-500">최근 지지 동향 — 시그널 감지 (확정 지지 아님)</div>
          {supportClusters.length > 0
            ? renderClusters(supportClusters)
            : <p className="text-xs text-gray-400">탐지된 지지 시그널 없음</p>}
        </div>
      );
    case "합종연횡":
      return (
        <div className="space-y-2">
          <div className="text-xs font-bold text-gray-500">합종연횡 시그널 — 2인 이상 동시 언급</div>
          {allianceClusters.length > 0
            ? renderClusters(allianceClusters)
            : <p className="text-xs text-gray-400">탐지된 합종연횡 시그널 없음</p>}
        </div>
      );
    case "관련이슈":
      return (
        <div className="space-y-2">
          <div className="text-xs font-bold text-gray-500">관련 이슈 ({campClusters.length}건)</div>
          {renderClusters(campClusters, 8)}
        </div>
      );
    case "확인필요":
      return (
        <div className="space-y-2">
          <div className="text-xs font-bold text-gray-500">확인 필요 — 검증 대기 항목</div>
          {needsReviewItems.length > 0
            ? renderTags(needsReviewItems, "bg-yellow-50 border-yellow-200 text-yellow-700")
            : <p className="text-xs text-gray-400">확인 필요 항목 없음</p>}
        </div>
      );
  }
}

// ── CampCard (마인드맵) ───────────────────────────────────────
function CampCard({ cand, clusters, thisWeekMap, lastWeekMap }: {
  cand: Cand;
  clusters: Cluster[];
  thisWeekMap: Record<string, number>;
  lastWeekMap: Record<string, number>;
}) {
  const col = C[cand];
  const [selectedNode, setSelectedNode] = useState<NodeKey | null>(null);

  const campClusters = useMemo(
    () => clusters.filter((c) => detectCamp(c) === cand),
    [clusters, cand]
  );
  const supportClusters = useMemo(() => campClusters.filter(hasSupport), [campClusters]);
  const allianceClusters = useMemo(
    () => clusters.filter((c) => detectMultiCamp(c).includes(cand) && detectMultiCamp(c).length >= 2),
    [clusters, cand]
  );

  const known = KNOWN[cand];
  const autoMP = useMemo(() => {
    const knownSet = new Set(known.의원);
    const names = new Set<string>();
    campClusters.forEach((c) => {
      extractMPNames(`${c.title} ${c.summary ?? ""}`).forEach((n) => {
        if (!knownSet.has(n)) names.add(n);
      });
    });
    return [...names].slice(0, 8);
  }, [campClusters, known.의원]);

  const needsReviewItems = useMemo(() => {
    return autoMP.filter((n) => !known.의원.includes(n));
  }, [autoMP, known.의원]);

  const nodeCounts: Record<NodeKey, number> = {
    지지의원:  known.의원.length + autoMP.length,
    우호가능:  autoMP.length,
    미디어:    known.유튜버.length,
    단체:      known.단체.length,
    지지동향:  supportClusters.length,
    합종연횡:  allianceClusters.length,
    관련이슈:  campClusters.length,
    확인필요:  needsReviewItems.length,
  };

  const thisW = thisWeekMap[cand] ?? 0;
  const lastW = lastWeekMap[cand] ?? 0;
  const diff = thisW - lastW;

  function handleSelect(key: NodeKey) {
    setSelectedNode((prev) => (prev === key ? null : key));
  }

  return (
    <div className={`rounded-2xl border-2 ${col.border} bg-white overflow-hidden shadow-sm`}>
      {/* 카드 헤더 */}
      <div className={`px-5 py-3 ${col.light} border-b ${col.border}`}>
        <div className="flex items-center justify-between">
          <h2 className={`text-base font-black ${col.text}`}>{cand} 진영</h2>
          <div className="flex items-center gap-2">
            {diff !== 0 && (
              <span className={`text-xs font-bold ${diff > 0 ? "text-[#00A86B]" : "text-[#E53935]"}`}>
                {diff > 0 ? "▲" : "▼"}{Math.abs(diff)}
              </span>
            )}
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${col.badge}`}>
              {campClusters.length}건
            </span>
          </div>
        </div>
        <div className="mt-0.5 text-[11px] text-gray-500">
          이번주 {thisW}건 · 지난주 {lastW}건
          {diff > 0 && <span className="ml-1 text-[#00A86B]">상승세</span>}
        </div>
      </div>

      {/* 마인드맵 SVG */}
      <div className="px-3 pt-3">
        <MindmapSVG
          cand={cand}
          nodeCounts={nodeCounts}
          selected={selectedNode}
          onSelect={handleSelect}
        />
      </div>

      {/* 노드 클릭 상세 패널 */}
      {selectedNode && (
        <div className="mx-3 mb-3 rounded-xl border border-gray-200 bg-gray-50 p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-gray-600">
              {NODE_META.find((n) => n.key === selectedNode)?.icon}{" "}
              {NODE_META.find((n) => n.key === selectedNode)?.label}
            </span>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              ✕ 닫기
            </button>
          </div>
          <NodeDetail
            nodeKey={selectedNode}
            cand={cand}
            known={known}
            autoMP={autoMP}
            supportClusters={supportClusters}
            campClusters={campClusters}
            allianceClusters={allianceClusters}
            needsReviewItems={needsReviewItems}
          />
        </div>
      )}
    </div>
  );
}

// ── TrendBadge ────────────────────────────────────────────────
function TrendBadge({ diff }: { diff: number }) {
  if (diff === 0) return <span className="text-xs text-gray-400">±0</span>;
  const up = diff > 0;
  return (
    <span className={`text-xs font-bold ${up ? "text-[#00A86B]" : "text-[#E53935]"}`}>
      {up ? "▲" : "▼"}{Math.abs(diff)}
    </span>
  );
}

// ── 합종연횡 시그널 패널 ──────────────────────────────────────
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
          <a key={c.id} href={`/clusters/${c.id}`}
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

// ── 메인 ─────────────────────────────────────────────────────
export default function Allies() {
  const { data, loading } = useClusters();
  const [view, setView] = useState<"main" | "all">("main");

  const now = useMemo(() => new Date(), []);
  const weekAgo    = useMemo(() => new Date(now.getTime() - 7 * 86400000), [now]);
  const twoWeekAgo = useMemo(() => new Date(now.getTime() - 14 * 86400000), [now]);

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
  const displayCands: Cand[] = view === "main" ? CANDS : CANDS;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">세력지도</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            후보 중심 관계도 — 확정 관계도가 아닌 세력 시그널 지도
          </p>
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

      {/* 세력 판세 바 */}
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
                  <div className={`h-4 rounded-full ${C[name].bar} transition-all duration-700`}
                    style={{ width: `${Math.max(pct, 1)}%` }} />
                </div>
                <span className="w-8 shrink-0 text-right"><TrendBadge diff={diff} /></span>
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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {displayCands.map((c) => (
              <CampCard key={c} cand={c} clusters={data}
                thisWeekMap={thisWeekMap} lastWeekMap={lastWeekMap} />
            ))}
          </div>
          <AllianceSignal clusters={data} />
        </>
      )}

      <p className="text-xs text-gray-400">
        * 노드를 클릭하면 상세 내용을 확인할 수 있습니다.
        숫자 뱃지 = 해당 항목 수. 시그널 감지는 확정 지지가 아닙니다.
      </p>
    </div>
  );
}
