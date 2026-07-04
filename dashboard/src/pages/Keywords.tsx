import { useMemo } from "react";
import { useKeywordTrend } from "../lib/data";
import { ALL_CANDIDATE_NAMES } from "../lib/candidates";

// ── 불용어 목록 (UI 필터) ──────────────────────────────────────
const STOPWORDS = new Set([
  // 도메인
  "v.daum", "daum.net", "naver.com", "youtube.com", "youtu.be", "t.co", "bit.ly",
  // 관용어·부사
  "오찬", "우려", "끝에", "안팎", "앞두고", "관련", "밝혔다", "말했다", "전했다", "강조했다",
  "단독", "속보", "긴급", "입장", "발표", "진행", "예정", "관련해", "대해", "에서", "통해",
  "위해", "으로", "에서", "까지", "부터", "가운데", "한편", "이에", "이날", "이번", "오는",
  "지난", "같은", "아직", "모두", "매우", "이후", "이전", "또한", "따라", "바로", "다시",
  // 조사·접속사 (한 글자 또는 무의미)
  "은", "는", "이", "가", "을", "를", "과", "와", "의", "에", "서", "도", "만", "로",
  // 기타 무의미어
  "등", "및", "것", "수", "그", "한", "더", "두", "많은", "없이", "없는", "없다", "있다",
  "했다", "됐다", "됩니다", "합니다", "됩니", "말했", "밝혔", "했습", "대통령",
]);

// 한 글자 키워드 제외 함수
function isStopword(word: string): boolean {
  if (word.length <= 1) return true;
  if (STOPWORDS.has(word)) return true;
  if (word.includes(".") && word.includes("/")) return true; // URL 패턴
  if (/^https?/.test(word)) return true;
  return false;
}

// ── 가중치 키워드 (전당대회 관련) ─────────────────────────────
const WEIGHTED_KEYWORDS: Record<string, string> = {
  // 전당대회 핵심
  전당대회: "core", 당대표: "core", 최고위원: "core", 권리당원: "core",
  전국당원대회: "core", 예비경선: "core", 컷오프: "core", 결선투표: "core",
  지도부: "core", 당권: "core", 출마: "core", 지지선언: "core", 시도당: "core",
  지역위원장: "core",
  // 후보별 (candidates.ts에서 자동 생성)
  ...Object.fromEntries(ALL_CANDIDATE_NAMES.map((n) => [n, "candidate"])),
  // 프레임
  책임론: "frame", 쇄신론: "frame", 통합론: "frame", 안정론: "frame", 개혁론: "frame",
  검찰개혁: "frame", 강성당원: "frame", 친명: "frame", 비명: "frame", 반명: "frame",
  당정일체: "frame", 당정관계: "frame", 관리형: "frame", 확장성: "frame",
  실용: "frame", 개혁강성: "frame", 친명주류비판: "frame",
  지방선거책임: "frame",
};

const CATEGORY_META: Record<string, { label: string; color: string; bg: string }> = {
  core:      { label: "전당대회 핵심", color: "text-brand",         bg: "bg-brand/10 border border-brand/20" },
  candidate: { label: "후보별",        color: "text-green-accent",   bg: "bg-green-accent/10 border border-green-accent/20" },
  frame:     { label: "프레임",        color: "text-purple-accent",  bg: "bg-purple-accent/10 border border-purple-accent/20" },
  other:     { label: "기타",          color: "text-gray-600",       bg: "bg-gray-50 border border-gray-200" },
};

type KwItem = { word: string; count: number; category: string };

export default function Keywords() {
  const { data, loading } = useKeywordTrend();
  const rawTop = data[0]?.top ?? [];
  const date = data[0]?.date ?? "";

  const filtered: KwItem[] = useMemo(() => {
    return rawTop
      .filter((t) => !isStopword(t.word))
      .map((t) => ({
        word: t.word,
        count: t.count,
        category: WEIGHTED_KEYWORDS[t.word] ?? "other",
      }));
  }, [rawTop]);

  const byCat = useMemo(() => {
    const groups: Record<string, KwItem[]> = { core: [], candidate: [], frame: [], other: [] };
    for (const kw of filtered) {
      groups[kw.category].push(kw);
    }
    return groups;
  }, [filtered]);

  const maxCount = filtered.reduce((m, t) => Math.max(m, t.count), 1);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-gray-900">키워드 레이더</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          전당대회 전용 키워드 동향 — 불용어·도메인 제거 후 범주별 분류
          {date && <span className="ml-2 text-gray-400">({date} 기준)</span>}
        </p>
      </div>

      {loading ? (
        <p className="py-12 text-center text-gray-400">불러오는 중…</p>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-200 bg-white p-8 text-center">
          <p className="text-gray-400">아직 키워드 데이터가 없습니다.</p>
          <p className="text-xs text-gray-300 mt-1">파이프라인 실행 후 자동 생성됩니다.</p>
        </div>
      ) : (
        <>
          {/* 범주별 섹션 */}
          {(["core", "candidate", "frame", "other"] as const)
            .filter((cat) => byCat[cat].length > 0)
            .map((cat) => {
              const meta = CATEGORY_META[cat];
              const items = byCat[cat].slice(0, cat === "other" ? 10 : 20);
              return (
                <div key={cat} className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
                  <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${meta.bg} ${meta.color}`}>
                      {meta.label}
                    </span>
                    <span className="text-xs text-gray-400">{byCat[cat].length}개</span>
                  </div>
                  <div className="p-4 space-y-2">
                    {items.map((t, i) => (
                      <div key={t.word} className="flex items-center gap-3">
                        <span className="w-5 shrink-0 text-right text-xs font-bold text-gray-300">
                          {i + 1}
                        </span>
                        <span className={`w-24 shrink-0 text-sm font-semibold ${meta.color}`}>
                          {t.word}
                        </span>
                        <div className="flex-1 h-4 rounded-full bg-gray-100 overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{
                              width: `${Math.max((t.count / maxCount) * 100, 3)}%`,
                              backgroundColor:
                                cat === "core" ? "#005BAC"
                                : cat === "candidate" ? "#00A86B"
                                : cat === "frame" ? "#6D5DF6"
                                : "#9ca3af",
                            }}
                          />
                        </div>
                        <span className="w-10 shrink-0 text-right text-xs font-semibold text-gray-500">
                          {t.count}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}

          {/* 제거된 키워드 안내 */}
          <div className="rounded-lg border border-dashed border-gray-200 p-3 text-xs text-gray-400 text-center">
            불용어·도메인·무의미어 {rawTop.length - filtered.length}개 자동 필터링됨
          </div>
        </>
      )}
    </div>
  );
}
