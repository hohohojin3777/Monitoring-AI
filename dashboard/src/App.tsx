import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Issues from "./pages/Issues";
import ClusterDetail from "./pages/ClusterDetail";
import Alerts from "./pages/Alerts";
import Reports from "./pages/Reports";
import Keywords from "./pages/Keywords";
import Authors from "./pages/Authors";
import Rejected from "./pages/Rejected";
import Settings from "./pages/Settings";

function Splash({ text }: { text: string }) {
  return (
    <div className="flex h-full items-center justify-center text-gray-500">{text}</div>
  );
}

export default function App() {
  const { user, isMember, loading } = useAuth();

  if (loading) return <Splash text="불러오는 중…" />;
  if (!user) return <Login />;
  if (!isMember)
    return (
      <Splash text="승인된 멤버만 접근할 수 있습니다. 관리자에게 등록을 요청하세요." />
    );

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Issues />} />
        <Route path="/clusters/:id" element={<ClusterDetail />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/keywords" element={<Keywords />} />
        <Route path="/authors" element={<Authors />} />
        <Route path="/rejected" element={<Rejected />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
