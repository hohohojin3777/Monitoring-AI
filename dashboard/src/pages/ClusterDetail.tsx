import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth";
import {
  publishResponse,
  recordAck,
  recordLinkClick,
  setClusterStatus,
  useAcks,
  useCluster,
  useClusterItems,
  useResponses,
} from "../lib/data";
import { Chip, GRADE_META, GradeDot, fmtDate, platformLabel } from "../lib/ui";
import type { CampResponse, ResponseLink, ResponseStep } from "../types";

const SENT_LABEL: Record<string, string> = {
  positive: "우호",
  neutral: "중립",
  negative: "부정",
  attack: "공격",
};

export default function ClusterDetail() {
  const { id = "" } = useParams();
  const { user, role } = useAuth();
  const cluster = useCluster(id);
  const { data: items } = useClusterItems(id);
  const { data: responses } = useResponses(id);
  const { data: acks } = useAcks(id);
  const isAdmin = role === "admin";
  const displayName = user?.email?.split("@")[0] ?? "회원";
  const resp = responses[0];

  // 회원이 상세 진입 시 읽음 기록
  useEffect(() => {
    if (id && user && !isAdmin) recordAck(id, user.uid, displayName).catch(() => {});
  }, [id, user, isAdmin, displayName]);

  if (cluster === null)
    return <p className="py-16 text-center text-gray-400">클러스터를 찾을 수 없습니다.</p>;

  const m = GRADE_META[cluster.grade] ?? GRADE_META.none;
  const s = cluster.stats;

  return (
    <div className="space-y-5">
      <Link to="/" className="text-sm text-gray-500 hover:text-brand">
        ← 이슈 목록
      </Link>

      {/* 헤더 */}
      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <div className="flex flex-wrap items-center gap-2">
          <GradeDot grade={cluster.grade} />
          <Chip className={m.chip}>{m.label}</Chip>
          {cluster.reactivated && <Chip className="bg-purple-100 text-purple-700">재발</Chip>}
          {(cluster.patterns ?? []).map((p) => (
            <Chip key={p} className="bg-slate-100 text-slate-600">
              {p}
            </Chip>
          ))}
          <span className="ml-auto text-xs text-gray-400">
            최초 {fmtDate(cluster.firstSeen)} · 최근 {fmtDate(cluster.lastSeen)}
          </span>
        </div>
        <h1 className="mt-3 text-lg font-bold leading-snug text-gray-900">{cluster.title}</h1>
        {cluster.summary && cluster.summary !== cluster.title && (
          <p className="mt-1 text-sm text-gray-600">{cluster.summary}</p>
        )}
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Metric label="총 글" value={cluster.itemCount ?? s?.posts ?? 0} />
          <Metric label="댓글" value={s?.comments ?? 0} />
          <Metric label="좋아요" value={s?.likes ?? 0} />
          <Metric label="매체" value={s?.platformCount ?? 0} />
        </div>
        {isAdmin && (
          <div className="mt-4 flex gap-2">
            <button
              onClick={() =>
                setClusterStatus(id, cluster.status === "resolved" ? "active" : "resolved")
              }
              className="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50"
            >
              {cluster.status === "resolved" ? "대응 재개" : "대응 완료 처리"}
            </button>
            <span className="self-center text-xs text-gray-400">
              상태: {cluster.status}
            </span>
          </div>
        )}
      </div>

      {/* 캠프 대응 */}
      <ResponsePanel
        clusterId={id}
        clusterTitle={cluster.title}
        isAdmin={isAdmin}
        resp={resp}
        uid={user!.uid}
        displayName={displayName}
      />

      {/* 회원 확인 현황 (관리자만) */}
      {isAdmin && (
        <section className="rounded-lg border border-gray-200 bg-white p-5">
          <h2 className="font-semibold text-gray-900">회원 확인 현황</h2>
          {acks.length === 0 ? (
            <p className="mt-2 text-sm text-gray-400">아직 확인한 회원이 없습니다.</p>
          ) : (
            <ul className="mt-2 divide-y text-sm">
              {acks.map((a) => (
                <li key={a.id} className="flex items-center gap-2 py-1.5">
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${
                      a.status === "acted" ? "bg-green-500" : "bg-gray-300"
                    }`}
                  />
                  <span className="font-medium">{a.displayName ?? a.uid}</span>
                  <span className="text-gray-400">
                    {a.status === "acted" ? "대응함" : "읽음"}
                  </span>
                  {!!a.clickedLinks?.length && (
                    <span className="text-xs text-gray-400">
                      · 링크 {a.clickedLinks.length}개 클릭
                    </span>
                  )}
                  <span className="ml-auto text-xs text-gray-400">{fmtDate(a.readAt)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* 글 목록 */}
      <section className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="font-semibold text-gray-900">글 목록 ({items.length})</h2>
        <ul className="mt-3 divide-y">
          {items.map((it) => (
            <li key={it.id} className="py-2.5">
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <Chip className="bg-gray-100 text-gray-600">{platformLabel(it.platform)}</Chip>
                {it.sentiment && (
                  <Chip
                    className={
                      it.sentiment === "negative" || it.sentiment === "attack"
                        ? "bg-red-50 text-red-600"
                        : it.sentiment === "positive"
                          ? "bg-green-50 text-green-600"
                          : "bg-gray-50 text-gray-500"
                    }
                  >
                    {SENT_LABEL[it.sentiment] ?? it.sentiment}
                  </Chip>
                )}
                <span>{fmtDate(it.publishedAt)}</span>
                {it.author && <span>· {it.author}</span>}
              </div>
              <a
                href={it.url}
                target="_blank"
                rel="noreferrer"
                className="mt-0.5 block font-medium text-gray-800 hover:text-brand hover:underline"
              >
                {it.title || it.url}
              </a>
            </li>
          ))}
          {items.length === 0 && (
            <li className="py-3 text-sm text-gray-400">표시할 글이 없습니다.</li>
          )}
        </ul>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-gray-100 bg-gray-50 p-2.5 text-center">
      <div className="text-lg font-bold text-gray-900">{value.toLocaleString()}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}

// ── 대응 패널 (관리자 편집 / 회원 조회) ──────────────────────
function ResponsePanel({
  clusterId,
  clusterTitle,
  isAdmin,
  resp,
  uid,
  displayName,
}: {
  clusterId: string;
  clusterTitle: string;
  isAdmin: boolean;
  resp?: CampResponse;
  uid: string;
  displayName: string;
}) {
  const [editing, setEditing] = useState(false);

  // 회원 뷰: 발행된 대응만 표시
  if (!isAdmin) {
    if (!resp || resp.status !== "published")
      return (
        <section className="rounded-lg border border-dashed border-gray-300 bg-white p-5 text-sm text-gray-400">
          아직 등록된 캠프 대응이 없습니다. 관리자가 대응 방안을 정하면 이곳에 표시됩니다.
        </section>
      );
    return (
      <ResponseView
        resp={resp}
        clusterId={clusterId}
        uid={uid}
        displayName={displayName}
      />
    );
  }

  // 관리자 뷰
  if (editing || !resp)
    return (
      <ResponseEditor
        clusterId={clusterId}
        clusterTitle={clusterTitle}
        uid={uid}
        initial={resp}
        onDone={() => setEditing(false)}
      />
    );

  return (
    <div>
      <ResponseView resp={resp} clusterId={clusterId} uid={uid} displayName={displayName} readOnlyLinks />
      <button
        onClick={() => setEditing(true)}
        className="mt-2 rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50"
      >
        대응 수정
      </button>
    </div>
  );
}

function ResponseView({
  resp,
  clusterId,
  uid,
  displayName,
  readOnlyLinks = false,
}: {
  resp: CampResponse;
  clusterId: string;
  uid: string;
  displayName: string;
  readOnlyLinks?: boolean;
}) {
  async function clickLink(l: ResponseLink) {
    if (!readOnlyLinks) await recordLinkClick(clusterId, uid, displayName, l.url).catch(() => {});
    window.open(l.url, "_blank", "noopener");
  }
  return (
    <section className="rounded-lg border-2 border-brand/30 bg-orange-50/40 p-5">
      <div className="flex items-center gap-2">
        <h2 className="font-bold text-gray-900">캠프 대응</h2>
        <Chip className={resp.status === "published" ? "bg-green-100 text-green-700" : "bg-gray-200 text-gray-600"}>
          {resp.status === "published" ? "발행됨" : "초안"}
        </Chip>
        {resp.aiSuggested && <Chip className="bg-blue-100 text-blue-700">AI 추천 기반</Chip>}
      </div>

      {resp.plan && <p className="mt-3 whitespace-pre-wrap text-sm text-gray-800">{resp.plan}</p>}

      {!!resp.steps?.length && (
        <ol className="mt-3 space-y-1.5">
          {resp.steps
            .slice()
            .sort((a, b) => a.order - b.order)
            .map((st, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="flex h-5 w-5 flex-none items-center justify-center rounded-full bg-brand text-xs font-bold text-white">
                  {st.order}
                </span>
                <span className="text-gray-800">{st.text}</span>
              </li>
            ))}
        </ol>
      )}

      {!!resp.links?.length && (
        <div className="mt-4">
          <p className="mb-1 text-xs font-semibold text-gray-500">관련 링크 (클릭하여 대응)</p>
          <div className="flex flex-wrap gap-2">
            {resp.links.map((l, i) => (
              <button
                key={i}
                onClick={() => clickLink(l)}
                className="rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark"
              >
                {l.title || l.url} ↗
              </button>
            ))}
          </div>
        </div>
      )}

      {resp.lawCheckRequired && (
        <p className="mt-3 text-xs text-red-600">
          ※ 외부 발송 콘텐츠는 캠프 자문 변호사 사전 검토가 필요합니다.
        </p>
      )}
    </section>
  );
}

function ResponseEditor({
  clusterId,
  clusterTitle,
  uid,
  initial,
  onDone,
}: {
  clusterId: string;
  clusterTitle: string;
  uid: string;
  initial?: CampResponse;
  onDone: () => void;
}) {
  const [plan, setPlan] = useState(initial?.plan ?? "");
  const [steps, setSteps] = useState<ResponseStep[]>(initial?.steps ?? [{ order: 1, text: "" }]);
  const [links, setLinks] = useState<ResponseLink[]>(initial?.links ?? []);
  const [lawCheck, setLawCheck] = useState(initial?.lawCheckRequired ?? true);
  const [busy, setBusy] = useState(false);

  function aiTemplate() {
    setPlan(
      `[${clusterTitle}] 대응 기조\n- 사실관계 확인 후 일관된 메시지로 대응\n- 과잉대응 금지, 근거 자료 첨부\n\n※ AI 추천 초안입니다. 검토·수정 후 발행하세요.`
    );
    setSteps([
      { order: 1, text: "사실관계 즉시 확인 (담당: 공보팀)" },
      { order: 2, text: "대응 메시지 초안 작성 + 변호사 검토" },
      { order: 3, text: "채널별 게시 및 회원 공유" },
    ]);
    setLawCheck(true);
  }

  async function save(status: "draft" | "published") {
    setBusy(true);
    try {
      await publishResponse(
        clusterId,
        {
          status,
          plan,
          steps: steps.filter((s) => s.text.trim()).map((s, i) => ({ ...s, order: i + 1 })),
          links: links.filter((l) => l.url.trim()),
          lawCheckRequired: lawCheck,
          aiSuggested: initial?.aiSuggested ?? false,
          createdBy: uid,
        },
        uid
      );
      onDone();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-lg border-2 border-brand/40 bg-white p-5">
      <div className="flex items-center gap-2">
        <h2 className="font-bold text-gray-900">캠프 대응 작성</h2>
        <button
          onClick={aiTemplate}
          className="ml-auto rounded border border-blue-300 px-2.5 py-1 text-xs text-blue-700 hover:bg-blue-50"
        >
          AI 추천 (변호사 검토 필수)
        </button>
      </div>

      <label className="mt-3 block text-sm font-medium">대응 방안</label>
      <textarea
        value={plan}
        onChange={(e) => setPlan(e.target.value)}
        rows={4}
        placeholder="이 이슈에 대한 대응 기조를 적으세요."
        className="mt-1 w-full rounded border border-gray-300 p-2 text-sm outline-none focus:border-brand"
      />

      <label className="mt-4 block text-sm font-medium">대응 순서</label>
      <div className="mt-1 space-y-2">
        {steps.map((st, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="text-sm text-gray-400">{i + 1}</span>
            <input
              value={st.text}
              onChange={(e) =>
                setSteps(steps.map((s, j) => (j === i ? { ...s, text: e.target.value } : s)))
              }
              placeholder="단계별 대응 내용"
              className="flex-1 rounded border border-gray-300 px-2 py-1.5 text-sm outline-none focus:border-brand"
            />
            <button
              onClick={() => setSteps(steps.filter((_, j) => j !== i))}
              className="text-gray-400 hover:text-red-500"
            >
              ✕
            </button>
          </div>
        ))}
        <button
          onClick={() => setSteps([...steps, { order: steps.length + 1, text: "" }])}
          className="text-sm text-brand hover:underline"
        >
          + 단계 추가
        </button>
      </div>

      <label className="mt-4 block text-sm font-medium">관련 링크</label>
      <div className="mt-1 space-y-2">
        {links.map((l, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              value={l.title}
              onChange={(e) =>
                setLinks(links.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))
              }
              placeholder="링크 제목"
              className="w-32 rounded border border-gray-300 px-2 py-1.5 text-sm outline-none focus:border-brand"
            />
            <input
              value={l.url}
              onChange={(e) =>
                setLinks(links.map((x, j) => (j === i ? { ...x, url: e.target.value } : x)))
              }
              placeholder="https://..."
              className="flex-1 rounded border border-gray-300 px-2 py-1.5 text-sm outline-none focus:border-brand"
            />
            <button
              onClick={() => setLinks(links.filter((_, j) => j !== i))}
              className="text-gray-400 hover:text-red-500"
            >
              ✕
            </button>
          </div>
        ))}
        <button
          onClick={() => setLinks([...links, { title: "", url: "" }])}
          className="text-sm text-brand hover:underline"
        >
          + 링크 추가
        </button>
      </div>

      <label className="mt-4 flex items-center gap-2 text-sm">
        <input type="checkbox" checked={lawCheck} onChange={(e) => setLawCheck(e.target.checked)} />
        외부 발송 콘텐츠 변호사 검토 필요 표시
      </label>

      <div className="mt-5 flex gap-2">
        <button
          onClick={() => save("published")}
          disabled={busy}
          className="rounded bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-dark disabled:opacity-60"
        >
          발행 (회원 공유)
        </button>
        <button
          onClick={() => save("draft")}
          disabled={busy}
          className="rounded border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
        >
          초안 저장
        </button>
        {initial && (
          <button onClick={onDone} className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700">
            취소
          </button>
        )}
      </div>
    </section>
  );
}
