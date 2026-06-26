import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useClusters } from "../lib/data";
import { Chip, GRADE_META, GradeDot, fmtDate } from "../lib/ui";
import type { Cluster, FilterTag } from "../types";

const FILTER_TABS: FilterTag[] = ["전체", "대응필요", "주의", "위기", "재발"];
const SOURCE_TABS = ["SNS", "뉴스", "커뮤니티", "영상", "전체"] as const;
type SourceTab = typeof SOURCE_TABS[number];

// SNS = X + 페이스북만
const SNS_PLATFORMS = new Set(["x", "facebook"]);
// 영상 = 유튜브 + 인스타그램 쇼츠
const VIDEO_PLATFORMS = new Set(["youtube", "instagram"]);
// 뉴스: 언론사 뉴스 플랫폼만 (커뮤니티·블로그 제외)
const NEWS_PLATFORMS = new Set(["naver_news", "google_news", "rss", "nate_news", "daum_news"]);
// 커뮤니티 (네이버카페 포함)
const COMMUNITY_PLATFORMS = new Set([
  "naver_cafe", "dcinside", "fmkorea", "clien", "ruliweb", "ppomppu",
  "mlbpark", "natepan", "todayhumor", "bobaedream", "bbadam",
]);


const PLATFORM_INFO: Record<string, { label: string; favicon: string }> = {
  naver_news:  { label: "네이버뉴스",  favicon: "https://www.google.com/s2/favicons?domain=news.naver.com&sz=16" },
  naver_blog:  { label: "네이버블로그", favicon: "https://www.google.com/s2/favicons?domain=blog.naver.com&sz=16" },
  naver_cafe:  { label: "네이버카페",  favicon: "https://www.google.com/s2/favicons?domain=cafe.naver.com&sz=16" },
  google_news: { label: "구글뉴스",   favicon: "https://www.google.com/s2/favicons?domain=news.google.com&sz=16" },
  rss:         { label: "RSS",        favicon: "https://www.google.com/s2/favicons?domain=google.com&sz=16" },
  nate_news:   { label: "네이트뉴스",  favicon: "https://www.google.com/s2/favicons?domain=news.nate.com&sz=16" },
  daum_news:   { label: "다음뉴스",   favicon: "https://www.google.com/s2/favicons?domain=news.daum.net&sz=16" },
  youtube:     { label: "유튜브",     favicon: "https://www.google.com/s2/favicons?domain=youtube.com&sz=16" },
  x:           { label: "X",          favicon: "https://www.google.com/s2/favicons?domain=x.com&sz=16" },
  instagram:   { label: "인스타그램",  favicon: "https://www.google.com/s2/favicons?domain=instagram.com&sz=16" },
  facebook:    { label: "페이스북",   favicon: "https://www.google.com/s2/favicons?domain=facebook.com&sz=16" },
  threads:     { label: "스레드",     favicon: "https://www.google.com/s2/favicons?domain=threads.net&sz=16" },
  dcinside:    { label: "디시인사이드", favicon: "https://www.google.com/s2/favicons?domain=dcinside.com&sz=16" },
  fmkorea:     { label: "에펨코리아",  favicon: "https://www.google.com/s2/favicons?domain=fmkorea.com&sz=16" },
  clien:       { label: "클리앙",     favicon: "https://www.google.com/s2/favicons?domain=clien.net&sz=16" },
  ruliweb:     { label: "루리웹",     favicon: "https://www.google.com/s2/favicons?domain=ruliweb.com&sz=16" },
  ppomppu:     { label: "뽐뿌",       favicon: "https://www.google.com/s2/favicons?domain=ppomppu.co.kr&sz=16" },
  mlbpark:     { label: "엠엘비파크",  favicon: "https://www.google.com/s2/favicons?domain=mlbpark.com&sz=16" },
  natepan:     { label: "네이트판",   favicon: "https://www.google.com/s2/favicons?domain=pann.nate.com&sz=16" },
  todayhumor:  { label: "오늘의유머",  favicon: "https://www.google.com/s2/favicons?domain=todayhumor.co.kr&sz=16" },
  bobaedream:  { label: "보배드림",   favicon: "https://www.google.com/s2/favicons?domain=bobaedream.co.kr&sz=16" },
};


