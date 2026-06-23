import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useClusters } from "../lib/data";
import { Chip, GRADE_META, GradeDot, fmtDate, platformLabel } from "../lib/ui";
import type { Cluster, FilterTag } from "../types";

const TABS: FilterTag[] = ["전체", "대응필요", "주의", "위기", "재발"];

function matches(c: Cluster, tab: FilterTag): boolean {
  switch (tab) {
    case "전체":
      return c.status !== "archived";
    case "대응필요":
      return (
        c.filterTag === "대응필요" ||
        c.grade === "red" ||
        c.grade === "orange" ||
        (c.patterns ?? []).some((p) => p === "부정다플랫폼" || p === "다플랫폼집단")
      );
    case "주의":
      return c.grade === "yellow" || c.filterTag === "주의";
    case "위기":
      return c.grade !== "none";
    case "재발":
      return !!c.reactivated || c.filterTag === "재발";
  }
}

function CardStat({ label, value }: { label: string; value: number }) {
  return (
    <span className="text-gray-500">
      {label} <span className="font-semibold text-gray-700">{value}</span>
    </span>
  );
}

function ClusterCard({ c }: { c: Cluster }) {
  const m = GRADE_META[c.grade] ?? GRADE_META.none;
  const platforms = c.stats?.platforms ?? [];
  return (
    <Link
      to={`/clusters/${c.id}`}
      className="block rounded-lg border border-gray-200 bg-white p-3.5 transition hover:border-brand hover:shadow-sm"
    >
      <div className="flex items-center gap-2">
        <GradeDot grade={c.grade} />
        <Chip className={m.chip}>{m.label}</Chip>
        {c.reactivated && <Chip className="bg-purple-100 text-purple-700">재발</Chip>}
        {(c.patterns ?? []).slice(0, 2).map((p) => (
          <Chip key={p} className="bg-slate-100 text-slate-600">
            {p}
          </Chip>
        ))}
        <span className="ml-auto text-[11px] text-gray-400">{fmtDate(c.lastSeen)}</span>
      </div>
      <h3 className="mt-2 line-clamp-2 font-semibold leading-snug text-gray-900">
        {c.title || "(제목 없음)"}
      </h3>
      {c.summary && c.summary !== c.title && (
        <p className="mt-1 line-clamp-2 text-sm text-gray-500">{c.summary}</p>
      )}
      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <CardStat label="글" value={c.itemCount ?? c.stats?.posts ?? 0} />
        <CardStat label="댓글" value={c.stats?.comments ?? 0} />
        <CardStat label="좋아요" value={c.stats?.likes ?? 0} />
        <span className="ml-auto text-gray-400">
          {platforms.slice(0, 3).map(platformLabel).join(" · ")}
          {platforms.length > 3 ? ` +${platforms.length - 3}` : ""}
        </span>
      </div>
    </Link>
  );
}

export default function Issues() {
  const { data, loading } = useClusters();
  const [tab, setTab] = useState<FilterTag>("전체");

  const filtered = useMemo(() => data.filter((c) => matches(c, tab)), [data, tab]);
  const counts = useMemo(
    () => Object.fromEntries(TABS.map((t) => [t, data.filter((c) => matches(c, t)).length])),
    [data]
  );

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-xl font-bold text-gray-900">이슈 클러스터</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          같은 사건을 여러 매체에서 자동으로 묶어 표시합니다. 위기 분류는 자동 갱신됩니다.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md border px-3 py-1.5 text-sm transition ${
              tab === t
                ? "border-brand bg-brand text-white"
                : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
            }`}
          >
            {t}
            <span className={`ml-1.5 text-xs ${tab === t ? "text-white/80" : "text-gray-400"}`}>
              {counts[t] ?? 0}
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <p className="py-16 text-center text-gray-400">불러오는 중…</p>
      ) : filtered.length === 0 ? (
        <p className="py-16 text-center text-gray-400">표시할 이슈가 없습니다.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((c) => (
            <ClusterCard key={c.id} c={c} />
          ))}
        </div>
      )}
    </div>
  );
}
