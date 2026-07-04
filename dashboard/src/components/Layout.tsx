import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { collection, onSnapshot } from "firebase/firestore";
import { db, DEFAULT_TARGET } from "../firebase";
import { useAuth } from "../auth";

// 실무자용 메인 메뉴
const NAV_MAIN = [
  { to: "/",         label: "종합상황판", end: true },
  { to: "/issues",   label: "이슈 분석" },
  { to: "/polls",    label: "여론조사" },
  { to: "/alerts",   label: "위기·대응" },
  { to: "/reports",  label: "보고서" },
  { to: "/allies",   label: "세력지도" },
];

// 실무자 보조 메뉴 (서브)
const NAV_SUB = [
  { to: "/keywords", label: "키워드" },
  { to: "/authors",  label: "작성자" },
  { to: "/rejected", label: "거부검토" },
];

// 관리자 전용
const NAV_ADMIN = [
  { to: "/members",  label: "멤버 관리" },
  { to: "/settings", label: "설정" },
];

function NavItem({ to, label, end }: { to: string; label: string; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `shrink-0 whitespace-nowrap rounded-t px-3 py-2 text-sm font-medium transition ${
          isActive
            ? "bg-brand text-white"
            : "text-gray-300 hover:bg-navy-light hover:text-white"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, role, logout } = useAuth();
  const isAdmin = role === "admin";
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    if (!isAdmin) return;
    const unsub = onSnapshot(
      collection(db, "targets", DEFAULT_TARGET, "memberRequests"),
      (snap) => setPendingCount(snap.size),
      () => {}
    );
    return unsub;
  }, [isAdmin]);

  return (
    <div className="min-h-screen bg-[#F4F6F8]">
      <header className="bg-navy text-white shadow-md">
        <div className="mx-auto max-w-7xl px-4">
          {/* 상단바: 로고 + 시스템명 + 유저 */}
          <div className="flex items-center justify-between py-2.5">
            <div className="flex items-center gap-3">
              <span className="text-base font-black tracking-tight">
                <span className="text-blue-300">H</span>
                <span className="text-white">ORIZON</span>
                <span className="text-gray-400 font-normal text-sm ml-0.5">0817</span>
              </span>
              <span className="hidden sm:block text-[10px] text-gray-400 border-l border-gray-600 pl-3 leading-tight">
                8·17 전당대회<br />정무상황판
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-gray-300">
              {isAdmin && (
                <span className="rounded bg-brand/20 px-2 py-0.5 text-brand font-semibold">관리자</span>
              )}
              <span className="hidden sm:inline max-w-[160px] truncate">{user?.email}</span>
              <button
                onClick={() => logout()}
                className="rounded border border-white/20 px-2.5 py-1 hover:bg-white/10 transition text-xs"
              >
                로그아웃
              </button>
            </div>
          </div>

          {/* 메인 네비게이션 */}
          <nav className="flex items-end gap-0.5 overflow-x-auto" style={{ scrollbarWidth: "none" }}>
            {NAV_MAIN.map((n) => (
              <NavItem key={n.to} to={n.to} label={n.label} end={n.end} />
            ))}

            {/* 구분선 */}
            <span className="mx-1 self-center text-gray-600 text-xs select-none">|</span>

            {/* 서브 메뉴 (작은 크기) */}
            {NAV_SUB.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                className={({ isActive }) =>
                  `shrink-0 whitespace-nowrap rounded-t px-2.5 py-2 text-xs transition ${
                    isActive
                      ? "bg-brand/80 text-white"
                      : "text-gray-400 hover:text-gray-200"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}

            {isAdmin && (
              <>
                <span className="mx-1 self-center text-gray-600 text-xs select-none">|</span>
                {NAV_ADMIN.map((n) => (
                  <NavLink
                    key={n.to}
                    to={n.to}
                    className={({ isActive }) =>
                      `relative shrink-0 whitespace-nowrap rounded-t px-2.5 py-2 text-xs transition ${
                        isActive
                          ? "bg-brand/80 text-white"
                          : "text-gray-400 hover:text-gray-200"
                      }`
                    }
                  >
                    {n.label}
                    {n.to === "/members" && pendingCount > 0 && (
                      <span className="absolute -top-1 -right-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white leading-none">
                        {pendingCount}
                      </span>
                    )}
                  </NavLink>
                ))}
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}
