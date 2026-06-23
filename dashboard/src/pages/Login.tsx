import { useState } from "react";
import { useAuth } from "../auth";

export default function Login() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      if (mode === "login") await login(email, pw);
      else await signup(email, pw);
    } catch (e: unknown) {
      setErr(mode === "login" ? "로그인 실패. 이메일/비밀번호를 확인하세요." : "가입 실패.");
      console.error(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-navy px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-xl bg-white p-7 shadow-xl"
      >
        <h1 className="text-xl font-bold">
          <span className="text-brand">여론</span> 모니터링
        </h1>
        <p className="mt-1 text-sm text-gray-500">승인된 멤버 전용</p>

        <label className="mt-5 block text-sm font-medium">이메일</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="example@camp.kr"
          className="mt-1 w-full rounded border border-gray-300 px-3 py-2 outline-none focus:border-brand"
        />

        <label className="mt-4 block text-sm font-medium">비밀번호</label>
        <input
          type="password"
          required
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          className="mt-1 w-full rounded border border-gray-300 px-3 py-2 outline-none focus:border-brand"
        />

        {err && <p className="mt-3 text-sm text-red-600">{err}</p>}

        <button
          type="submit"
          disabled={busy}
          className="mt-5 w-full rounded bg-brand py-2.5 font-semibold text-white hover:bg-brand-dark disabled:opacity-60"
        >
          {busy ? "처리 중…" : mode === "login" ? "로그인" : "가입"}
        </button>

        <button
          type="button"
          onClick={() => setMode(mode === "login" ? "signup" : "login")}
          className="mt-3 w-full text-center text-xs text-gray-500 hover:text-gray-700"
        >
          {mode === "login" ? "계정이 없으신가요? 가입" : "이미 계정이 있으신가요? 로그인"}
        </button>
        <p className="mt-3 text-center text-[11px] text-gray-400">
          가입 후 관리자 승인(멤버 등록)이 되어야 데이터가 보입니다.
        </p>
      </form>
    </div>
  );
}
