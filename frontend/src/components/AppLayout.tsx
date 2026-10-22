import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router";
import {
  BriefcaseBusiness, FileText, FlaskConical, Images, LayoutDashboard,
  LogOut, ScrollText, Settings2, UserRound, Sparkles, ClipboardList,
} from "lucide-react";
import { clearToken, isAdmin, isDemo, notifyLogout, onDemoChange } from "@/lib/api";
import { clearMe, getMe, type Me } from "@/lib/db";
import { Toaster } from "@/components/ui/sonner";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

const NAV = [
  { to: "/", label: "总览", icon: LayoutDashboard, end: true },
  { to: "/profile", label: "档案中心", icon: UserRound },
  { to: "/jd", label: "JD 解析", icon: FlaskConical },
  { to: "/resumes", label: "简历工坊", icon: FileText },
  { to: "/forms", label: "报名表", icon: ClipboardList },
  { to: "/photos", label: "照片库", icon: Images },
  { to: "/applications", label: "投递追踪", icon: BriefcaseBusiness },
];

/** 由用户名稳定派生一个色相：同一个人永远是同一个配色，不同人尽量错开。 */
function hueOf(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return h % 360;
}

/** 头像首字：中文取第一个汉字，英文取首字母大写。 */
function initialOf(name: string): string {
  const t = (name || "").trim();
  if (!t) return "?";
  return /[a-zA-Z]/.test(t[0]) ? t[0].toUpperCase() : t[0];
}

export default function AppLayout() {
  const navigate = useNavigate();
  const [demo, setDemo] = useState(isDemo());
  const [me, setMe] = useState<Me | null>(null);
  const admin = isAdmin();
  const nav = admin
    ? [...NAV, { to: "/admin", label: "后台管理", icon: Settings2 }]
    : NAV;

  useEffect(() => onDemoChange(setDemo), []);

  // 昵称与头像来自真实账号，不再写死。演示模式下没有后端，回落到本地占位。
  useEffect(() => {
    let alive = true;
    getMe().then((u) => {
      if (alive && u) setMe(u);
    });
    return () => {
      alive = false;
    };
  }, []);

  const displayName = me?.username || (demo ? "演示用户" : "未登录");
  const hue = hueOf(displayName);

  const logout = () => {
    clearToken();
    clearMe();
    notifyLogout();
    navigate("/auth");
  };

  return (
    <div className="relative min-h-screen bg-[#05070f] text-slate-100 overflow-hidden">
      {/* 背景层：极光 + 网格 */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="aurora w-[520px] h-[520px] bg-cyan-500 -top-40 -left-32" />
        <div className="aurora w-[460px] h-[460px] bg-violet-600 top-1/3 -right-32" style={{ animationDelay: "-6s" }} />
        <div className="aurora w-[380px] h-[380px] bg-sky-600 bottom-0 left-1/3" style={{ animationDelay: "-10s" }} />
        <div className="absolute inset-0 grid-bg" />
      </div>

      {/* 侧边导航 */}
      <aside className="fixed left-0 top-0 bottom-0 w-60 z-20 flex flex-col border-r border-white/[0.07] bg-[#070b16]/80 backdrop-blur-xl">
        <div className="flex items-center gap-2.5 px-5 h-16 border-b border-white/[0.07]">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-400 to-violet-600 flex items-center justify-center shadow-[0_0_18px_-2px] shadow-cyan-500/60">
            <ScrollText className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="font-bold text-sm gradient-text">智能简历系统</div>
            <div className="text-[10px] text-slate-500 tracking-wider">AI RESUME STUDIO</div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {nav.map(({ to, label, icon: Icon, end }: any) => (
            <NavLink
              key={to} to={to} end={end}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm transition-all duration-300 ${
                  isActive
                    ? "bg-gradient-to-r from-cyan-500/20 to-violet-500/20 text-white border border-cyan-500/30 shadow-[0_0_20px_-8px] shadow-cyan-500/50"
                    : "text-slate-400 hover:text-white hover:bg-white/[0.05] border border-transparent"
                }`
              }
            >
              <Icon className="w-[18px] h-[18px]" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-white/[0.07]">
          <div className="glass p-3 flex items-center gap-2 text-xs text-slate-400">
            <Sparkles className="w-4 h-4 text-cyan-400 shrink-0" />
            <span>Kimi AI 驱动 · 一岗一版</span>
          </div>
        </div>
      </aside>

      {/* 主区域 */}
      <div className="relative z-10 ml-60 min-h-screen flex flex-col">
        <header className="sticky top-0 z-20 h-16 flex items-center justify-between px-8 border-b border-white/[0.07] bg-[#05070f]/70 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            {demo && (
              <span className="chip bg-amber-500/15 text-amber-300 border-amber-500/30 animate-pulse-glow">
                演示模式 · 未连接后端
              </span>
            )}
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger className="outline-none">
              <Avatar className="w-9 h-9 border cursor-pointer transition-shadow hover:shadow-[0_0_16px_-2px]"
                style={{ borderColor: `hsl(${hue} 70% 55% / 0.45)` }}>
                <AvatarFallback className="text-sm text-white font-medium"
                  style={{
                    background: `linear-gradient(135deg, hsl(${hue} 65% 42%), hsl(${(hue + 55) % 360} 65% 34%))`,
                  }}>
                  {initialOf(displayName)}
                </AvatarFallback>
              </Avatar>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44 bg-[#0b1120] border-white/10 text-slate-200">
              <DropdownMenuLabel className="truncate" title={me?.email}>
                {displayName}
                {me?.email && <span className="block text-[10px] font-normal text-slate-500 truncate">{me.email}</span>}
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="bg-white/10" />
              <DropdownMenuItem onClick={logout} className="text-rose-300 focus:text-rose-200 cursor-pointer">
                <LogOut className="w-4 h-4 mr-2" /> 退出登录
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>

        <main className="flex-1 p-8">
          <Outlet />
        </main>
      </div>

      <Toaster theme="dark" position="top-right" richColors />
    </div>
  );
}