function matchesFilter(c: Cluster, tab: FilterTag): boolean {
  switch (tab) {
    case "전체": return c.status !== "archived";
    case "대응필요":
      return c.filterTag === "대응필요" || c.grade === "red" || c.grade === "orange" ||
        (c.patterns ?? []).some((p) => p === "부정다플랫폼" || p === "다플랫폼집단");
    case "주의": return c.grade === "yellow" || c.filterTag === "주의";
    case "위기": return c.grade !== "none";
    case "재발": return !!c.reactivated || c.filterTag === "재발";
  }
}

function matchesSource(c: Cluster, src: SourceTab): boolean {
  if (src === "전체") return true;
  const platforms = c.stats?.platforms ?? [];
  const hasNews = platforms.some((p) => NEWS_PLATFORMS.has(p));
  const hasSNS = platforms.some((p) => SNS_PLATFORMS.has(p));
  const hasCommunity = platforms.some((p) => COMMUNITY_PLATFORMS.has(p));
  const hasVideo = platforms.some((p) => VIDEO_PLATFORMS.has(p));
  const hasThreads = platforms.includes("threads");

  // SNS: x/facebook 있고, threads 없고, 뉴스/커뮤니티 없는 것만
  if (src === "SNS") return hasSNS && !hasThreads && !hasNews && !hasCommunity;
  if (src === "영상") return hasVideo;
  // 뉴스: 뉴스 플랫폼이 있고, 커뮤니티·SNS 없는 것만
  if (src === "뉴스") return hasNews && !hasCommunity && !hasSNS;
  // 커뮤니티: 커뮤니티 플랫폼 있는 것 (뉴스/SNS 섞여도 포함)
  if (src === "커뮤니티") return hasCommunity;
  return false;
}

// ── 플랫폼 아이콘 ─────────────────────────────────────────
function PlatformIcon({ platform }: { platform: string }) {
  const info = PLATFORM_INFO[platform];
  if (!info) return null;
  return (
    <span className="flex items-center gap-1 rounded-full border border-gray-100 bg-white px-2 py-0.5 text-[11px] text-gray-600 shadow-sm">
      <img
        src={info.favicon}
        alt={info.label}
        className="h-3.5 w-3.5 rounded-sm"
        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
      />
      {info.label}
    </span>
  );
}

