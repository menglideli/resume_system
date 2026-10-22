import { useEffect, useState } from "react";
import { Loader2, Plus, Save, Search, Settings2, Users } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/PageHeader";
import {
  adminCreateUser, adminDeleteUser, adminListUsers, adminResetPassword,
  adminUpdateUser, getConfig, updateConfig,
} from "@/lib/db";
import type { AdminUser, KimiConfig } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

const EMPTY_USER = { username: "", email: "", password: "", is_admin: false };

export default function AdminPage() {
  // ---------------- 用户管理 ----------------
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [keyword, setKeyword] = useState("");
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [userForm, setUserForm] = useState({ ...EMPTY_USER });
  const [resetTarget, setResetTarget] = useState<AdminUser | null>(null);
  const [newPassword, setNewPassword] = useState("");

  const loadUsers = async (kw = keyword) => {
    setLoadingUsers(true);
    try {
      setUsers(await adminListUsers(kw));
    } catch (e: any) { toast.error(e.message); }
    setLoadingUsers(false);
  };

  // ---------------- 系统配置 ----------------
  const [config, setConfig] = useState<KimiConfig | null>(null);
  const [savingConfig, setSavingConfig] = useState(false);

  useEffect(() => {
    loadUsers("");
    getConfig().then(setConfig).catch((e) => toast.error(e.message));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const doCreateUser = async () => {
    if (!userForm.username || !userForm.email || !userForm.password) return toast.warning("请完整填写用户信息");
    try {
      await adminCreateUser(userForm);
      toast.success("用户已创建");
      setCreateOpen(false);
      setUserForm({ ...EMPTY_USER });
      loadUsers();
    } catch (e: any) { toast.error(e.message); }
  };

  const doDeleteUser = async (u: AdminUser) => {
    if (!confirm(`确认删除用户「${u.username}」？其档案、简历、报名表将一并删除。`)) return;
    try {
      await adminDeleteUser(u.id);
      toast.success("已删除");
      loadUsers();
    } catch (e: any) { toast.error(e.message); }
  };

  const doResetPassword = async () => {
    if (!resetTarget || newPassword.length < 6) return toast.warning("新密码至少 6 位");
    try {
      await adminResetPassword(resetTarget.id, newPassword);
      toast.success(`已重置「${resetTarget.username}」的密码`);
      setResetTarget(null);
      setNewPassword("");
    } catch (e: any) { toast.error(e.message); }
  };

  const toggleAdmin = async (u: AdminUser) => {
    try {
      await adminUpdateUser(u.id, { is_admin: !u.is_admin });
      toast.success(u.is_admin ? "已取消管理员" : "已设为管理员");
      loadUsers();
    } catch (e: any) { toast.error(e.message); }
  };

  const saveConfig = async () => {
    if (!config) return;
    setSavingConfig(true);
    try {
      setConfig(await updateConfig(config));
      toast.success("配置已保存，AI 调用立即生效");
    } catch (e: any) { toast.error(e.message); }
    setSavingConfig(false);
  };

  return (
    <div>
      <PageHeader title="后台管理" desc="用户管理 · Kimi API 配置（修改后立即生效，无需重启）" />

      <Tabs defaultValue="users">
        <TabsList className="bg-white/[0.05] mb-4">
          <TabsTrigger value="users"><Users className="w-4 h-4 mr-1.5" /> 用户管理</TabsTrigger>
          <TabsTrigger value="config"><Settings2 className="w-4 h-4 mr-1.5" /> 系统配置</TabsTrigger>
        </TabsList>

        {/* ---------------- 用户管理 ---------------- */}
        <TabsContent value="users">
          <div className="glass p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="relative flex-1 max-w-xs">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <Input placeholder="搜索用户名 / 邮箱" className="bg-white/[0.05] border-white/10 pl-9"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && loadUsers()} />
              </div>
              <Button variant="ghost" className="text-slate-300" onClick={() => loadUsers()}>搜索</Button>
              <div className="flex-1" />
              <Button className="gradient-btn" onClick={() => setCreateOpen(true)}>
                <Plus className="w-4 h-4 mr-1" /> 新建用户
              </Button>
            </div>

            {loadingUsers ? (
              <div className="flex justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-cyan-400" /></div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500 border-b border-white/[0.07]">
                    <th className="py-2.5 font-medium">用户名</th>
                    <th className="py-2.5 font-medium">邮箱</th>
                    <th className="py-2.5 font-medium">注册时间</th>
                    <th className="py-2.5 font-medium">管理员</th>
                    <th className="py-2.5 font-medium text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-white/[0.05] hover:bg-white/[0.03]">
                      <td className="py-3">{u.username}</td>
                      <td className="py-3 text-slate-400">{u.email}</td>
                      <td className="py-3 text-slate-500 text-xs">{(u.created_at || "").slice(0, 10)}</td>
                      <td className="py-3">
                        <Switch checked={u.is_admin} onCheckedChange={() => toggleAdmin(u)} />
                      </td>
                      <td className="py-3 text-right space-x-2">
                        <Button size="sm" variant="ghost" className="text-slate-300 h-7"
                          onClick={() => { setResetTarget(u); setNewPassword(""); }}>
                          重置密码
                        </Button>
                        <Button size="sm" variant="ghost" className="text-rose-300 h-7" onClick={() => doDeleteUser(u)}>
                          删除
                        </Button>
                      </td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr><td colSpan={5} className="text-center text-slate-500 py-10 text-xs">暂无用户</td></tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        </TabsContent>

        {/* ---------------- 系统配置 ---------------- */}
        <TabsContent value="config">
          <div className="glass p-6 max-w-2xl">
            {!config ? (
              <div className="flex justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-cyan-400" /></div>
            ) : (
              <div className="space-y-4">
                <h3 className="font-semibold text-sm text-slate-300">Kimi API（OpenAI 兼容）</h3>
                <div className="space-y-1.5">
                  <Label className="text-slate-400">API Key（掩码回显，保存掩码值则保持不变）</Label>
                  <Input type="password" className="bg-white/[0.05] border-white/10"
                    value={config.KIMI_API_KEY}
                    onChange={(e) => setConfig({ ...config, KIMI_API_KEY: e.target.value })} />
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-slate-400">Base URL</Label>
                    <Input className="bg-white/[0.05] border-white/10"
                      value={config.KIMI_BASE_URL}
                      onChange={(e) => setConfig({ ...config, KIMI_BASE_URL: e.target.value })} />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-slate-400">模型</Label>
                    <Input className="bg-white/[0.05] border-white/10" placeholder="kimi-latest"
                      value={config.KIMI_MODEL}
                      onChange={(e) => setConfig({ ...config, KIMI_MODEL: e.target.value })} />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-slate-400">超时时间（秒）</Label>
                    <Input type="number" className="bg-white/[0.05] border-white/10"
                      value={config.KIMI_TIMEOUT}
                      onChange={(e) => setConfig({ ...config, KIMI_TIMEOUT: e.target.value })} />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-slate-400">最大 Tokens</Label>
                    <Input type="number" className="bg-white/[0.05] border-white/10"
                      value={config.KIMI_MAX_TOKENS}
                      onChange={(e) => setConfig({ ...config, KIMI_MAX_TOKENS: e.target.value })} />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-slate-400">思考强度（仅推理模型）</Label>
                    <Select value={config.KIMI_REASONING_EFFORT || "high"}
                      onValueChange={(v) => setConfig({ ...config, KIMI_REASONING_EFFORT: v })}>
                      <SelectTrigger className="bg-white/[0.05] border-white/10">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="low">low（最快，约 60 秒）</SelectItem>
                        <SelectItem value="high">high（推荐，约 75 秒）</SelectItem>
                        <SelectItem value="max">max（最慢，生成简历会超 500 秒并失败）</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <Button className="gradient-btn" onClick={saveConfig} disabled={savingConfig}>
                  {savingConfig ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                  保存配置
                </Button>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* 新建用户对话框 */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-[#0b1120] border-white/10 text-slate-100 max-w-md">
          <DialogHeader><DialogTitle>新建用户</DialogTitle></DialogHeader>
          <div className="space-y-3.5 py-2">
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-xs">用户名</Label>
              <Input className="bg-white/[0.05] border-white/10 text-sm"
                value={userForm.username}
                onChange={(e) => setUserForm({ ...userForm, username: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-xs">邮箱</Label>
              <Input type="email" className="bg-white/[0.05] border-white/10 text-sm"
                value={userForm.email}
                onChange={(e) => setUserForm({ ...userForm, email: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-xs">初始密码</Label>
              <Input type="password" className="bg-white/[0.05] border-white/10 text-sm"
                value={userForm.password}
                onChange={(e) => setUserForm({ ...userForm, password: e.target.value })} />
            </div>
            <div className="flex items-center gap-2 text-sm text-slate-300">
              <Switch checked={userForm.is_admin}
                onCheckedChange={(v) => setUserForm({ ...userForm, is_admin: v })} />
              设为管理员
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>取消</Button>
            <Button className="gradient-btn" onClick={doCreateUser}>创建</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 重置密码对话框 */}
      <Dialog open={!!resetTarget} onOpenChange={(o) => !o && setResetTarget(null)}>
        <DialogContent className="bg-[#0b1120] border-white/10 text-slate-100 max-w-sm">
          <DialogHeader><DialogTitle>重置「{resetTarget?.username}」的密码</DialogTitle></DialogHeader>
          <div className="space-y-1.5 py-2">
            <Label className="text-slate-400 text-xs">新密码（至少 6 位）</Label>
            <Input type="password" className="bg-white/[0.05] border-white/10 text-sm"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)} />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setResetTarget(null)}>取消</Button>
            <Button className="gradient-btn" onClick={doResetPassword}>确认重置</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
