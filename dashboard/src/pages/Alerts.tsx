import { useState } from "react";
import { Link } from "react-router-dom";
import { useAlerts } from "../lib/data";
import { fmtDate } from "../lib/ui";
import type { Alert } from "../types";

const GRADE_META: Record<string, { label: string; chip: string; dot: string }> = {
  red:    { label: "위기",   chip: "bg-danger-red/10 text-danger-red border border-danger-red/30",     dot: "bg-danger-red" },
  orange: { label: "주의",   chip: "bg-warning-orange/10 text-warning-orange border border-warning-orange/30", dot: "bg-warning-orange" },
  yellow: { label: "관찰",   chip: "bg-yellow-50 text-yellow-700 border border-yellow-300",             dot: "bg-yellow-400" },
  none:   { label: "정보",   chip: "bg-gray-100 text-gray-500 border border-gray-200",                  dot: "bg-gray-300" },
};

// 임시 대응 상태 (실제 구현 시 Firestore에 저장)
const RESPONSE_STATUS = ["신규", "검토중", "보고완료", "대응중", "종료", "오탐"] as const;
type ResponseStatus = (typeof RESPONSE_STATUS)[number];

const STATUS_STYLE: Record<ResponseStatus, string> = {
  신규:    "bg-danger-red/10 text-danger-red font-bold",
  검토중:  "bg-warning-orange/10 text-warning-orange font-bold",
  보고완료:"bg-brand/10 text-brand font-bold",
  대응중:  "bg-purple-accent/10 text-purple-accent font-bold",
  종료:    "bg-gray-100 text-gray-400",
  오탐:    "bg-gray-100 text-gray-300",
};

const DECISION_LABELS = ["즉시 보고", "보고 참고", "모니터링", "무대응", "팩트체크 필요"];

function AlertCard({ alert }: { alert: Alert }) {
  const [status, setStatus] = useState<ResponseStatus>("신규");
  const [decision, setDecision] = useState<string>("");
  const m = GRADE_META[alert.grade] ?? GRADE_META.none;

  return (
    <div className={`rounded-xl border bg-white shadow-sm overflow-hidden ${
      alert.grade === "red" ? "border-danger-red/30" :
      alert.grade === "orange" ? "border-warning-orange/30" :
      "border-gray-200"
    }`}>
      {/* 카드 헤더 */}
      <div className={`px-4 py-3 flex items-center gap-2 border-b ${
        alert.grade === "red" ? "bg-danger-red/5 border-danger-red/20" :
        alert.grade === "orange" ? "bg-warning-orange/5 border-warning-orange/20" :
        "bg-gray-50 border-gray-100"
      }`}>
        <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${m.dot}`} />
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${m.chip}`}>{m.label}</span>
        <span className="font-semibold text-gray-800 text-sm flex-1">{alert.type || "위기 신호"}</span>
        <span className="text-[11px] text-gray-400">{fmtDate(alert.createdAt)}</span>
      </div>

      {/* 카드 본문 */}
      <div className="px-4 py-3 space-y-3">
        <p className="text-sm text-gray-700 leading-relaxed">{alert.summary}</p>

        {/* 메타 정보 */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg bg-gray-50 p-2">
            <p className="text-gray-400 mb-0.5">김민석 영향</p>
            <p className="text-gray-600 font-semibold">확인 필요</p>
          </div>
          <div className="rounded-lg bg-gray-50 p-2">
            <p className="text-gray-400 mb-0.5">전당대회 영향</p>
            <p className="text-gray-600 font-semibold">확인 필요</p>
          </div>
          {alert.platforms && alert.platforms.length > 0 && (
            <div className="rounded-lg bg-gray-50 p-2 col-span-2">
              <p className="text-gray-400 mb-0.5">확산 채널</p>
              <p className="text-gray-600">{alert.platforms.join(", ")}</p>
            </div>
          )}
        </div>

        {/* 대응 판단 */}
        <div>
          <p className="text-[10px] text-gray-400 mb-1 font-semibold">대응 판단</p>
          <div className="flex flex-wrap gap-1.5">
            {DECISION_LABELS.map((d) => (
              <button
                key={d}
                onClick={() => setDecision(decision === d ? "" : d)}
                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold transition border ${
                  decision === d
                    ? "bg-brand text-white border-brand"
                    : "bg-gray-50 text-gray-500 border-gray-200 hover:border-brand/40 hover:text-brand"
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 카드 푸터 */}
      <div className="px-4 py-2.5 border-t border-gray-100 flex items-center justify-between">
        <div className="flex gap-1.5">
          {RESPONSE_STATUS.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={`rounded-full px-2 py-0.5 text-[10px] transition border ${
                status === s
                  ? STATUS_STYLE[s] + " border-transparent"
                  : "bg-transparent text-gray-300 border-gray-200 hover:text-gray-500"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        {alert.clusterIds?.length && (
          <Link
            to={`/clusters/${alert.clusterIds[0]}`}
            className="text-xs text-brand hover:underline"
          >
            관련 이슈 →
          </Link>
        )}
      </div>
    </div>
  );
}

export default function Alerts() {
  const { data, loading } = useAlerts();
  const [filter, setFilter] = useState<string>("전체");

  const FILTERS = ["전체", "위기", "주의", "관찰", "정보"];
  const FILTER_TO_GRADE: Record<string, string> = {
    위기: "red", 주의: "orange", 관찰: "yellow", 정보: "none",
  };

  const filtered = filter === "전체"
    ? data
    : data.filter((a) => a.grade === FILTER_TO_GRADE[filter]);

  const counts: Record<string, number> = {
    전체: data.length,
    위기: data.filter((a) => a.grade === "red").length,
    주의: data.filter((a) => a.grade === "orange").length,
    관찰: data.filter((a) => a.grade === "yellow").length,
    정보: data.filter((a) => a.grade === "none").length,
  };

  return (
    <div className="space-y-5">
      {/* 헤더 */}
      <div>
        <h1 className="text-xl font-bold text-gray-900">위기·대응 관리판</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          시스템이 감지한 위기 신호를 등급별로 분류하고 대응 상태를 관리합니다.
        </p>
      </div>

      {/* KPI 요약 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "위기", grade: "red", count: counts.위기, color: "text-danger-red" },
          { label: "주의", grade: "orange", count: counts.주의, color: "text-warning-orange" },
          { label: "관찰", grade: "yellow", count: counts.관찰, color: "text-yellow-600" },
          { label: "전체", grade: "", count: counts.전체, color: "text-navy" },
        ].map((item) => (
          <div key={item.label} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-xs text-gray-500">{item.label} 알림</p>
            <p className={`text-2xl font-black mt-1 ${item.color}`}>{item.count}</p>
          </div>
        ))}
      </div>

      {/* 필터 */}
      <div className="flex gap-2 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition ${
              filter === f ? "bg-navy text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {f}
            <span className={`ml-1.5 text-xs ${filter === f ? "text-white/70" : "text-gray-400"}`}>
              {counts[f]}
            </span>
          </button>
        ))}
      </div>

      {/* 목록 */}
      {loading ? (
        <p className="py-16 text-center text-gray-400">불러오는 중…</p>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-200 p-12 text-center">
          <p className="text-gray-400">감지된 위기 신호가 없습니다.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {filtered.map((a) => <AlertCard key={a.id} alert={a} />)}
        </div>
      )}
    </div>
  );
}
