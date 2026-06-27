import { useState } from "react";
import type { Timestamp } from "firebase/firestore";
import { useRejected } from "../lib/data";
import { Chip, fmtDate, platformLabel } from "../lib/ui";

const REASON_LABEL: Record<string, string> = {
  duplicate:     "중복",
  old_date:      "기간 초과",
  no_date:       "날짜 미상",
  irrelevant:    "무관",
  noise:         "노이즈/광고",
  hallucination: "환각 차단",
};

const REASON_COLOR: Record<string, string> = {
  duplicate:     "bg-gray-100 text-gray-600",
  old_date:      "bg-yellow-50 text-yellow-700",
  no_date:       "bg-yellow-50 text-yellow-700",
  irrelevant:    "bg-red-50 text-red-600",
  noise:         "bg-orange-50 text-orange-600",
  hallucination: "bg-purple-50 text-purple-700",
};

type RejectedItem = {
  id: string;
  platform?: string;
  title?: string;
  url?: string;
  publishedAt?: Timestamp | null;
  collectedAt?: Timestamp | null;
  rejectReason?: string;
  matchedEntities?: string[];
  keyword?: string;
  content?: string;
};

type PendingAction = {
  type: "recover" | "elevate" | "keyword_exception" | "domain_exception" | "exclude";
  itemId: string;
};

function ActionButtons({
  item,
  onAction,
}: {
  item: RejectedItem;
  onAction: (action: PendingAction) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      <button
        onClick={() => onAction({ type: "recover", itemId: item.id })}
        className="rounded px-2 py-0.5 text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 transition"
      >
        복구
      </button>
      <button
        onClick={() => onAction({ type: "elevate", itemId: item.id })}
        className="rounded px-2 py-0.5 text-xs font-medium bg-green-50 text-green-700 hover:bg-green-100 border border-green-200 transition"
      >
        이슈로 승격
      </button>
      <button
        onClick={() => onAction({ type: "keyword_exception", itemId: item.id })}
        className="rounded px-2 py-0.5 text-xs font-medium bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 transition"
      >
        키워드 예외 등록
      </button>
      <button
        onClick={() => onAction({ type: "domain_exception", itemId: item.id })}
        className="rounded px-2 py-0.5 text-xs font-medium bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200 transition"
      >
        도메인 예외 등록
      </button>
      <button
        onClick={() => onAction({ type: "exclude", itemId: item.id })}
        className="rounded px-2 py-0.5 text-xs font-medium bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 transition"
      >
        완전 제외
      </button>
    </div>
  );
}

const ACTION_LABEL: Record<PendingAction["type"], string> = {
  recover:           "복구 대기",
  elevate:           "이슈 승격 대기",
  keyword_exception: "키워드 예외 검토 대기",
  domain_exception:  "도메인 예외 검토 대기",
  exclude:           "완전 제외 대기",
};

