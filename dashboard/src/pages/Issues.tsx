import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useClusters } from "../lib/data";
import { reclassifyCluster } from "../lib/data";
import { Chip, GRADE_META, GradeDot, fmtDate } from "../lib/ui";
import type { Cluster, FilterTag, SourceType } from "../types";
import { MAIN_CANDIDATE_NAMES } from "../lib/candidates";

// ── 탭 정의 ──────────────────────────────────────────────────────
const FILTER_TABS: FilterTag[] = ["전체", "대응필요", "주의", "위기", "재발"];
const SOURCE_TABS = ["전체", "뉴스", "SNS", "커뮤니티", "영상", "공식", "확인필요"] as const;
type SourceTab = typeof SOURCE_TABS[number];

const CAND_TABS = ["전체", ...MAIN_CANDIDATE_NAMES] as const;
type CandTab = typeof CAND_TABS[number];

// ── sourceType 매핑 ──────────────────────────────────────────────
// 뉴스: 언론사 기사만
const NEWS_PLATFORMS = new Set([
  "naver_news", "daum_news", "google_news", "rss", "nate_news",
]);
// SNS: Facebook / X / Instagram / Threads
const SNS_PLATFORMS = new Set([
  "facebook", "x", "twitter", "instagram", "threads",
]);
// 커뮤니티
const COMMUNITY_PLATFORMS = new Set([
  "dcinside", "fmkorea", "clien", "ruliweb", "ppomppu", "bobaedream",
  "naver_cafe", "mlbpark", "natepan", "natepann", "todayhumor", "ddanzi", "theqoo",
]);
// 영상: YouTube만
const VIDEO_PLATFORMS = new Set([
  "youtube",
]);
// 공식
const OFFICIAL_PLATFORMS = new Set([
  "official", "theminjoo", "nec", "assembly",
]);

// 플랫폼 배열 → 주 sourceType 추론 (클러스터에 sourceType 필드 없을 때 폴백)
function inferSourceType(platforms: string[]): SourceType {
  const ps = new Set(platforms);
  if ([...ps].some((p) => OFFICIAL_PLATFORMS.has(p))) return "official";
  if ([...ps].some((p) => VIDEO_PLATFORMS.has(p))) return "video";
  if ([...ps].some((p) => SNS_PLATFORMS.has(p)) && ![...ps].some((p) => NEWS_PLATFORMS.has(p) || COMMUNITY_PLATFORMS.has(p))) return "sns";
  if ([...ps].some((p) => NEWS_PLATFORMS.has(p)) && ![...ps].some((p) => COMMUNITY_PLATFORMS.has(p) || SNS_PLATFORMS.has(p))) return "news";
  if ([...ps].some((p) => COMMUNITY_PLATFORMS.has(p))) return "community";
  if ([...ps].some((p) => NEWS_PLATFORMS.has(p))) return "news";
  return "unknown";
}

function getSourceType(c: Cluster): SourceType {
  if (c.sourceType) return c.sourceType;
  return inferSourceType(c.stats?.platforms ?? []);
}

// 확인필요: sourceType이 unknown이거나 플랫폼 혼재
function needsReview(c: Cluster): boolean {
  // 낮은 병합 신뢰도
  if ((c.clusterConfidence ?? 1.0) < 0.75) return true;
  if (c.sourceType === "unknown") return true;
  const platforms = c.stats?.platforms ?? [];
  if (platforms.length === 0) return !c.sourceType;
  const hasNews = platforms.some((p) => NEWS_PLATFORMS.has(p));
  const hasCommunity = platforms.some((p) => COMMUNITY_PLATFORMS.has(p));
  const hasSNS = platforms.some((p) => SNS_PLATFORMS.has(p));
  const hasVideo = platforms.some((p) => VIDEO_PLATFORMS.has(p));
  if (hasVideo && hasNews) return true;
  if (hasCommunity && hasSNS && !hasNews) return true;
  if (!c.sourceType) {
    if (!hasNews && !hasSNS && !hasCommunity && !hasVideo) return true;
  }
  return false;
}

