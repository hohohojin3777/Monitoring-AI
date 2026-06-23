import { useRejected } from "../lib/data";
import { Chip, fmtDate, platformLabel } from "../lib/ui";

const REASON_LABEL: Record<string, string> = {
  duplicate: "중복",
  old_date: "기간 초과",
  no_date: "날짜 미상",
  irrelevant: "무관",
  noise: "노이즈/광고",
  hallucination: "환각 차단",
};

export default function Rejected() {
  const { data, loading } = useRejected();
  return (
    <div>
      <h1 className="text-xl font-bold text-gray-900">거부 검토</h1>
      <p className="mt-0.5 text-sm text-gray-500">
        필터(중복·기간·무관·노이즈)에 걸려 제외된 글입니다. 오탐 점검용으로 표시됩니다.
      </p>
      <div className="mt-4 rounded-lg border border-gray-200 bg-white">
        {loading ? (
          <p className="py-12 text-center text-gray-400">불러오는 중…</p>
        ) : data.length === 0 ? (
          <p className="py-12 text-center text-gray-400">거부된 글이 없습니다.</p>
        ) : (
          <ul className="divide-y">
            {data.map((it) => (
              <li key={it.id} className="flex items-center gap-2 px-4 py-2.5 text-sm">
                <Chip className="bg-gray-100 text-gray-600">{platformLabel(it.platform)}</Chip>
                <Chip className="bg-red-50 text-red-600">
                  {REASON_LABEL[it.rejectReason] ?? it.rejectReason}
                </Chip>
                <a
                  href={it.url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex-1 truncate text-gray-700 hover:text-brand hover:underline"
                >
                  {it.title || it.url}
                </a>
                <span className="text-xs text-gray-400">{fmtDate(it.publishedAt)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
