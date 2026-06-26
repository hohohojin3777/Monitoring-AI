import { NavLink } from "react-router-dom";
import { useAuth } from "../auth";

const NAV = [
  { to: "/", label: "이슈" },
  { to: "/polls", label: "여론조사" },
  { to: "/alerts", label: "위기 알림" },
  { to: "/reports", label: "보고서" },
  { to: "/keywords", label: "키워드" },
  { to: "/allies", label: "지지세력" },
  { to: "/authors", label: "작성자 영향력" },
  { to: "/rejected", label: "거부 검토" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, role, logout } = useAuth();
  const nav = role === "admin" ? [...NAV, { to: "/members", label: "멤버 관리" }, { to: "/settings", label: "설정" }] : NAV;
  return (
    <div className="min-h-full">
      <header className="bg-navy text-white">
        <div className="mx-auto max-w-7xl px-4">
          {/* 로고 + 사용자 — 한 줄 */}
          <div className="flex items-center justify-between py-2.5">
            <span className="text-base font-bold tracking-tight">
              <span className="text-brand">H</span>O<span className="text-brand">rizon</span><span className="text-gray-300">0817</span>
            </span>
            <div className="flex items-center gap-2 text-xs text-gray-300">
              {role === "admin" && (
                <span className="rounded bg-brand/20 px-2 py-0.5 text-brand">관리자</span>
              )}
              <span className="hidden sm:inline max-w-[140px] truncate">{user?.email}</span>
              <button
                onClick={() => logout()}
                className="rounded border border-white/30 px-2 py-1 hover:bg-white/10"
              >
                로그아웃
              </button>
            </div>
          </div>
          {/* 네비게이션 — 가로 스크롤 (모바일 메뉴 세로 쌓임 제거) */}
          <nav className="flex gap-0.5 overflow-x-auto" style={{ scrollbarWidth: "none" }}>
            {nav.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                className={({ isActive }) =>
                  `shrink-0 whitespace-nowrap rounded-t px-3 py-2 text-sm transition ${
                    isActive ? "bg-brand text-white" : "text-gray-300 hover:bg-navy-light"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}