// 확인필요 추정 사유
function reviewReason(c: Cluster): string {
  const platforms = c.stats?.platforms ?? [];
  if (platforms.length === 0) return "플랫폼 정보 없음";
  const hasNews = platforms.some((p) => NEWS_PLATFORMS.has(p));
  const hasVideo = platforms.some((p) => VIDEO_PLATFORMS.has(p));
  const hasCommunity = platforms.some((p) => COMMUNITY_PLATFORMS.has(p));
  const hasSNS = platforms.some((p) => SNS_PLATFORMS.has(p));
  const conf = c.clusterConfidence ?? 1.0;
  if (conf < 0.50) return `병합 신뢰도 매우 낮음 (${conf.toFixed(2)}) — split 후보`;
  if (conf < 0.75) return `병합 신뢰도 낮음 (${conf.toFixed(2)}) — 확인 필요`;
  if (hasVideo && hasNews) return "뉴스+YouTube 혼재 — 영상인지 뉴스보도인지 불명확";
  if (hasCommunity && hasSNS) return "커뮤니티+SNS 혼재";
  if (hasCommunity && hasNews) return "커뮤니티+뉴스 혼재";
  if (!hasNews && !hasSNS && !hasCommunity && !hasVideo) return "알 수 없는 플랫폼";
  return "소스 분류 불명확";
}

function matchesSource(c: Cluster, src: SourceTab): boolean {
  if (src === "전체") return true;
  if (src === "확인필요") return needsReview(c);
  // unknown 항목은 확인필요 탭에만 표시 — 나머지 탭에서 제외
  if (needsReview(c)) return false;
  const st = getSourceType(c);
  switch (src) {
    case "뉴스": return st === "news";
    case "SNS": return st === "sns";
    case "커뮤니티": return st === "community";
    case "영상": return st === "video";
    case "공식": return st === "official";
    default: return false;
  }
}

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

function matchesCandidate(c: Cluster, cand: CandTab): boolean {
  if (cand === "전체") return true;
  const text = `${c.title} ${c.summary ?? ""}`;
  return text.includes(cand);
}

