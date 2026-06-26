import { useState } from "react";
import { useAuth } from "../auth";

// 이메일이면 그대로, 아이디면 @monitor.local 붙임
function toEmail(input: string) {
  const v = input.trim().toLowerCase();
  return v.includes("@") ? v : `${v}@monitor.local`;
}

export default function Login() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (!id.trim()) return setErr("아이디 또는 이메일을 입력하세요.");
    if (mode === "signup" && pw !== pw2) return setErr("비밀번호가 일치하지 않습니다.");
    setBusy(true);
    try {
      const email = toEmail(id);
      const displayName = id.trim().includes("@") ? id.trim().split("@")[0] : id.trim();
      if (mode === "login") await login(email, pw);
      else await signup(email, pw, displayName);
    } catch (e: unknown) {
      const msg = (e as { code?: string })?.code;
      if (msg === "auth/user-not-found" || msg === "auth/wrong-password" || msg === "auth/invalid-credential")
        setErr("아이디 또는 비밀번호가 올바르지 않습니다.");
      else if (msg === "auth/email-already-in-use")
        setErr("이미 사용 중인 아이디입니다.");
      else if (msg === "auth/weak-password")
        setErr("비밀번호는 6자 이상이어야 합니다.");
      else
        setErr(mode === "login" ? "로그인 실패." : "가입 실패.");
      console.error(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-navy px-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-xl bg-white p-7 shadow-xl">
        <h1 className="text-xl font-bold">
          <span className="text-brand">여론</span> 모니터링
        </h1>
        <p className="mt-1 text-sm text-gray-500">승인된 멤버 전용</p>

        <label className="mt-5 block text-sm font-medium">아이디 또는 이메일</label>
        <input
          type="text"
          required
          value={id}
          onChange={(e) => setId(e.target.value)}
          placeholder="아이디 또는 이메일 주소"
          autoComplete="username"
          className="mt-1 w-full rounded border border-gray-300 px-3 py-2 outline-none focus:border-brand"
        />

        <label className="mt-4 block text-sm font-medium">비밀번호</label>
        <input
          type="password"
          required
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          className="mt-1 w-full rounded border border-gray-300 px-3 py-2 outline-none focus:border-brand"
        />

        {mode === "signup" && (
          <>
            <label className="mt-4 block text-sm font-medium">비밀번호 확인</label>
            <input
              type="password"
              required
              value={pw2}
              onChange={(e) => setPw2(e.target.value)}
              autoComplete="new-password"
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 outline-none focus:border-brand"
            />
          </>
        )}

        {err && <p className="mt-3 text-sm text-red-600">{err}</p>}

        <button
          type="submit"
          disabled={busy}
          className="mt-5 w-full rounded bg-brand py-2.5 font-semibold text-white hover:bg-brand-dark disabled:opacity-60"
        >
          {busy ? "처리 중…" : mode === "login" ? "로그인" : "가입 신청"}
        </button>

        <button
          type="button"
          onClick={() => { setMode(mode === "login" ? "signup" : "login"); setErr(""); }}
          className="mt-3 w-full text-center text-xs text-gray-500 hover:text-gray-700"
        >
          {mode === "login" ? "계정이 없으신가요? 가입 신청" : "이미 계정이 있으신가요? 로그인"}
        </button>
        {mode === "signup" && (
          <p className="mt-3 text-center text-[11px] text-gray-400">
            가입 후 관리자 승인이 되어야 데이터가 보입니다.
          </p>
        )}
      </form>
    </div>
  );
}