export default function Rejected() {
  const { data, loading } = useRejected();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [pending, setPending] = useState<Map<string, PendingAction>>(new Map());
  const [filterReason, setFilterReason] = useState<string>("all");

  function toggleExpand(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function handleAction(action: PendingAction) {
    setPending((prev) => new Map(prev).set(action.itemId, action));
  }

  const filtered = filterReason === "all"
    ? data
    : data.filter((it) => (it as RejectedItem).rejectReason === filterReason);

  const reasonCounts = data.reduce<Record<string, number>>((acc, it) => {
    const r = (it as RejectedItem).rejectReason ?? "unknown";
    acc[r] = (acc[r] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-gray-900">거부 검토</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          필터에 의해 제외된 글을 확인하고, 오탐을 복구하거나 필터 기준을 보정하는 관리 페이지입니다.
        </p>
      </div>

      {/* 필터 탭 */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setFilterReason("all")}
          className={`rounded-full px-3 py-1 text-xs font-semibold border transition ${
            filterReason === "all"
              ? "bg-gray-800 text-white border-gray-800"
              : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
          }`}
        >
          전체 {data.length}
        </button>
        {Object.entries(REASON_LABEL).map(([key, label]) =>
          reasonCounts[key] ? (
            <button
              key={key}
              onClick={() => setFilterReason(key)}
              className={`rounded-full px-3 py-1 text-xs font-semibold border transition ${
                filterReason === key
                  ? "bg-gray-800 text-white border-gray-800"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}
            >
              {label} {reasonCounts[key]}
            </button>
          ) : null
        )}
      </div>

      {/* 액션 대기 안내 */}
      {pending.size > 0 && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
          <span className="font-semibold">검토 대기 {pending.size}건</span> — 액션은 pending 상태로 저장됩니다.
          키워드/도메인 예외는 검토 후 적용됩니다.
          <button
            onClick={() => setPending(new Map())}
            className="ml-3 text-xs underline text-yellow-700"
          >
            초기화
          </button>
        </div>
      )}

      <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
        {loading ? (
          <p className="py-12 text-center text-gray-400">불러오는 중…</p>
        ) : filtered.length === 0 ? (
          <p className="py-12 text-center text-gray-400">거부된 글이 없습니다.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {filtered.map((it) => {
              const item = it as RejectedItem;
              const isExpanded = expanded.has(item.id);
              const pendingAction = pending.get(item.id);
              const reasonKey = item.rejectReason ?? "";

              return (
                <li key={item.id} className="px-4 py-3 text-sm">
                  {/* 상단 행 */}
                  <div className="flex items-start gap-2">
                    <Chip className="bg-gray-100 text-gray-600 shrink-0">
                      {platformLabel(item.platform ?? "")}
                    </Chip>
                    <Chip className={`shrink-0 ${REASON_COLOR[reasonKey] ?? "bg-red-50 text-red-600"}`}>
                      {REASON_LABEL[reasonKey] ?? reasonKey}
                    </Chip>

                    {pendingAction && (
                      <Chip className="shrink-0 bg-yellow-100 text-yellow-700">
                        {ACTION_LABEL[pendingAction.type]}
                      </Chip>
                    )}

                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex-1 min-w-0 truncate text-gray-700 hover:text-brand hover:underline"
                    >
                      {item.title || item.url}
                    </a>

                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-gray-400">{fmtDate(item.publishedAt)}</span>
                      <button
                        onClick={() => toggleExpand(item.id ?? "")}
                        className="text-xs text-gray-400 hover:text-gray-600"
                      >
                        {isExpanded ? "▲" : "▼"}
                      </button>
                    </div>
                  </div>

                  {/* 확장 영역 */}
                  {isExpanded && (
                    <div className="mt-3 space-y-2 pl-2 border-l-2 border-gray-100">
                      {/* 매칭된 키워드/엔티티 */}
                      {(item.matchedEntities?.length ?? 0) > 0 && (
                        <div className="flex flex-wrap gap-1">
                          <span className="text-xs text-gray-400">매칭:</span>
                          {item.matchedEntities!.map((e) => (
                            <span key={e} className="rounded bg-brand/10 px-1.5 py-0.5 text-xs text-brand">
                              {e}
                            </span>
                          ))}
                        </div>
                      )}
                      {item.keyword && (
                        <div className="text-xs text-gray-400">
                          검색 키워드: <span className="text-gray-600">{item.keyword}</span>
                        </div>
                      )}
                      {/* 본문 미리보기 */}
                      {item.content && (
                        <p className="text-xs text-gray-500 line-clamp-3 leading-relaxed">
                          {item.content}
                        </p>
                      )}
                      {/* 수집일 */}
                      <div className="text-xs text-gray-400">
                        수집: {fmtDate(item.collectedAt)}
                      </div>
                      {/* 액션 버튼 */}
                      <ActionButtons item={item} onAction={handleAction} />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
