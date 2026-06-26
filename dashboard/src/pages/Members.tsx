import { useEffect, useState } from "react";
import { collection, onSnapshot, doc, setDoc, deleteDoc, serverTimestamp } from "firebase/firestore";
import { db, DEFAULT_TARGET } from "../firebase";
import { useAuth } from "../auth";

const T = DEFAULT_TARGET;

interface MemberRequest {
  id: string;
  email: string;
  displayName?: string;
  requestedAt?: { toDate(): Date };
}
interface Member {
  id: string;
  email: string;
  displayName?: string;
  role: "admin" | "member";
  joinedAt?: { toDate(): Date };
}

function fmtDt(ts?: { toDate(): Date } | null) {
  if (!ts) return "-";
  try {
    return ts.toDate().toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch { return "-"; }
}

export default function Members() {
  const { role: myRole } = useAuth();
  const [requests, setRequests] = useState<MemberRequest[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [addEmail, setAddEmail] = useState("");
  const [addName, setAddName] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    const unsub1 = onSnapshot(
      collection(db, "targets", T, "memberRequests"),
      (snap) => {
        const list = snap.docs.map((d) => ({ id: d.id, ...d.data() }) as MemberRequest);
        list.sort((a, b) => (b.requestedAt?.toDate?.()?.getTime() ?? 0) - (a.requestedAt?.toDate?.()?.getTime() ?? 0));
        setRequests(list);
      },
      (err) => console.error("[Members] memberRequests 읽기 실패:", err)
    );
    const unsub2 = onSnapshot(
      collection(db, "targets", T, "members"),
      (snap) => setMembers(snap.docs.map((d) => ({ id: d.id, ...d.data() }) as Member)),
      () => {}
    );
    return () => { unsub1(); unsub2(); };
  }, []);

  if (myRole !== "admin") {
    return <p className="py-16 text-center text-gray-400">관리자만 접근할 수 있습니다.</p>;
  }

  async function approve(req: MemberRequest) {
    setBusy(req.id);
    await setDoc(doc(db, "targets", T, "members", req.id), {
      role: "member",
      email: req.email,
      displayName: req.displayName ?? req.email,
      joinedAt: serverTimestamp(),
    });
    await deleteDoc(doc(db, "targets", T, "memberRequests", req.id));
    setBusy(null);
  }

  async function reject(req: MemberRequest) {
    setBusy(req.id);
    await deleteDoc(doc(db, "targets", T, "memberRequests", req.id));
    setBusy(null);
  }

  async function changeRole(m: Member, newRole: "admin" | "member") {
    setBusy(m.id);
    await setDoc(doc(db, "targets", T, "members", m.id), { role: newRole }, { merge: true });
    setBusy(null);
  }

  async function removeMember(m: Member) {
    if (!confirm(`${m.email} 멤버를 삭제하시겠습니까?`)) return;
    setBusy(m.id);
    await deleteDoc(doc(db, "targets", T, "members", m.id));
    setBusy(null);
  }

  async function addDirect() {
    if (!addEmail.trim()) return;
    const fakeUid = `manual_${Date.now()}`;
    setBusy("add");
    await setDoc(doc(db, "targets", T, "memberRequests", fakeUid), {
      email: addEmail.trim(),
      displayName: addName.trim() || addEmail.trim(),
      requestedAt: serverTimestamp(),
      manualAdd: true,
    });
    setAddEmail("");
    setAddName("");
    setMsg("신청 목록에 추가했습니다. 해당 사용자가 로그인하면 UID로 연결되므로 승인 후 직접 계정 등록이 필요합니다.");
    setTimeout(() => setMsg(""), 5000);
    setBusy(null);
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">멤버 관리</h1>
        <p className="mt-0.5 text-sm text-gray-500">가입 신청 승인·거절, 역할 변경, 멤버 추가/삭제.</p>
      </div>

      {/* 가입 신청 목록 */}
      <section className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="font-semibold">
          가입 신청
          {requests.length > 0 && (
            <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
              {requests.length}
            </span>
          )}
        </h2>
        {requests.length === 0 ? (
          <p className="mt-3 text-sm text-gray-400">대기 중인 신청이 없습니다.</p>
        ) : (
          <div className="mt-3 space-y-2">
            {requests.map((r) => (
              <div key={r.id} className="flex items-center gap-3 rounded border border-gray-100 p-3">
                <div className="flex-1 min-w-0">
                  <p className="truncate text-sm font-medium">{r.displayName || r.email}</p>
                  <p className="truncate text-xs text-gray-400">{r.email} · {fmtDt(r.requestedAt)}</p>
                </div>
                <button
                  onClick={() => approve(r)}
                  disabled={busy === r.id}
                  className="rounded bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
                >
                  승인
                </button>
                <button
                  onClick={() => reject(r)}
                  disabled={busy === r.id}
                  className="rounded border border-gray-200 px-3 py-1.5 text-sm text-gray-600 hover:border-red-300 hover:text-red-600 disabled:opacity-50"
                >
                  거절
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 직접 추가 */}
      <section className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="font-semibold">멤버 직접 추가</h2>
        <p className="mt-1 text-xs text-gray-400">
          해당 이메일로 먼저 가입(회원가입)한 뒤, 신청 목록에서 승인하거나 아래에서 직접 등록하세요.
        </p>
        <div className="mt-3 flex gap-2">
          <input
            value={addName}
            onChange={(e) => setAddName(e.target.value)}
            placeholder="이름 (선택)"
            className="w-32 rounded border border-gray-300 px-3 py-2 text-sm outline-none focus:border-brand"
          />
          <input
            value={addEmail}
            onChange={(e) => setAddEmail(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addDirect()}
            placeholder="이메일"
            className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm outline-none focus:border-brand"
          />
          <button
            onClick={addDirect}
            disabled={busy === "add"}
            className="rounded bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
          >
            추가
          </button>
        </div>
        {msg && <p className="mt-2 text-xs text-amber-600">{msg}</p>}
      </section>

      {/* 현재 멤버 목록 */}
      <section className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="font-semibold">현재 멤버 <span className="text-sm font-normal text-gray-400">({members.length}명)</span></h2>
        <div className="mt-3 space-y-2">
          {members.map((m) => (
            <div key={m.id} className="flex items-center gap-3 rounded border border-gray-100 p-3">
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-medium">{m.displayName || m.email}</p>
                <p className="truncate text-xs text-gray-400">{m.email} · 가입 {fmtDt(m.joinedAt)}</p>
              </div>
              <select
                value={m.role}
                onChange={(e) => changeRole(m, e.target.value as "admin" | "member")}
                disabled={busy === m.id}
                className="rounded border border-gray-200 px-2 py-1.5 text-sm outline-none focus:border-brand"
              >
                <option value="member">일반</option>
                <option value="admin">관리자</option>
              </select>
              <button
                onClick={() => removeMember(m)}
                disabled={busy === m.id}
                className="text-gray-300 hover:text-red-500 disabled:opacity-50"
                title="삭제"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
