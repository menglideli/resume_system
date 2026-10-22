import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { BellRing, Download, Loader2, Mail, Plus, Globe, Landmark, Lock, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/PageHeader";
import {
  createApplication, deleteApplication, downloadSnapshotPdf, getApplicationSnapshot, getFollowUps,
  getStats, listApplications, listResumes, updateApplication,
} from "@/lib/db";
import {
  CHANNEL_META, STATUS_META,
  type Application, type ApplicationSnapshot, type AppStats, type Resume, type ResumeSection,
} from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const CHANNEL_ICON: Record<string, any> = { email: Mail, website: Globe, official: Landmark };
const FLOW = ["applied", "viewed", "interview", "offer", "rejected"];

/** 快照内容渲染：招聘方当时看到的简历（只读、简化版） */
function SnapshotSections({ sections }: { sections?: ResumeSection[] }) {
  return (
    <div className="space-y-4">
      {(sections || []).map((sec, i) => (
        <div key={i}>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="w-1 h-3.5 rounded bg-gradient-to-b from-cyan-400 to-violet-500" />
            <span className="font-semibold text-xs text-slate-200">{sec.title || sec.type}</span>
          </div>
          {sec.type === "summary" && <p className="text-xs text-slate-400 leading-relaxed">{sec.content}</p>}
          {sec.type === "skills" && (
            <div className="flex flex-wrap gap-1">
              {(sec.items || []).filter((it: any) => !it.hidden).map((it: any, j: number) => (
                <span key={j} className="chip bg-cyan-500/10 text-cyan-300 border-cyan-500/20 text-[10px]">
                  {it.name}{it.level ? ` · ${it.level}` : ""}
                </span>
              ))}
            </div>
          )}
          {["experience", "projects"].includes(sec.type) && (sec.items || []).filter((it: any) => !it.hidden).map((it: any, j: number) => (
            <div key={j} className="mb-2">
              <div className="flex justify-between text-xs">
                <span className="font-medium text-slate-200">{it.company || it.name}{(it.position || it.role) ? ` · ${it.position || it.role}` : ""}</span>
                <span className="text-slate-500">{it.period}</span>
              </div>
              <ul className="text-xs text-slate-400 mt-0.5 space-y-0.5">
                {(it.bullets || []).map((b: string, k: number) => <li key={k} className="flex gap-1.5"><span className="text-cyan-500">▪</span>{b}</li>)}
              </ul>
            </div>
          ))}
          {sec.type === "education" && (sec.items || []).filter((it: any) => !it.hidden).map((it: any, j: number) => (
            <div key={j} className="flex justify-between text-xs text-slate-300">
              <span>{it.school} · {it.major}{it.degree ? `（${it.degree}）` : ""}</span>
              <span className="text-slate-500">{it.period}</span>
            </div>
          ))}
          {sec.type === "certifications" && (sec.items || []).filter((it: any) => !it.hidden).map((it: any, j: number) => (
            <div key={j} className="flex justify-between text-xs text-slate-300">
              <span>{it.name}{it.issuer ? ` · ${it.issuer}` : ""}</span>
              <span className="text-slate-500">{it.date}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

export default function ApplicationsPage() {
  const [items, setItems] = useState<Application[]>([]);
  const [stats, setStats] = useState<AppStats | null>(null);
  const [followUps, setFollowUps] = useState<Application[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [filter, setFilter] = useState({ status: "all", channel: "all" });
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ company_name: "", position_title: "", channel: "website", notes: "", follow_up_date: "", resume_id: "" });
  // 投递版本快照查看
  const [snapApp, setSnapApp] = useState<Application | null>(null);
  const [snap, setSnap] = useState<ApplicationSnapshot | null>(null);
  const [snapLoading, setSnapLoading] = useState(false);

  const reload = async () => {
    const params = new URLSearchParams();
    if (filter.status !== "all") params.set("status", filter.status);
    if (filter.channel !== "all") params.set("channel", filter.channel);
    const q = params.toString() ? `?${params}` : "";
    const [list, st, fu] = await Promise.all([listApplications(q), getStats(), getFollowUps()]);
    setItems(list.items);
    setStats(st);
    setFollowUps(fu);
  };
  useEffect(() => { reload().catch(() => {}); }, [filter]);
  // 可关联的简历：只有生成成功/已导出的才有锁定意义
  useEffect(() => { listResumes().then(setResumes).catch(() => {}); }, []);
  const linkableResumes = resumes.filter((r) => ["generated", "exported"].includes(r.status));

  const doCreate = async () => {
    if (!form.company_name || !form.position_title) return toast.warning("公司和岗位必填");
    setSaving(true);
    try {
      const { resume_id, ...rest } = form;
      await createApplication({ ...rest, follow_up_date: form.follow_up_date || null, resume_id: resume_id || null } as any);
      toast.success(resume_id ? "投递记录已创建，简历版本已锁定" : "投递记录已创建");
      setOpen(false);
      setForm({ company_name: "", position_title: "", channel: "website", notes: "", follow_up_date: "", resume_id: "" });
      reload();
    } catch (e: any) { toast.error(e.message); }
    setSaving(false);
  };

  const openSnapshot = async (a: Application) => {
    setSnapApp(a);
    setSnap(null);
    setSnapLoading(true);
    try { setSnap(await getApplicationSnapshot(a.id)); }
    catch (e: any) { toast.error(e.message); setSnapApp(null); }
    setSnapLoading(false);
  };

  const doDownloadSnapshot = async (a: Application) => {
    try { await downloadSnapshotPdf(a); }
    catch (e: any) { toast.error(e.message); }
  };

  const advance = async (a: Application, status: string) => {
    try {
      await updateApplication(a.id, { status });
      toast.success(`已更新为「${STATUS_META[status]?.label}」`);
      reload();
    } catch (e: any) { toast.error(e.message); }
  };

  const remove = async (a: Application) => {
    try {
      await deleteApplication(a.id);
      toast.success("已删除");
      reload();
    } catch (e: any) { toast.error(e.message); }
  };

  return (
    <div>
      <PageHeader title="投递追踪" desc="每条投递都有归宿：状态机 + 跟进提醒 + 转化统计"
        actions={<Button className="gradient-btn" onClick={() => setOpen(true)}><Plus className="w-4 h-4 mr-2" />记录投递</Button>} />

      {/* 统计条 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
        {[
          { label: "总投递", value: stats?.total },
          { label: "已投递", value: stats?.by_status?.applied },
          { label: "面试", value: stats?.by_status?.interview },
          { label: "Offer", value: stats?.by_status?.offer },
          { label: "转化率", value: stats ? `${stats.conversion_rate}%` : "-" },
        ].map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
            className="glass p-4 text-center">
            <div className="text-xl font-bold gradient-text">{s.value ?? "-"}</div>
            <div className="text-xs text-slate-500 mt-0.5">{s.label}</div>
          </motion.div>
        ))}
      </div>

      {/* 筛选 */}
      <div className="flex gap-3 mb-4">
        <Select value={filter.status} onValueChange={(v) => setFilter({ ...filter, status: v })}>
          <SelectTrigger className="w-36 bg-white/[0.05] border-white/10 h-9"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
            <SelectItem value="all">全部状态</SelectItem>
            {Object.entries(STATUS_META).map(([k, m]) => <SelectItem key={k} value={k}>{m.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filter.channel} onValueChange={(v) => setFilter({ ...filter, channel: v })}>
          <SelectTrigger className="w-36 bg-white/[0.05] border-white/10 h-9"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
            <SelectItem value="all">全部渠道</SelectItem>
            {Object.entries(CHANNEL_META).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {/* 列表 */}
      <div className="space-y-2.5">
        {items.length === 0 && <div className="glass p-12 text-center text-slate-600 text-sm">暂无投递记录</div>}
        {items.map((a, i) => {
          const Icon = CHANNEL_ICON[a.channel] || Globe;
          const isFollowUp = followUps.some((f) => f.id === a.id);
          return (
            <motion.div key={a.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
              className={`glass glass-hover p-4 flex items-center gap-4 ${isFollowUp ? "border-amber-500/30" : ""}`}>
              <div className="w-10 h-10 rounded-xl bg-white/[0.05] flex items-center justify-center shrink-0">
                <Icon className="w-5 h-5 text-cyan-300" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm truncate">{a.company_name} · {a.position_title}</span>
                  {isFollowUp && <BellRing className="w-3.5 h-3.5 text-amber-300 shrink-0" />}
                </div>
                <div className="text-xs text-slate-500 mt-0.5 truncate">
                  {CHANNEL_META[a.channel]} · {new Date(a.applied_at).toLocaleDateString("zh-CN")}
                  {a.resume_version_name && ` · 简历：${a.resume_version_name}`}
                  {a.notes && ` · ${a.notes}`}
                </div>
              </div>
              {a.has_snapshot && (
                <button
                  className="chip shrink-0 bg-violet-500/15 text-violet-300 border-violet-500/30 hover:bg-violet-500/25 cursor-pointer"
                  title="查看招聘方当时实际收到的简历版本"
                  onClick={() => openSnapshot(a)}
                >
                  <Lock className="w-3 h-3 mr-1 inline" />锁定版本
                </button>
              )}
              {a.has_snapshot_pdf && (
                <button
                  className="chip shrink-0 bg-cyan-500/15 text-cyan-300 border-cyan-500/30 hover:bg-cyan-500/25 cursor-pointer"
                  title="下载投递时锁定的 PDF 副本"
                  onClick={() => doDownloadSnapshot(a)}
                >
                  <Download className="w-3 h-3 mr-1 inline" />快照 PDF
                </button>
              )}
              <span className={`chip shrink-0 ${STATUS_META[a.status]?.color}`}>{STATUS_META[a.status]?.label}</span>
              <Select value={a.status} onValueChange={(v) => advance(a, v)}>
                <SelectTrigger className="w-28 h-8 bg-white/[0.05] border-white/10 text-xs shrink-0"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
                  {FLOW.map((s) => <SelectItem key={s} value={s}>{STATUS_META[s].label}</SelectItem>)}
                </SelectContent>
              </Select>
              <Button size="icon" variant="ghost" className="h-8 w-8 text-slate-500 hover:text-rose-300 shrink-0" onClick={() => remove(a)}>
                <Trash2 className="w-4 h-4" />
              </Button>
            </motion.div>
          );
        })}
      </div>

      {/* 新建对话框 */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0b1120] border-white/10 text-slate-100 max-w-md">
          <DialogHeader><DialogTitle className="gradient-text">记录一次投递</DialogTitle></DialogHeader>
          <div className="space-y-3.5 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-slate-400 text-xs">公司 *</Label>
                <Input className="bg-white/[0.05] border-white/10" value={form.company_name}
                  onChange={(e) => setForm({ ...form, company_name: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-slate-400 text-xs">岗位 *</Label>
                <Input className="bg-white/[0.05] border-white/10" value={form.position_title}
                  onChange={(e) => setForm({ ...form, position_title: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-slate-400 text-xs">渠道</Label>
                <Select value={form.channel} onValueChange={(v) => setForm({ ...form, channel: v })}>
                  <SelectTrigger className="bg-white/[0.05] border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
                    {Object.entries(CHANNEL_META).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-slate-400 text-xs">跟进日期</Label>
                <Input type="date" className="bg-white/[0.05] border-white/10" value={form.follow_up_date}
                  onChange={(e) => setForm({ ...form, follow_up_date: e.target.value })} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-xs">关联简历（锁定投递版本）</Label>
              <Select value={form.resume_id || "none"} onValueChange={(v) => setForm({ ...form, resume_id: v === "none" ? "" : v })}>
                <SelectTrigger className="bg-white/[0.05] border-white/10"><SelectValue placeholder="不关联" /></SelectTrigger>
                <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
                  <SelectItem value="none">不关联（仅手工记录）</SelectItem>
                  {linkableResumes.map((r) => (
                    <SelectItem key={r.id} value={r.id}>{r.version_name}{r.match_score != null ? ` · 匹配 ${r.match_score}` : ""}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-[10px] leading-relaxed text-slate-500">
                关联后系统会锁定投递当时的简历内容、模板、匹配分和 JD，并保留 PDF 副本 —— 之后简历再怎么改，回看到的都是招聘方实际收到的那份
              </p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-xs">备注</Label>
              <Textarea rows={3} className="bg-white/[0.05] border-white/10" value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>取消</Button>
            <Button className="gradient-btn" onClick={doCreate} disabled={saving}>
              {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 投递版本快照：招聘方当时实际收到的内容 */}
      <Dialog open={!!snapApp} onOpenChange={(o) => !o && setSnapApp(null)}>
        <DialogContent className="bg-[#0b1120] border-white/10 text-slate-100 max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="gradient-text flex items-center gap-2">
              <Lock className="w-4 h-4" />投递锁定版本
              {snapApp && <span className="text-sm text-slate-400 font-normal">· {snapApp.company_name} {snapApp.position_title}</span>}
            </DialogTitle>
          </DialogHeader>
          {snapLoading && <div className="p-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-slate-500" /></div>}
          {snap && (
            <div className="space-y-4">
              <div className="rounded-lg border border-violet-500/25 bg-violet-500/[0.05] px-3.5 py-2.5 text-[11px] leading-relaxed text-slate-400">
                这是 <b className="text-violet-300">{new Date(snap.applied_at).toLocaleString("zh-CN")}</b> 投递时锁定的版本
                {snap.resume_version_name && <>（简历：{snap.resume_version_name}）</>}
                {snap.snapshot_match_score != null && <> · 当时匹配分 <b className="text-slate-200">{snap.snapshot_match_score}</b></>}
                。之后对简历的任何编辑、回滚都不影响这里的内容；面试准备应针对这份简历。
              </div>
              <div className="flex items-center gap-2">
                <div className="text-sm font-semibold text-slate-200">
                  {snap.resume_snapshot?.header?.name} · {snap.resume_snapshot?.header?.title}
                </div>
                {snap.has_snapshot_pdf && (
                  <Button size="sm" variant="outline" className="ml-auto border-white/10 text-slate-300 hover:bg-white/[0.06] h-7"
                    onClick={() => snapApp && doDownloadSnapshot(snapApp)}>
                    <Download className="w-3.5 h-3.5 mr-1.5" />下载当时的 PDF
                  </Button>
                )}
              </div>
              <div className="text-xs text-slate-500">
                {Object.values(snap.resume_snapshot?.header?.contact || {}).filter(Boolean).join(" · ")}
              </div>
              <SnapshotSections sections={snap.resume_snapshot?.sections} />
              {snap.jd_snapshot?.raw_text && (
                <details className="rounded-lg border border-white/[0.08] bg-white/[0.02] p-3">
                  <summary className="text-xs text-slate-400 cursor-pointer">当时的 JD 原文（{snap.jd_snapshot.company_name} · {snap.jd_snapshot.position_title}）</summary>
                  <pre className="mt-2 text-[11px] text-slate-500 whitespace-pre-wrap max-h-52 overflow-y-auto">{snap.jd_snapshot.raw_text}</pre>
                </details>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
