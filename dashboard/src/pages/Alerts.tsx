import { Link } from "react-router-dom";
import { useAlerts } from "../lib/data";
import { Chip, GRADE_META, GradeDot, fmtDate } from "../lib/ui";

export default function Alerts() {
  const { data, loading } = useAlerts();
  return (
    <div>
      <h1 className="text-xl font-bold text-gray-900">위기 알림</h1>
      <p className="mt-0.5 text-sm text-gray-500">
        시스템이 자동 감지한 위기 신호 히스토리입니다.
      </p>
      <div className="mt-4 space-y-2">
        {loading ? (
          <p className="py-16 text-center text-gray-400">불러오는 중…</p>
        ) : data.length === 0 ? (
          <p className="py-16 text-center text-gray-400">감지된 위기 신호가 없습니다.</p>
        ) : (
          data.map((a) => {
            const m = GRADE_META[a.grade] ?? GRADE_META.none;
            return (
              <div key={a.id} className="rounded-lg border border-gray-200 bg-white p-4">
                <div className="flex items-center gap-2">
                  <GradeDot grade={a.grade} />
                  <Chip className={m.chip}>{m.label}</Chip>
                  <span className="font-semibold text-gray-900">{a.type}</span>
                  <span className="ml-auto text-xs text-gray-400">{fmtDate(a.createdAt)}</span>
                </div>
                <p className="mt-2 text-sm text-gray-700">{a.summary}</p>
                {!!a.clusterIds?.length && (
                  <Link
                    to={`/clusters/${a.clusterIds[0]}`}
                    className="mt-2 inline-block text-sm text-brand hover:underline"
                  >
                    관련 이슈 보기 →
                  </Link>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
