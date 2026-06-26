import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useClusters, useReports, usePolls, useAlerts } from "../lib/data";
import { fmtDate } from "../lib/ui";

// ── 유틸 ──────────────────────────────────────────────────────
function dday(): number {
  const target = new Date("2026-08-17T00:00:00+09:00");
  return Math.ceil((target.getTime() - Date.now()) / 86400000);
}

function todayKST(): string {
  return new Date().toLocaleDateString("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric", month: "long", day: "numeric", weekday: "short",
  });
}

function isToday(ts: any): boolean {
  if (!ts) return false;
  const d = ts.toDate ? ts.toDate() : new Date(ts);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

// ── KPI 카드 ──────────────────────────────────────────────────
function KpiCard({
  label, value, sub, color = "text-navy", icon,
}: {
  label: string; value: string | number; sub?: string;
  color?: string; icon: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm flex items-start gap-3">
      <span className="text-2xl mt-0.5">{icon}</span>
      <div className="min-w-0">
        <p className="text-xs text-gray-500 font-medium">{label}</p>
        <p className={`text-2xl font-black mt-0.5 ${color}`}>{value}</p>
        {sub && <p className="text-[11px] text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ── 등급 배지 ──────────────────────────────────────────────────
function GradeBadge({ grade }: { grade: string }) {
  const map: Record<string, string> = {
    red:    "bg-danger-red/10 text-danger-red border border-danger-red/30",
    orange: "bg-warning-orange/10 text-warning-orange border border-warning-orange/30",
    yellow: "bg-yellow-50 text-yellow-700 border border-yellow-300",
    none:   "bg-gray-100 text-gray-500 border border-gray-200",
  };
  const label: Record<string, string> = { red: "위기", orange: "주의", yellow: "관찰", none: "일반" };
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${map[grade] ?? map.none}`}>
      {label[grade] ?? grade}
    </span>
  );
}

// ── 섹션 헤더 ──────────────────────────────────────────────────
function SectionHeader({ title, to, count }: { title: string; to: string; count?: number }) {
  return (
    <div className="flex items-center justify-between">
      <h2 className="text-sm font-bold text-white flex items-center gap-2">
        <span className="inline-block w-0.5 h-4 bg-blue-300 rounded" />
        {title}
        {count !== undefined && (
          <span className="ml-1 rounded-full bg-white/20 px-2 py-0.5 text-[10px] text-white/80 font-normal">
            {count}건
          </span>
        )}
      </h2>
      <Link to={to} className="text-xs text-blue-200 hover:text-white transition">전체 보기 →</Link>
    </div>
  );
}

// ── 메인 컴포넌트 ──────────────────────────────────────────────
export default function Dashboard() {
  const { data: clusters, loading: cLoading } = useClusters();
  const { data: reports, loading: rLoading } = useReports();
  const { data: allPolls, loading: pLoading } = usePolls();
  const { data: alerts, loading: aLoading } = useAlerts();

  const D = dday();

  // 이슈 KPI
  const todayClusters = useMemo(
    () => clusters.filter((c) => isToday((c as any).lastSeen)),
    [clusters]
  );
  const criticalClusters = useMemo(
    () => clusters.filter((c) => c.grade === "red" || c.grade === "orange"),
    [clusters]
  );
  const reportClusters = useMemo(
    () => clusters.filter((c) => c.grade === "red"),
    [clusters]
  );

  // 최신 브리핑
  const latestReport = useMemo(
    () => reports.find((r) => (r as any).type === "daily" || !(r as any).type),
    [reports]
  );
  const hasTodayReport = useMemo(
    () => reports.some((r) => isToday((r as any).generatedAt)),
    [reports]
  );

  // 최신 여론조사 (수치 있는 것만)
  const CANDIDATES = ["정청래", "김민석", "송영길", "김용민"];
  const pollsWithData = useMemo(() => {
    return (allPolls as any[])
      .filter((p) => {
        const cands = p.candidatesGeneral ?? p.candidates ?? [];
        return cands.some((c: any) => CANDIDATES.includes(c.name));
      })
      .sort((a: any, b: any) => {
        const da = a.regDate || a.publishedAt?.toDate?.()?.toISOString() || "";
        const db2 = b.regDate || b.publishedAt?.toDate?.()?.toISOString() || "";
        return db2.localeCompare(da);
      });
  }, [allPolls]);
  const latestPoll = pollsWithData[0] as any;

  // 최근 알림
  const recentAlerts = alerts.slice(0, 5);

  // 텔레그램 요약 또는 본문 앞부분
  const briefingSummary = useMemo(() => {
    if (!latestReport) return null;
    const r = latestReport as any;
    if (r.telegramText) return r.telegramText.slice(0, 400);
    if (r.bodyMarkdown) return r.bodyMarkdown.slice(0, 400);
    return null;
  }, [latestReport]);

  return (
    <div className="space-y-6">
      {/* ── 상단 헤더 ───────────────────────────────────────────── */}
      <div className="rounded-xl bg-navy text-white p-5 shadow-md">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-lg font-black tracking-tight">
                <span className="text-blue-300">H</span>ORIZON<span className="text-gray-400 font-normal text-sm">0817</span>
              </span>
              <span className="rounded-lg bg-white/10 px-3 py-1 text-2xl font-black text-white">
                D-{D}
              </span>
              <span className="text-sm text-gray-300">8·17 전당대회</span>
            </div>
            <p className="mt-1.5 text-xs text-gray-400">{todayKST()}</p>
          </div>
          <div className="flex gap-2">
            <Link
              to="/reports"
              className="rounded-lg bg-brand px-4 py-2 text-xs font-bold text-white hover:bg-brand-dark transition"
            >
              오늘 브리핑 보기
            </Link>
            <Link
              to="/alerts"
              className="rounded-lg bg-white/10 px-4 py-2 text-xs font-bold text-white hover:bg-white/20 transition"
            >
              위기·대응
            </Link>
          </div>
        </div>
      </div>

      {/* ── KPI 카드 ────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <KpiCard
          icon="📰"
          label="오늘 수집 이슈"
          value={cLoading ? "…" : todayClusters.length}
          sub="최근 24시간 기준"
          color="text-navy"
        />
        <KpiCard
          icon="⚠️"
          label="위기·주의 이슈"
          value={cLoading ? "…" : criticalClusters.length}
          sub="red + orange 등급"
          color={criticalClusters.length > 0 ? "text-danger-red" : "text-gray-400"}
        />
        <KpiCard
          icon="📋"
          label="즉시 보고 이슈"
          value={cLoading ? "…" : reportClusters.length}
          sub="위기(red) 등급"
          color={reportClusters.length > 0 ? "text-warning-orange" : "text-gray-400"}
        />
        <KpiCard
          icon="📄"
          label="오늘 브리핑"
          value={rLoading ? "…" : hasTodayReport ? "완료" : "대기중"}
          sub={hasTodayReport ? "매일 오전 6시 자동생성" : "오전 6시 생성 예정"}
          color={hasTodayReport ? "text-green-accent" : "text-gray-400"}
        />
        <KpiCard
          icon="📊"
          label="최신 여론조사"
          value={pLoading ? "…" : pollsWithData.length > 0 ? "있음" : "없음"}
          sub={latestPoll ? `최신: ${latestPoll.regDate?.slice(0, 10) ?? "날짜 미상"}` : "데이터 없음"}
          color={pollsWithData.length > 0 ? "text-brand" : "text-gray-400"}
        />
      </div>

      {/* ── 2단 그리드 ──────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 오늘의 핵심 흐름 (브리핑 요약) */}
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="bg-navy px-4 py-3 flex items-center justify-between">
            <span className="text-sm font-bold text-white">오늘의 핵심 흐름</span>
            {hasTodayReport && (
              <span className="text-[10px] bg-green-accent/20 text-green-accent rounded-full px-2 py-0.5 font-bold">
                브리핑 생성됨
              </span>
            )}
          </div>
          <div className="p-4">
            {rLoading ? (
              <p className="text-sm text-gray-400 py-6 text-center">불러오는 중…</p>
            ) : briefingSummary ? (
              <div className="space-y-2">
                <pre className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed font-sans">
                  {briefingSummary}
                </pre>
                <Link
                  to="/reports"
                  className="mt-3 inline-flex items-center gap-1 text-xs text-brand hover:underline font-semibold"
                >
                  전체 브리핑 보기 →
                </Link>
              </div>
            ) : (
              <div className="py-6 text-center">
                <p className="text-sm text-gray-400">아직 오늘 브리핑이 없습니다.</p>
                <p className="text-xs text-gray-300 mt-1">매일 오전 6시 자동 생성</p>
              </div>
            )}
          </div>
        </div>

        {/* 위기·대응 현황 */}
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="bg-navy px-4 py-3 flex items-center justify-between">
            <span className="text-sm font-bold text-white">위기·대응 현황</span>
            {recentAlerts.filter((a) => a.grade === "red").length > 0 && (
              <span className="text-[10px] bg-danger-red/20 text-danger-red rounded-full px-2 py-0.5 font-bold">
                위기 {recentAlerts.filter((a) => a.grade === "red").length}건
              </span>
            )}
          </div>
          <div className="divide-y divide-gray-100">
            {aLoading ? (
              <p className="text-sm text-gray-400 p-4 text-center">불러오는 중…</p>
            ) : recentAlerts.length === 0 ? (
              <p className="text-sm text-gray-400 p-4 text-center">감지된 위기 신호 없음</p>
            ) : (
              recentAlerts.map((a) => (
                <div key={a.id} className="px-4 py-3 flex items-start gap-3">
                  <GradeBadge grade={a.grade} />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-gray-700 truncate">{a.type || "위기 신호"}</p>
                    <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{a.summary}</p>
                  </div>
                  <span className="text-[10px] text-gray-300 shrink-0">{fmtDate(a.createdAt)}</span>
                </div>
              ))
            )}
          </div>
          <div className="px-4 py-2.5 border-t border-gray-100">
            <Link to="/alerts" className="text-xs text-brand hover:underline">전체 위기 현황 →</Link>
          </div>
        </div>
      </div>

      {/* ── 보고 필요 이슈 ───────────────────────────────────────── */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
        <div className="bg-navy px-4 py-3">
          <SectionHeader title="보고 필요 이슈" to="/issues" count={criticalClusters.length} />
        </div>
        <div className="divide-y divide-gray-100">
          {cLoading ? (
            <p className="text-sm text-gray-400 p-4 text-center">불러오는 중…</p>
          ) : criticalClusters.length === 0 ? (
            <p className="text-sm text-gray-400 p-4 text-center">보고 필요 이슈 없음</p>
          ) : (
            criticalClusters.slice(0, 8).map((c) => (
              <Link
                key={c.id}
                to={`/clusters/${c.id}`}
                className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 transition"
              >
                <GradeBadge grade={c.grade} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-gray-800 truncate">{c.title}</p>
                  {c.summary && (
                    <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{c.summary}</p>
                  )}
                </div>
                <div className="text-right shrink-0">
                  <p className="text-xs text-gray-400">
                    {c.stats?.posts ?? c.itemCount ?? 0}건
                  </p>
                </div>
              </Link>
            ))
          )}
        </div>
        {criticalClusters.length > 8 && (
          <div className="px-4 py-2.5 border-t border-gray-100">
            <Link to="/issues" className="text-xs text-brand hover:underline">
              +{criticalClusters.length - 8}건 더 보기 →
            </Link>
          </div>
        )}
      </div>

      {/* ── 최신 여론조사 ───────────────────────────────────────── */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
        <div className="bg-navy px-4 py-3">
          <SectionHeader title="최신 여론조사" to="/polls" count={pollsWithData.length} />
        </div>
        {pLoading ? (
          <p className="text-sm text-gray-400 p-4 text-center">불러오는 중…</p>
        ) : pollsWithData.length === 0 ? (
          <p className="text-sm text-gray-400 p-4 text-center">여론조사 데이터 없음</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  {["조사일", "기관/매체", "조사대상", "김민석", "정청래", "송영길", "김용민", "1위", "원문"].map((h) => (
                    <th key={h} className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {pollsWithData.slice(0, 5).map((p: any) => {
                  const cands: { name: string; pct: number }[] = p.candidatesGeneral ?? p.candidates ?? [];
                  const get = (name: string) => cands.find((c) => c.name === name)?.pct;
                  const top = [...cands].sort((a, b) => b.pct - a.pct)[0];
                  const date =
                    p.regDate?.slice(0, 10) ||
                    p.publishedAt?.toDate?.()?.toISOString()?.slice(0, 10) ||
                    "-";
                  const link = p.detailUrl || p.url;
                  return (
                    <tr key={p.id} className="hover:bg-gray-50 transition">
                      <td className="px-3 py-2.5 text-xs text-gray-600 whitespace-nowrap">{date}</td>
                      <td className="px-3 py-2.5 text-xs text-gray-700 whitespace-nowrap max-w-[120px] truncate">
                        {p.org || p.client || p.name || "-"}
                      </td>
                      <td className="px-3 py-2.5 text-xs text-gray-500 whitespace-nowrap">
                        {p.sampleGroup || p.respondents || "-"}
                      </td>
                      <Pct val={get("김민석")} highlight />
                      <Pct val={get("정청래")} />
                      <Pct val={get("송영길")} />
                      <Pct val={get("김용민")} />
                      <td className="px-3 py-2.5 text-xs font-bold text-brand whitespace-nowrap">
                        {top?.name ?? "-"}
                      </td>
                      <td className="px-3 py-2.5">
                        {link ? (
                          <a
                            href={link}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-brand hover:underline"
                          >
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
        )}
        <div className="px-4 py-2.5 border-t border-gray-100">
          <Link to="/polls" className="text-xs text-brand hover:underline">
            전체 여론조사 보기 →
          </Link>
        </div>
      </div>

      {/* ── 세력 변화 요약 (placeholder) ─────────────────────────── */}
      <div className="rounded-xl border border-dashed border-gray-300 bg-white/60 shadow-sm p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold text-gray-600 flex items-center gap-2">
            <span className="inline-block w-0.5 h-4 bg-gray-300 rounded" />
            세력 변화 요약
          </h2>
          <span className="text-[10px] text-gray-400 bg-gray-100 rounded-full px-2 py-0.5">
            수동 검증 준비 중
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {["신규 지지·우호 인물", "확인 필요 인물", "핵심 스피커 변화", "후보별 미디어 흐름"].map((label) => (
            <div key={label} className="rounded-lg bg-gray-50 border border-gray-200 p-3 text-center">
              <p className="text-xs text-gray-400">{label}</p>
              <p className="text-sm text-gray-300 mt-1 font-semibold">확인 필요</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-gray-400 text-center">
          세력지도는 수동 검증 기반으로 단계적으로 구축됩니다. →{" "}
          <Link to="/allies" className="text-brand hover:underline">세력지도 바로가기</Link>
        </p>
      </div>
    </div>
  );
}

// 퍼센트 셀
function Pct({ val, highlight }: { val: number | undefined; highlight?: boolean }) {
  if (val === undefined || val === null) {
    return <td className="px-3 py-2.5 text-xs text-gray-300">-</td>;
  }
  return (
    <td className={`px-3 py-2.5 text-xs font-bold whitespace-nowrap ${
      highlight ? "text-brand" : "text-gray-700"
    }`}>
      {val}%
    </td>
  );
}
