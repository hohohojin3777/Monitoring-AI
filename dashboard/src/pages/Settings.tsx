import { useEffect, useState } from "react";
import { useAuth } from "../auth";
import { saveTarget, useTarget } from "../lib/data";
import { SITE_GROUPS } from "../lib/sites";
import type { Entity } from "../types";

export default function Settings() {
  const { role } = useAuth();
  const { data, loading } = useTarget();

  const [keywords, setKeywords] = useState<string[]>([]);
  const [kwInput, setKwInput] = useState("");
  const [entities, setEntities] = useState<Entity[]>([]);
  const [sites, setSites] = useState<string[]>([]);
  const [api, setApi] = useState({ naver: true, youtube: true, rss: true });
  const [everyMin, setEveryMin] = useState(30);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!data) return;
    setKeywords(data.keywords ?? []);
    setEntities(data.entities ?? []);
    setSites(data.sources?.sites ?? []);
    setApi({
      naver: data.sources?.naver ?? true,
      youtube: data.sources?.youtube ?? true,
      rss: data.sources?.rss ?? true,
    });
    setEveryMin(data.schedule?.collectEveryMin ?? 30);
  }, [data]);

  if (role !== "admin")
    return (
      <p className="py-16 text-center text-gray-400">설정은 관리자만 변경할 수 있습니다.</p>
    );
  if (loading) return <p className="py-16 text-center text-gray-400">불러오는 중…</p>;

  function addKeyword() {
    const v = kwInput.trim();
    if (v && !keywords.includes(v)) setKeywords([...keywords, v]);
    setKwInput("");
  }
  function toggleSite(key: string) {
    setSites(sites.includes(key) ? sites.filter((s) => s !== key) : [...sites, key]);
  }

  async function save() {
    setBusy(true);
    setSaved(false);
    try {
      await saveTarget({
        keywords,
        entities,
        sources: { ...api, sites },
        schedule: { ...(data?.schedule ?? {}), collectEveryMin: Number(everyMin) },
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">모니터링 설정</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          키워드·인물·수집 소스를 언제든 바꿀 수 있습니다. 변경은 다음 수집 주기부터 자동 반영됩니다.
        </p>
      </div>

      {/* 키워드 */}
      <section className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="font-semibold">검색 키워드</h2>
        <div className="mt-2 flex flex-wrap gap-2">
          {keywords.map((k) => (
            <span key={k} className="flex items-center gap-1 rounded-full bg-gray-100 px-3 py-1 text-sm">
              {k}
              <button onClick={() => setKeywords(keywords.filter((x) => x !== k))} className="text-gray-400 hover:text-red-500">
                ✕
              </button>
            </span>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <input
            value={kwInput}
            onChange={(e) => setKwInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addKeyword())}
            placeholder="키워드 입력 후 Enter"
            className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm outline-none focus:border-brand"
          />
          <button onClick={addKeyword} className="rounded bg-brand px-4 text-sm font-medium text-white hover:bg-brand-dark">
            추가
          </button>
        </div>
      </section>

      {/* 인물 */}
      <section className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="font-semibold">모니터링 인물</h2>
        <div className="mt-2 space-y-2">
          {entities.map((e, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                value={e.name}
                onChange={(ev) => setEntities(entities.map((x, j) => (j === i ? { ...x, name: ev.target.value } : x)))}
                placeholder="이름"
                className="w-32 rounded border border-gray-300 px-2 py-1.5 text-sm outline-none focus:border-brand"
              />
              <input
                value={e.role ?? ""}
                onChange={(ev) => setEntities(entities.map((x, j) => (j === i ? { ...x, role: ev.target.value } : x)))}
                placeholder="역할 (예: 당대표후보)"
                className="w-40 rounded border border-gray-300 px-2 py-1.5 text-sm outline-none focus:border-brand"
              />
              <input
                value={(e.aliases ?? []).join(", ")}
                onChange={(ev) =>
                  setEntities(
                    entities.map((x, j) =>
                      j === i ? { ...x, aliases: ev.target.value.split(",").map((s) => s.trim()).filter(Boolean) } : x
                    )
                  )
                }
                placeholder="별칭 (쉼표 구분)"
                className="flex-1 rounded border border-gray-300 px-2 py-1.5 text-sm outline-none focus:border-brand"
              />
              <button onClick={() => setEntities(entities.filter((_, j) => j !== i))} className="text-gray-400 hover:text-red-500">
                ✕
              </button>
            </div>
          ))}
          <button
            onClick={() => setEntities([...entities, { name: "", role: "", aliases: [] }])}
            className="text-sm text-brand hover:underline"
          >
            + 인물 추가
          </button>
        </div>
      </section>

      {/* 수집 소스 */}
      <section className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="font-semibold">수집 소스</h2>
        <div className="mt-2 flex flex-wrap gap-4 text-sm">
          {(["naver", "youtube", "rss"] as const).map((k) => (
            <label key={k} className="flex items-center gap-2">
              <input type="checkbox" checked={api[k]} onChange={(e) => setApi({ ...api, [k]: e.target.checked })} />
              {k === "naver" ? "네이버(뉴스·블로그·카페)" : k === "youtube" ? "유튜브" : "구글뉴스/RSS"}
            </label>
          ))}
        </div>
        <div className="mt-4 space-y-3">
          {SITE_GROUPS.map((g) => (
            <div key={g.label}>
              <p className="text-xs font-semibold text-gray-500">{g.label}</p>
              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1.5 text-sm">
                {g.sites.map((s) => (
                  <label key={s.key} className="flex items-center gap-1.5">
                    <input type="checkbox" checked={sites.includes(s.key)} onChange={() => toggleSite(s.key)} />
                    {s.name}
                    {s.login && <span className="text-[10px] text-orange-500">로그인</span>}
                    {s.tune && <span className="text-[10px] text-gray-400">튜닝</span>}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 수집 주기 */}
      <section className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="font-semibold">수집 주기</h2>
        <label className="mt-2 flex items-center gap-2 text-sm">
          <input
            type="number"
            min={5}
            value={everyMin}
            onChange={(e) => setEveryMin(Number(e.target.value))}
            className="w-24 rounded border border-gray-300 px-2 py-1.5 outline-none focus:border-brand"
          />
          분마다 수집
        </label>
        <p className="mt-1 text-xs text-gray-400">
          노트북 엔진(engine.main) 재시작 시 적용됩니다. 키워드/소스는 즉시(다음 주기) 반영.
        </p>
      </section>

      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={busy}
          className="rounded bg-brand px-5 py-2.5 font-semibold text-white hover:bg-brand-dark disabled:opacity-60"
        >
          {busy ? "저장 중…" : "저장"}
        </button>
        {saved && <span className="text-sm text-green-600">저장되었습니다 ✓</span>}
      </div>
    </div>
  );
}