// ── 플랫폼 메타 ───────────────────────────────────────────────────
const PLATFORM_INFO: Record<string, { label: string; favicon: string }> = {
  naver_news:  { label: "네이버뉴스",   favicon: "https://www.google.com/s2/favicons?domain=news.naver.com&sz=16" },
  naver_blog:  { label: "네이버블로그", favicon: "https://www.google.com/s2/favicons?domain=blog.naver.com&sz=16" },
  naver_cafe:  { label: "네이버카페",   favicon: "https://www.google.com/s2/favicons?domain=cafe.naver.com&sz=16" },
  daum_news:   { label: "다음뉴스",    favicon: "https://www.google.com/s2/favicons?domain=news.daum.net&sz=16" },
  google_news: { label: "구글뉴스",    favicon: "https://www.google.com/s2/favicons?domain=news.google.com&sz=16" },
  rss:         { label: "RSS",         favicon: "https://www.google.com/s2/favicons?domain=google.com&sz=16" },
  nate_news:   { label: "네이트뉴스",   favicon: "https://www.google.com/s2/favicons?domain=news.nate.com&sz=16" },
  youtube:     { label: "유튜브",      favicon: "https://www.google.com/s2/favicons?domain=youtube.com&sz=16" },
  x:           { label: "X",           favicon: "https://www.google.com/s2/favicons?domain=x.com&sz=16" },
  twitter:     { label: "X",           favicon: "https://www.google.com/s2/favicons?domain=x.com&sz=16" },
  instagram:   { label: "인스타그램",   favicon: "https://www.google.com/s2/favicons?domain=instagram.com&sz=16" },
  facebook:    { label: "페이스북",    favicon: "https://www.google.com/s2/favicons?domain=facebook.com&sz=16" },
  threads:     { label: "스레드",      favicon: "https://www.google.com/s2/favicons?domain=threads.net&sz=16" },
  dcinside:    { label: "디시인사이드", favicon: "https://www.google.com/s2/favicons?domain=dcinside.com&sz=16" },
  fmkorea:     { label: "에펨코리아",   favicon: "https://www.google.com/s2/favicons?domain=fmkorea.com&sz=16" },
  clien:       { label: "클리앙",      favicon: "https://www.google.com/s2/favicons?domain=clien.net&sz=16" },
  ruliweb:     { label: "루리웹",      favicon: "https://www.google.com/s2/favicons?domain=ruliweb.com&sz=16" },
  ppomppu:     { label: "뽐뿌",        favicon: "https://www.google.com/s2/favicons?domain=ppomppu.co.kr&sz=16" },
  mlbpark:     { label: "엠엘비파크",   favicon: "https://www.google.com/s2/favicons?domain=mlbpark.com&sz=16" },
  natepan:     { label: "네이트판",    favicon: "https://www.google.com/s2/favicons?domain=pann.nate.com&sz=16" },
  todayhumor:  { label: "오늘의유머",   favicon: "https://www.google.com/s2/favicons?domain=todayhumor.co.kr&sz=16" },
  bobaedream:  { label: "보배드림",    favicon: "https://www.google.com/s2/favicons?domain=bobaedream.co.kr&sz=16" },
  ddanzi:      { label: "딴지일보",    favicon: "https://www.google.com/s2/favicons?domain=ddanzi.com&sz=16" },
  theqoo:      { label: "더쿠",        favicon: "https://www.google.com/s2/favicons?domain=theqoo.net&sz=16" },
  official:    { label: "공식",        favicon: "https://www.google.com/s2/favicons?domain=theminjoo.kr&sz=16" },
};

const SOURCE_TYPE_LABEL: Record<string, string> = {
  news: "뉴스", sns: "SNS", community: "커뮤니티", video: "영상",
  official: "공식", blog_cafe: "블로그/카페", unknown: "확인필요",
};

function PlatformIcon({ platform }: { platform: string }) {
  const info = PLATFORM_INFO[platform];
  if (!info) return null;
  return (
    <span className="flex items-center gap-1 rounded-full border border-gray-100 bg-white px-2 py-0.5 text-[11px] text-gray-600 shadow-sm">
      <img src={info.favicon} alt={info.label} className="h-3.5 w-3.5 rounded-sm"
        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
      {info.label}
    </span>
  );
}

// ── 확인필요 재분류 버튼 ──────────────────────────────────────────
const RECLASSIFY_OPTIONS: { label: string; type: SourceType }[] = [
  { label: "뉴스", type: "news" },
  { label: "SNS", type: "sns" },
  { label: "커뮤니티", type: "community" },
  { label: "영상", type: "video" },
  { label: "공식", type: "official" },
];

function ReclassifyButtons({ c }: { c: Cluster }) {
  const [done, setDone] = useState(false);
  if (done) return <span className="text-xs text-green-600 font-semibold">재분류 완료</span>;
  return (
    <div className="mt-2 flex flex-wrap gap-1">
      <span className="text-[11px] text-gray-400 self-center mr-1">재분류:</span>
      {RECLASSIFY_OPTIONS.map((opt) => (
        <button
          key={opt.type}
          onClick={async (e) => {
            e.preventDefault();
            await reclassifyCluster(c.id, opt.type, c.sourceType);
            setDone(true);
          }}
          className="rounded border border-gray-200 bg-white px-2 py-0.5 text-[11px] text-gray-600 hover:bg-gray-50 hover:border-gray-300"
        >
          {opt.label}로 이동
        </button>
      ))}
    </div>
  );
}

