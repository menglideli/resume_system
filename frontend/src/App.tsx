import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";
import { clearToken, detectDemo, getToken, isAdmin, isDemo, onLogin, onLogout, onUnauthorized } from "@/lib/api";
import { clearMe, getMe } from "@/lib/db";
import AppLayout from "@/components/AppLayout";
import AuthPage from "@/pages/AuthPage";
import DashboardPage from "@/pages/DashboardPage";
import ProfilePage from "@/pages/ProfilePage";
import JdPage from "@/pages/JdPage";
import ResumesPage from "@/pages/ResumesPage";
import FormsPage from "@/pages/FormsPage";
import PhotosPage from "@/pages/PhotosPage";
import ApplicationsPage from "@/pages/ApplicationsPage";
import AdminPage from "@/pages/AdminPage";

function Splash() {
  return (
    <div className="min-h-screen bg-[#05070f] flex flex-col items-center justify-center gap-4">
      <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-cyan-400 to-violet-600 animate-pulse shadow-[0_0_40px_-4px] shadow-cyan-500/70" />
      <p className="text-slate-500 text-sm tracking-widest">正在连接服务…</p>
    </div>
  );
}

export default function App() {
  const [ready, setReady] = useState<"checking" | "authed" | "anon">("checking");
  const location = useLocation();

  useEffect(() => {
    let alive = true;
    (async () => {
      await detectDemo().catch(() => {});

      if (!getToken()) {
        if (alive) setReady("anon");
        return;
      }
      // 演示模式没有后端可以问，维持「有令牌即已登录」的既有行为
      if (isDemo()) {
        if (alive) setReady("authed");
        return;
      }
      // 真实后端：只认 localStorage 里有令牌是不够的 —— 手写一个字符串就能绕过登录页，
      // 而且令牌过期后前端会一直卡在「已登录、但每个接口都 401」的状态。
      // 启动时打一次 /auth/me，无效就清掉本地凭据回登录页。
      const me = await getMe(true);
      if (!me) {
        clearToken();
        clearMe();
        if (alive) setReady("anon");
        return;
      }
      if (alive) setReady("authed");
    })();
    return () => {
      alive = false;
    };
  }, []);

  // 会话中途令牌失效（过期、被服务端清掉）时回到登录页。
  // 没有这一步，用户只会看到一连串「请求失败 (401)」却不知道该重新登录。
  useEffect(
    () => onUnauthorized(() => {
      clearMe();
      setReady("anon");
    }),
    [],
  );

  // 登录/登出是运行中的状态迁移：守卫状态不能只在启动时求值一次，
  // 否则登录后 navigate("/") 会被仍是 anon 的守卫弹回登录页（登出同理）。
  useEffect(() => onLogin(() => setReady("authed")), []);
  useEffect(() => onLogout(() => setReady("anon")), []);

  if (ready === "checking") return <Splash />;

  const authed = ready === "authed";

  return (
    <Routes>
      <Route path="/auth" element={authed ? <Navigate to="/" replace /> : <AuthPage />} />
      <Route element={authed ? <AppLayout /> : <Navigate to="/auth" replace state={{ from: location }} />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/jd" element={<JdPage />} />
        <Route path="/resumes" element={<ResumesPage />} />
        <Route path="/forms" element={<FormsPage />} />
        <Route path="/photos" element={<PhotosPage />} />
        <Route path="/applications" element={<ApplicationsPage />} />
        <Route path="/admin" element={isAdmin() ? <AdminPage /> : <Navigate to="/" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
