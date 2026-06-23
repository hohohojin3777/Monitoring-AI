import { NavLink } from "react-router-dom";
import { useAuth } from "../auth";

const NAV = [
  { to: "/", label: "이슈" },
  { to: "/alerts", label: "위기 알림" },
  { to: "/reports", label: "보고서" },
  { to: "/keywords", label: "키워드" },
  { to: "/authors", label: "작성자 영향력" },
  { to: "/rejected", label: "거부 검토" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, role, logout } = useAuth();
  const nav = role === "admin" ? [...NAV, { to: "/settings", label: "설정" }] : NAV;
  return (
    <div className="min-h-full">
      <header className="bg-navy text-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="text-lg font-bold">
            <span className="text-brand">여론</span> 모니터링
          </span>
          <nav className="flex flex-1 flex-wrap items-center gap-1 text-sm">
            {nav.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                className={({ isActive }) =>
                  `rounded px-3 py-1.5 transition ${
                    isActive ? "bg-brand text-white" : "text-gray-200 hover:bg-navy-light"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3 text-xs text-gray-300">
            {role === "admin" && (
              <span className="rounded bg-brand/20 px-2 py-0.5 text-brand">관리자</span>
            )}
            <span className="hidden sm:inline">{user?.email}</span>
            <button
              onClick={() => logout()}
              className="rounded border border-white/30 px-2 py-1 hover:bg-white/10"
            >
              로그아웃
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}
