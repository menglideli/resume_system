import { useEffect, useState } from "react";
import { Link } from "react-router";
import { motion } from "framer-motion";
import {
  ArrowRight, BellRing, BriefcaseBusiness, FileText, FlaskConical,
  Rocket, Target, TrendingUp,
} from "lucide-react";
import {
  Area, AreaChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { PageHeader } from "@/components/PageHeader";
import { ScoreRing } from "@/components/ScoreRing";
import { getFollowUps, getStats, listApplications, getProfile } from "@/lib/db";
import { STATUS_META, CHANNEL_META, type Application, type AppStats } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  applied: "#38bdf8", viewed: "#fbbf24", interview: "#a78bfa", offer: "#34d399", rejected: "#fb7185",
};

const QUICK = [
  { to: "/jd", icon: FlaskConical, title: "解析新 JD", desc: "粘贴岗位描述，AI 提取要求" },
  { to: "/resumes", icon: FileText, title: "生成简历", desc: "一岗一版，匹配度评分" },
  { to: "/forms", icon: Rocket, title: "填写报名表", desc: "上传表格自动填充" },
];

export default function DashboardPage() {
  const [stats, setStats] = useState<AppStats | null>(null);
  const [followUps, setFollowUps] = useState<Application[]>([]);
  const [recent, setRecent] = useState<Application[]>([]);
  const [completeness, setCompleteness] = useState(0);

  useEffect(() => {
    getStats().then(setStats).catch(() => {});
    getFollowUps().then(setFollowUps).catch(() => {});
    listApplications().then((r) => setRecent(r.items.slice(0, 5))).catch(() => {});
    getProfile().then((p) => setCompleteness(p.completeness_score)).catch(() => {});
  }, []);

  const pieData = stats
    ? Object.entries(stats.by_status).map(([k, v]) => ({ name: STATUS_META[k]?.label || k, value: v, key: k }))
    : [];

  // 趋势横轴用短日期（MM-DD）；后端给 ISO 日期，演示模式给「N日」这样的短标签
  const trend = (stats?.trend_30d ?? []).map((d) => ({
    date: d.date.length >= 10 ? d.date.slice(5) : d.date,
    count: d.count,
  }));

  const cards = [
    { label: "投递总数", value: stats?.total ?? "-", icon: BriefcaseBusiness, color: "text-sky-300", bg: "bg-sky-500/15" },
    { label: "近 7 天投递", value: stats?.recent_7_days ?? "-", icon: TrendingUp, color: "text-cyan-300", bg: "bg-cyan-500/15" },
    { label: "面试转化率", value: stats ? `${stats.conversion_rate}%` : "-", icon: Target, color: "text-violet-300", bg: "bg-violet-500/15" },
    { label: "待跟进", value: followUps.length, icon: BellRing, color: "text-amber-300", bg: "bg-amber-500/15" },
  ];

  return (
    <div>
      <PageHeader title="总览 Dashboard" desc="求职进度一目了然，今天也是 offer 收割日" />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        {cards.map((c, i) => (
          <motion.div
            key={c.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="glass glass-hover p-5 flex items-center gap-4"
          >
            <div className={`w-12 h-12 rounded-xl ${c.bg} flex items-center justify-center shrink-0`}>
              <c.icon className={`w-6 h-6 ${c.color}`} />
            </div>
            <div>
              <div className="text-2xl font-bold">{c.value}</div>
              <div className="text-xs text-slate-500">{c.label}</div>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="grid xl:grid-cols-3 gap-4 mb-6">
        {/* 投递趋势 */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="glass p-5 xl:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-sm">近 30 天投递趋势</h3>
            <span className="chip bg-cyan-500/15 text-cyan-300 border-cyan-500/30">实时更新</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={trend}>
              <defs>
                <linearGradient id="trend" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 10 }} interval={4} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} />
              <Tooltip contentStyle={{ background: "#0b1120", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, fontSize: 12 }} />
              <Area type="monotone" dataKey="count" stroke="#22d3ee" strokeWidth={2.5} fill="url(#trend)" name="投递数" />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* 状态分布 + 完整度 */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="glass p-5 flex flex-col">
          <h3 className="font-semibold text-sm mb-2">投递状态分布</h3>
          <div className="flex-1 flex items-center">
            <ResponsiveContainer width="55%" height={160}>
              <PieChart>
                <Pie data={pieData} dataKey="value" innerRadius={42} outerRadius={64} paddingAngle={3} strokeWidth={0}>
                  {pieData.map((d) => <Cell key={d.key} fill={STATUS_COLORS[d.key] || "#64748b"} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#0b1120", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-1.5">
              {pieData.map((d) => (
                <div key={d.key} className="flex items-center gap-2 text-xs text-slate-400">
                  <span className="w-2 h-2 rounded-full" style={{ background: STATUS_COLORS[d.key] }} />
                  {d.name}<span className="ml-auto text-slate-200 font-semibold">{d.value}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="border-t border-white/[0.07] pt-3 flex items-center justify-between">
            <div className="text-xs text-slate-500">档案完整度</div>
            <ScoreRing value={completeness} size={64} stroke={6} label="完整" color="#34d399" />
          </div>
        </motion.div>
      </div>

      <div className="grid xl:grid-cols-3 gap-4">
        {/* 快捷操作 */}
        {QUICK.map((q, i) => (
          <motion.div key={q.to} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 + i * 0.08 }}>
            <Link to={q.to} className="glass glass-hover p-5 flex items-center gap-4 group block">
              <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-cyan-500/25 to-violet-500/25 flex items-center justify-center shrink-0">
                <q.icon className="w-5 h-5 text-cyan-300" />
              </div>
              <div className="flex-1">
                <div className="font-semibold text-sm">{q.title}</div>
                <div className="text-xs text-slate-500">{q.desc}</div>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-cyan-300 group-hover:translate-x-1 transition-all" />
            </Link>
          </motion.div>
        ))}
      </div>

      {/* 待跟进 + 最近投递 */}
      <div className="grid xl:grid-cols-2 gap-4 mt-6">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }} className="glass p-5">
          <h3 className="font-semibold text-sm mb-4 flex items-center gap-2">
            <BellRing className="w-4 h-4 text-amber-300" /> 待跟进
          </h3>
          {followUps.length === 0 && <p className="text-xs text-slate-500 py-6 text-center">暂无待跟进事项 🎉</p>}
          <div className="space-y-2.5">
            {followUps.map((a) => (
              <div key={a.id} className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <span className={`chip ${STATUS_META[a.status]?.color}`}>{STATUS_META[a.status]?.label}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{a.company_name} · {a.position_title}</div>
                  {a.notes && <div className="text-xs text-slate-500 truncate">{a.notes}</div>}
                </div>
                <span className="text-xs text-amber-300/90 shrink-0">{a.follow_up_date}</span>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.58 }} className="glass p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-sm">最近投递</h3>
            <Link to="/applications" className="text-xs text-cyan-300 hover:underline">查看全部</Link>
          </div>
          <div className="space-y-2.5">
            {recent.map((a) => (
              <div key={a.id} className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <span className={`chip ${STATUS_META[a.status]?.color}`}>{STATUS_META[a.status]?.label}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{a.company_name} · {a.position_title}</div>
                </div>
                <span className="text-xs text-slate-500 shrink-0">{CHANNEL_META[a.channel]}</span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