// ── 클러스터 카드 ─────────────────────────────────────────────────
function ClusterRow({ c, showReclassify = false }: { c: Cluster; showReclassify?: boolean }) {
  const m = GRADE_META[c.grade] ?? GRADE_META.none;
  const platforms = c.stats?.platforms ?? [];
  const shown = platforms.slice(0, 5);
  const extra = platforms.length - shown.length;
  const borderColor = {
    red: "border-l-[#e03131]", orange: "border-l-[#f08c00]",
    yellow: "border-l-[#f5c518]", none: "border-l-gray-200",
  }[c.grade] ?? "border-l-gray-200";

  const st = getSourceType(c);
  const displayTitle = c.latestArticleTitle ?? c.representativeTitle ?? c.title;
  const timeLabel = c.latestPublishedAt
    ? `발행 ${fmtDate(c.latestPublishedAt)}`
    : c.lastSeen
    ? `수집 ${fmtDate(c.lastSeen)}`
    : "";

  return (
    <Link
      to={`/clusters/${c.id}`}
      className={`flex gap-4 rounded-xl border border-gray-200 border-l-4 ${borderColor} bg-white px-5 py-4 shadow-sm transition hover:border-brand hover:shadow-md`}
    >
      <div className="flex w-14 shrink-0 flex-col items-center justify-start gap-1 pt-0.5">
        <GradeDot grade={c.grade} />
        <Chip className={`${m.chip} text-[10px]`}>{m.label}</Chip>
        {c.reactivated && <Chip className="bg-purple-100 text-purple-700 text-[10px]">재발</Chip>}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <h3 className="line-clamp-1 font-bold text-gray-900 md:text-base">{displayTitle || "(제목 없음)"}</h3>
          <div className="hidden shrink-0 flex-col items-end gap-0.5 md:flex">
            <span className="text-[10px] text-gray-400">{timeLabel}</span>
            {st !== "unknown" && (
              <span className="text-[10px] text-gray-300">{SOURCE_TYPE_LABEL[st] ?? st}</span>
            )}
            {st === "unknown" && (
              <span className="text-[10px] text-amber-500 font-semibold">확인필요</span>
            )}
          </div>
        </div>

        {c.summary && c.summary !== c.title && (
          <p className="mt-0.5 line-clamp-2 text-sm leading-relaxed text-gray-500">{c.summary}</p>
        )}

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
          </div>
        </div>

        {showReclassify && (
          <div className="mt-2 rounded-md border border-amber-100 bg-amber-50 px-3 py-1.5">
            <p className="text-[11px] text-amber-700 font-semibold">
              ⚠ 확인필요 사유: {reviewReason(c)}
            </p>
            <ReclassifyButtons c={c} />
          </div>
        )}
      </div>
    </Link>
  );
}

