import { useState } from "react";
import { useNavigate } from "react-router";
import { motion } from "framer-motion";
import { ScrollText, Sparkles, FileText, ClipboardList, TrendingUp, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { login, register } from "@/lib/db";
import { setToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const FEATURES = [
  { icon: Sparkles, title: "AI 简历定制", desc: "粘贴 JD，一键生成高匹配简历" },
  { icon: ClipboardList, title: "报名表秒填", desc: "PDF/Word/Excel 自动识别填充" },
  { icon: TrendingUp, title: "投递追踪", desc: "状态、转化率、跟进一目了然" },
];

export default function AuthPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [loginForm, setLoginForm] = useState({ username: "", password: "" });
  const [regForm, setRegForm] = useState({ username: "", email: "", password: "" });

  const doLogin = async () => {
    if (!loginForm.username || !loginForm.password) return toast.warning("请输入用户名和密码");
    setLoading(true);
    try {
      const res = await login(loginForm.username, loginForm.password);
      setToken(res.access_token);
      toast.success("登录成功，欢迎回来");
      navigate("/");
    } catch (e: any) {
      toast.error(e.message || "登录失败");
    } finally {
      setLoading(false);
    }
  };

  const doRegister = async () => {
    if (!regForm.username || !regForm.email || !regForm.password) return toast.warning("请完整填写注册信息");
    setLoading(true);
    try {
      await register(regForm.username, regForm.email, regForm.password);
      const res = await login(regForm.username, regForm.password);
      setToken(res.access_token);
      toast.success("注册成功，已自动登录");
      navigate("/");
    } catch (e: any) {
      toast.error(e.message || "注册失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen bg-[#05070f] text-slate-100 overflow-hidden flex">
      <div className="fixed inset-0 pointer-events-none">
        <div className="aurora w-[560px] h-[560px] bg-cyan-500 -top-40 -left-32" />
        <div className="aurora w-[480px] h-[480px] bg-violet-600 bottom-0 -right-24" style={{ animationDelay: "-7s" }} />
        <div className="absolute inset-0 grid-bg" />
      </div>

      {/* 左侧品牌区 */}
      <div className="relative z-10 flex-1 hidden lg:flex flex-col justify-center px-16">
        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
          <div className="flex items-center gap-3 mb-8">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-cyan-400 to-violet-600 flex items-center justify-center shadow-[0_0_30px_-4px] shadow-cyan-500/70">
              <ScrollText className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-bold gradient-text">智能简历投递系统</span>
          </div>
          <h1 className="text-4xl xl:text-5xl font-bold leading-tight mb-4">
            一份档案，<br />
            <span className="gradient-text">千份定制简历</span>
          </h1>
          <p className="text-slate-400 max-w-md mb-12">
            Kimi AI 驱动的求职工作台：JD 深度解析、简历一岗一版、事业单位报名表自动填写、投递全周期追踪。
          </p>
          <div className="space-y-4">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 + i * 0.15 }}
                className="flex items-center gap-4 glass p-4 max-w-md glass-hover"
              >
                <div className="w-10 h-10 rounded-xl bg-cyan-500/15 flex items-center justify-center shrink-0">
                  <f.icon className="w-5 h-5 text-cyan-300" />
                </div>
                <div>
                  <div className="font-semibold text-sm">{f.title}</div>
                  <div className="text-xs text-slate-500">{f.desc}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* 右侧表单区 */}
      <div className="relative z-10 w-full lg:w-[480px] flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-sm glass p-8 shadow-[0_0_60px_-20px] shadow-cyan-500/30"
        >
          <div className="lg:hidden flex items-center gap-2 mb-6 justify-center">
            <FileText className="w-5 h-5 text-cyan-400" />
            <span className="font-bold gradient-text">智能简历投递系统</span>
          </div>
          <Tabs defaultValue="login">
            <TabsList className="grid grid-cols-2 w-full bg-white/[0.05] mb-6">
              <TabsTrigger value="login">登录</TabsTrigger>
              <TabsTrigger value="register">注册</TabsTrigger>
            </TabsList>

            <TabsContent value="login" className="space-y-4">
              <div className="space-y-2">
                <Label>用户名 / 邮箱</Label>
                <Input placeholder="zhangsan" className="bg-white/[0.05] border-white/10"
                  value={loginForm.username}
                  onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label>密码</Label>
                <Input type="password" placeholder="••••••••" className="bg-white/[0.05] border-white/10"
                  value={loginForm.password}
                  onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                  onKeyDown={(e) => e.key === "Enter" && doLogin()} />
              </div>
              <Button className="w-full gradient-btn h-10" onClick={doLogin} disabled={loading}>
                {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />} 登 录
              </Button>
              <p className="text-xs text-slate-500 text-center">演示模式下任意账号密码均可进入</p>
            </TabsContent>

            <TabsContent value="register" className="space-y-4">
              <div className="space-y-2">
                <Label>用户名</Label>
                <Input className="bg-white/[0.05] border-white/10" value={regForm.username}
                  onChange={(e) => setRegForm({ ...regForm, username: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label>邮箱</Label>
                <Input type="email" className="bg-white/[0.05] border-white/10" value={regForm.email}
                  onChange={(e) => setRegForm({ ...regForm, email: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label>密码</Label>
                <Input type="password" className="bg-white/[0.05] border-white/10" value={regForm.password}
                  onChange={(e) => setRegForm({ ...regForm, password: e.target.value })} />
              </div>
              <Button className="w-full gradient-btn h-10" onClick={doRegister} disabled={loading}>
                {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />} 创建账号
              </Button>
            </TabsContent>
          </Tabs>
        </motion.div>
      </div>
    </div>
  );
}