// ── 클러스터 행 ───────────────────────────────────────────
function ClusterRow({ c }: { c: Cluster }) {
  const m = GRADE_META[c.grade] ?? GRADE_META.none;
  const platforms = c.stats?.platforms ?? [];
  const shown = platforms.slice(0, 5);
  const extra = platforms.length - shown.length;
  const borderColor = {
    red: "border-l-[#e03131]",
    orange: "border-l-[#f08c00]",
    yellow: "border-l-[#f5c518]",
    none: "border-l-gray-200",
  }[c.grade] ?? "border-l-gray-200";

  return (
    <Link
      to={`/clusters/${c.id}`}
      className={`flex gap-4 rounded-xl border border-gray-200 border-l-4 ${borderColor} bg-white px-5 py-4 shadow-sm transition hover:border-brand hover:shadow-md`}
    >
      {/* 등급 */}
      <div className="flex w-14 shrink-0 flex-col items-center justify-start gap-1 pt-0.5">
        <GradeDot grade={c.grade} />
        <Chip className={`${m.chip} text-[10px]`}>{m.label}</Chip>
        {c.reactivated && <Chip className="bg-purple-100 text-purple-700 text-[10px]">재발</Chip>}
      </div>

      {/* 본문 */}
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <h3 className="line-clamp-1 font-bold text-gray-900 md:text-base">
            {c.title || "(제목 없음)"}
          </h3>
          <span className="hidden shrink-0 text-xs text-gray-400 md:block">{fmtDate(c.lastSeen)}</span>
        </div>
        {c.summary && c.summary !== c.title && (
          <p className="mt-0.5 line-clamp-2 text-sm leading-relaxed text-gray-500">{c.summary}</p>
        )}
        {/* 패턴 + 플랫폼 */}
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {(c.patterns ?? []).map((p) => (
            <Chip key={p} className="bg-slate-100 text-slate-600 text-[10px]">{p}</Chip>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-1">
            {shown.map((p) => <PlatformIcon key={p} platform={p} />)}
            {extra > 0 && <span className="self-center text-xs text-gray-400">+{extra}</span>}
          </div>
          <div className="flex gap-3 text-xs text-gray-400">
            <span>글 <b className="text-gray-600">{c.itemCount ?? c.stats?.posts ?? 0}</b></span>
            <span>댓글 <b className="text-gray-600">{c.stats?.comments ?? 0}</b></span>
            <span>👍 <b className="text-gray-600">{c.stats?.likes ?? 0}</b></span>
            <span className="md:hidden text-gray-300">{fmtDate(c.lastSeen)}</span>
          </div>
        </div>
      </div>
    </Link>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────
export default function Issues() {
  const { data, loading } = useClusters();
  const [filterTab, setFilterTab] = useState<FilterTag>("전체");
  const [sourceTab, setSourceTab] = useState<SourceTab>("뉴스");

  const filtered = useMemo(() => {
    return data.filter((c) => matchesFilter(c, filterTab) && matchesSource(c, sourceTab));
  }, [data, filterTab, sourceTab]);

  const filterCounts = useMemo(
    () => Object.fromEntries(FILTER_TABS.map((t) => [t, data.filter((c) => matchesFilter(c, t)).length])),
    [data]
  );
  const sourceCounts = useMemo(
    () => Object.fromEntries(
      SOURCE_TABS.map((s) => [s, data.filter((c) => matchesFilter(c, filterTab) && matchesSource(c, s)).length])
    ),
    [data, filterTab]
  );

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-xl font-bold text-gray-900">이슈 클러스터</h1>
        <p className="mt-0.5 text-sm text-gray-500">같은 사건을 여러 매체에서 자동으로 묶어 표시합니다.</p>
      </div>

      {/* 위기 필터 — 가로 스크롤 지원 */}
      <div className="mb-4 flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
        {FILTER_TABS.map((t) => (
          <button
            key={t}
            onClick={() => setFilterTab(t)}
            className={`shrink-0 rounded-md border px-3 py-1.5 text-sm transition ${
              filterTab === t ? "border-brand bg-brand text-white" : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
            }`}
          >
            {t}
            <span className={`ml-1.5 text-xs ${filterTab === t ? "text-white/80" : "text-gray-400"}`}>
              {filterCounts[t] ?? 0}
            </span>
          </button>
        ))}
      </div>

      {/* 소스 탭 — 가로 스크롤 지원 */}
      <div className="mb-5 flex gap-0 overflow-x-auto border-b border-gray-200 scrollbar-hide">
        {SOURCE_TABS.map((s) => (
          <button
            key={s}
            onClick={() => setSourceTab(s)}
            className={`shrink-0 whitespace-nowrap border-b-2 px-4 pb-2.5 text-sm font-medium transition ${
              sourceTab === s ? "border-brand text-brand" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {s}
            <span className="ml-1 text-xs text-gray-400">{sourceCounts[s] ?? 0}</span>
          </button>
        ))}
      </div>

      {loading ? (
        <p className="py-16 text-center text-gray-400">불러오는 중…</p>
      ) : filtered.length === 0 ? (
        <p className="py-16 text-center text-gray-400">표시할 이슈가 없습니다.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((c) => (
            <ClusterRow key={c.id} c={c} />
          ))}
        </div>
      )}
    </div>
  );
}