// ── 메인 페이지 ──────────────────────────────────────────────────
export default function Issues() {
  const [sourceTab, setSourceTab] = useState<SourceTab>("뉴스");
  const [filterTab, setFilterTab] = useState<FilterTag>("전체");
  const [candTab, setCandTab] = useState<CandTab>("전체");

  // 뉴스 탭은 latestPublishedAt 기본, 나머지는 lastSeen
  const sortBy = sourceTab === "뉴스" ? "latestPublishedAt" : "lastSeen";
  const { data, loading } = useClusters(sortBy);

  const filtered = useMemo(() => {
    return data.filter((c) =>
      matchesFilter(c, filterTab) &&
      matchesSource(c, sourceTab) &&
      matchesCandidate(c, candTab)
    );
  }, [data, filterTab, sourceTab, candTab]);

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
  const candCounts = useMemo(
    () => Object.fromEntries(
      CAND_TABS.map((n) => [n, data.filter((c) => matchesFilter(c, filterTab) && matchesCandidate(c, n)).length])
    ),
    [data, filterTab]
  );

  return (
    <div>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">이슈 상황판</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            소스별 최신 이슈 — 뉴스 탭은 발행시각 최신순 자동 정렬
          </p>
        </div>
        <div className="hidden shrink-0 items-center gap-1 rounded-lg border border-gray-200 bg-white p-1 md:flex">
          <span className="px-2 text-xs text-gray-400">
            정렬: {sortBy === "latestPublishedAt" ? "발행시각순" : "수집시각순"}
          </span>
        </div>
      </div>

      {/* 소스 탭 (최상단) */}
      <div className="mb-4 flex gap-0 overflow-x-auto border-b border-gray-200 scrollbar-hide">
        {SOURCE_TABS.map((s) => {
          const isReview = s === "확인필요";
          const cnt = sourceCounts[s] ?? 0;
          return (
            <button
              key={s}
              onClick={() => setSourceTab(s)}
              className={`shrink-0 whitespace-nowrap border-b-2 px-4 pb-2.5 text-sm font-medium transition ${
                sourceTab === s
                  ? isReview ? "border-amber-500 text-amber-600" : "border-brand text-brand"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {s}
              <span className={`ml-1 text-xs ${isReview && cnt > 0 ? "text-amber-500 font-bold" : "text-gray-400"}`}>
                {cnt}
              </span>
            </button>
          );
        })}
      </div>

      {/* 위기 필터 */}
      <div className="mb-3 flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
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

      {/* 후보 필터 (4명 고정) */}
      <div className="mb-5 flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
        {CAND_TABS.map((n) => (
          <button
            key={n}
            onClick={() => setCandTab(n)}
            className={`shrink-0 rounded-full border px-3 py-1 text-xs font-semibold transition ${
              candTab === n ? "border-brand bg-brand text-white" : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
            }`}
          >
            {n}
            <span className={`ml-1 ${candTab === n ? "text-white/70" : "text-gray-400"}`}>
              {candCounts[n] ?? 0}
            </span>
          </button>
        ))}
      </div>

      {/* 탭별 안내 */}
      {sourceTab === "뉴스" && (
        <div className="mb-3 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-700">
          언론사 기사만 표시 · 발행시각 최신순 정렬
        </div>
      )}
      {sourceTab === "영상" && (
        <div className="mb-3 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-xs text-red-700">
          YouTube 영상/쇼츠/라이브만 표시
        </div>
      )}
      {sourceTab === "커뮤니티" && (
        <div className="mb-3 rounded-lg border border-green-100 bg-green-50 px-3 py-2 text-xs text-green-700">
          커뮤니티 게시글 중심 · 뉴스 공유글(shared_news)은 별도 분류
        </div>
      )}
      {sourceTab === "확인필요" && (
        <div className="mb-3 rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-700">
          소스 분류가 불명확하거나 혼재된 클러스터 · 카드 하단 버튼으로 재분류 가능
        </div>
      )}
      {sourceTab === "공식" && (
        <div className="mb-3 rounded-lg border border-purple-100 bg-purple-50 px-3 py-2 text-xs text-purple-700">
          민주당 공식자료 / 선관위 / 국회 / 후보 공식 발표만 표시
        </div>
      )}

      {loading ? (
        <p className="py-16 text-center text-gray-400">불러오는 중…</p>
      ) : filtered.length === 0 ? (
        <div className="py-16 text-center text-gray-400">
          <p>표시할 이슈가 없습니다.</p>
          {sourceTab === "공식" && (
            <p className="mt-1 text-xs text-gray-300">공식 소스로 분류된 클러스터가 없습니다.</p>
          )}
          {sourceTab === "확인필요" && (
            <p className="mt-1 text-xs text-gray-300">오분류 의심 항목이 없습니다.</p>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((c) => (
            <ClusterRow key={c.id} c={c} showReclassify={sourceTab === "확인필요"} />
          ))}
        </div>
      )}
    </div>
  );
}
