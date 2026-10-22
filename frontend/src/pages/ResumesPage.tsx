import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle, CheckCircle2, ClipboardList, Download, FileText,
  GraduationCap, History, Lightbulb, Loader2, Pencil, RefreshCw, Sparkles, Target, Trash2, Wand2,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/PageHeader";
import { ScoreRing } from "@/components/ScoreRing";
import ResumeEditor from "@/components/ResumeEditor";
import ResumeHistory from "@/components/ResumeHistory";
import {
  applyEnhancements, deleteResume, exportResume, generateResume, getInterviewPrep, getResumeStats,
  listJDs, listResumes, prepareInterview, regenerateInterview, retryResume,
} from "@/lib/db";
import type { Enhancement, InterviewPrep, JD, Resume, ResumeSection, ResumeStats, ResumeTemplate } from "@/lib/types";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// 补强建议的风险档位。用颜色把「档案完全没有对应」和「只是没写好」明确区分开，
// 避免用户把高风险推测当成低风险内容随手勾上。
const RISK_STYLE: Record<string, { label: string; cls: string }> = {
  high: { label: "高风险 · 档案无对应", cls: "bg-rose-500/15 text-rose-300 border-rose-500/30" },
  medium: { label: "中风险 · 档案有邻近经验", cls: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
  low: { label: "低风险 · 档案直接相关", cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
};

const RESUME_STATUS: Record<string, { label: string; cls: string }> = {
  draft: { label: "草稿", cls: "bg-slate-500/15 text-slate-300 border-slate-500/30" },
  pending: { label: "生成中", cls: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
  generated: { label: "已生成", cls: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30" },
  exported: { label: "已导出", cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
  failed: { label: "生成失败", cls: "bg-rose-500/15 text-rose-300 border-rose-500/30" },
};

const HIGHLIGHT_OPTIONS = ["技术深度", "项目经验", "业务成果", "管理能力"];

const TEMPLATE_STYLES: Array<{
  value: ResumeTemplate; name: string; desc: string; accent: string; badge?: string;
}> = [
  { value: "default", name: "ATS 经典", desc: "招聘网站、国企、外企系统", accent: "#197998", badge: "推荐 · 解析稳定" },
  { value: "technical", name: "技术极简", desc: "开发、运维、数据、产品技术", accent: "#197998" },
  { value: "management", name: "管理商务", desc: "管理、运营、资深负责人岗位", accent: "#4d26c0" },
  { value: "compact", name: "一页紧凑", desc: "经历较多、页数优先", accent: "#5b36ca", badge: "一页优先" },
];

const templateName = (value?: string) =>
  TEMPLATE_STYLES.find((item) => item.value === value)?.name || "ATS 经典";

/** pending 超过该毫秒数就认为任务已中断（后端巡检 10 分钟判定，前端略放宽） */
const PENDING_STUCK_MS = 12 * 60 * 1000;
const isStuck = (r: Resume) =>
  r.status === "pending" && Date.now() - new Date(r.created_at).getTime() > PENDING_STUCK_MS;

/** 秒级耗时 → 可读文本 */
const fmtDuration = (ms: number) => {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s} 秒`;
  const m = Math.floor(s / 60);
  return m < 60 ? `${m} 分 ${s % 60} 秒` : `${Math.floor(m / 60)} 小时 ${m % 60} 分`;
};

const QTYPE: Record<string, { label: string; cls: string }> = {
  technical: { label: "技术", cls: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30" },
  project: { label: "项目", cls: "bg-violet-500/15 text-violet-300 border-violet-500/30" },
  behavior: { label: "行为面", cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
};

function ListPoints({ title, items }: { title: string; items?: string[] }) {
  if (!items?.length) return null;
  return (
    <div>
      <div className="text-xs text-slate-400 mb-1.5">{title}</div>
      {items.map((it, i) => (
        <div key={i} className="text-xs text-slate-300 mb-1 flex gap-2"><span className="text-cyan-400">▪</span><span>{it}</span></div>
      ))}
    </div>
  );
}

function InterviewPrepPanel({ prep, loading, preparing, onGenerate }: {
  prep: InterviewPrep | null; loading: boolean; preparing: boolean; onGenerate: (regen: boolean) => void;
}) {
  if (prep?.status === "pending" || preparing) return (
    <div className="rounded-xl border border-white/[0.07] p-14 flex flex-col items-center text-slate-500">
      <Loader2 className="w-8 h-8 animate-spin text-cyan-400 mb-3" />
      <p className="text-sm">AI 正在生成面试准备…通常需要 3–8 分钟</p>
      <p className="text-xs mt-1">岗位调研 → 面试提纲 → 题库（含标准答案）</p>
      <p className="text-xs mt-3 text-slate-600">推理模型逐段生成，页面每 5 秒自动刷新，可放心切走</p>
    </div>
  );
  if (loading) return (
    <div className="rounded-xl border border-white/[0.07] p-14 flex justify-center">
      <Loader2 className="w-6 h-6 animate-spin text-slate-500" />
    </div>
  );
  if (!prep) return (
    <div className="rounded-xl border border-dashed border-white/10 p-14 flex flex-col items-center text-slate-600">
      <ClipboardList className="w-10 h-10 mb-3 opacity-40" />
      <p className="text-sm mb-1">这份简历还没有面试准备</p>
      <p className="text-xs mb-5">AI 将生成岗位调研、面试提纲和带标准答案的题库，之后每次打开简历都能直接复习</p>
      <Button className="gradient-btn" onClick={() => onGenerate(false)}>
        <Sparkles className="w-4 h-4 mr-2" />生成面试准备
      </Button>
    </div>
  );
  const r = prep.research || {};
  const o = prep.outline || {};
  return (
    <div className="space-y-5">
      {prep.status === "failed" && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          <div className="font-semibold mb-1">上次生成失败</div>
          <div className="text-xs text-rose-300/80 mb-2 break-all">
            {prep.error_message || "未知错误，请重新生成"}
          </div>
          <div className="text-xs text-rose-300/60 mb-2">下方显示的是上一次成功生成的内容，重新生成成功后会被覆盖。</div>
          <Button size="sm" variant="outline" className="border-rose-500/40 text-rose-200 hover:bg-rose-500/15"
            onClick={() => onGenerate(true)}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />重新生成
          </Button>
        </div>
      )}
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-500">更新于 {new Date(prep.updated_at).toLocaleString("zh-CN")}</span>
        <Button variant="outline" size="sm" className="border-white/10 text-slate-300 hover:bg-white/[0.06]" onClick={() => onGenerate(true)}>
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />重新生成
        </Button>
      </div>

      {/* 岗位调研 */}
      <div className="rounded-xl bg-cyan-500/[0.05] border border-cyan-500/20 p-4 space-y-3">
        <div className="text-sm font-semibold text-cyan-300 flex items-center gap-1.5"><Target className="w-4 h-4" />岗位调研</div>
        {r.position_analysis && <p className="text-sm text-slate-300 leading-relaxed">{r.position_analysis}</p>}
        <div className="grid md:grid-cols-2 gap-3">
          <ListPoints title="公司 / 团队关注点" items={r.company_points} />
          <ListPoints title="行业热点考察方向" items={r.hot_topics} />
          <ListPoints title="面试官会深挖的点" items={r.interviewer_focus} />
          <ListPoints title="准备建议" items={r.advice} />
        </div>
      </div>

      {/* 面试提纲 */}
      <div className="rounded-xl bg-violet-500/[0.05] border border-violet-500/20 p-4 space-y-3">
        <div className="text-sm font-semibold text-violet-300 flex items-center gap-1.5"><GraduationCap className="w-4 h-4" />面试提纲</div>
        {(o.rounds || []).map((rd, i) => (
          <div key={i} className="rounded-lg bg-white/[0.03] border border-white/[0.06] p-3">
            <div className="flex justify-between text-sm mb-1.5">
              <span className="font-medium text-slate-200">{rd.stage}</span>
              {rd.duration && <span className="text-xs text-slate-500">{rd.duration}</span>}
            </div>
            <div className="grid md:grid-cols-2 gap-2">
              <ListPoints title="考察方向" items={rd.focus} />
              <ListPoints title="可能的问题" items={rd.likely_questions} />
            </div>
          </div>
        ))}
        <div className="grid md:grid-cols-2 gap-3">
          <ListPoints title="自我介绍要点" items={o.self_intro_points} />
          <ListPoints title="建议反问面试官" items={o.questions_to_ask} />
        </div>
      </div>

      {/* 题库 */}
      <div className="rounded-xl bg-emerald-500/[0.05] border border-emerald-500/20 p-4">
        <div className="text-sm font-semibold text-emerald-300 mb-2 flex items-center gap-1.5">
          <ClipboardList className="w-4 h-4" />题库（{prep.questions.length} 题）
        </div>
        <Accordion type="multiple" className="w-full">
          {prep.questions.map((q, i) => (
            <AccordionItem key={i} value={`q${i}`} className="border-white/[0.07]">
              <AccordionTrigger className="text-sm text-left hover:no-underline">
                <span className="flex items-start gap-2">
                  <span className={`chip shrink-0 mt-0.5 ${QTYPE[q.type]?.cls || "bg-slate-500/15 text-slate-300 border-slate-500/30"}`}>
                    {QTYPE[q.type]?.label || q.type}
                  </span>
                  <span>{q.question}</span>
                </span>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-slate-400 space-y-2">
                <p className="leading-relaxed">{q.reference_answer}</p>
                {!!q.key_points?.length && (
                  <div className="flex flex-wrap gap-1.5">
                    {q.key_points.map((k) => (
                      <span key={k} className="chip bg-emerald-500/10 text-emerald-300 border-emerald-500/20 text-[10px]">{k}</span>
                    ))}
                  </div>
                )}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </div>
  );
}

function SectionView({ sec }: { sec: ResumeSection }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <span className="w-1 h-4 rounded bg-gradient-to-b from-cyan-400 to-violet-500" />
        <span className="font-semibold text-sm text-slate-200">{sec.title}</span>
      </div>
      {sec.type === "summary" && <p className="text-sm text-slate-400 leading-relaxed">{sec.content}</p>}
      {sec.type === "skills" && (
        <div className="space-y-1.5">
          {Object.entries((sec.items || []).reduce((groups: Record<string, any[]>, skill: any) => {
            const category = skill.category || "其他技能";
            (groups[category] ||= []).push(skill);
            return groups;
          }, {})).map(([category, skills]) => (
            <div key={category} className="grid grid-cols-[max-content_1fr] gap-2 text-sm">
              <span className="font-medium text-cyan-300">{category}：</span>
              <span className="text-slate-300">
                {(skills as any[]).map((skill, index) => (
                  <span key={skill.name}>{index > 0 && <span className="text-slate-600"> · </span>}{skill.name}{skill.level ? `（${skill.level}）` : ""}</span>
                ))}
              </span>
            </div>
          ))}
        </div>
      )}
      {["experience", "projects"].includes(sec.type) && (sec.items || []).map((it: any, i: number) => (
        <div key={i} className="mb-3">
          <div className="flex justify-between text-sm">
            <span className="font-medium text-slate-200">
              {it.company || it.name} · {it.position || it.role}
            </span>
            <span className="text-xs text-slate-500">{it.period}</span>
          </div>
          {it.tech_stack && (
            <div className="flex flex-wrap gap-1 my-1">
              {it.tech_stack.map((t: string) => <span key={t} className="chip bg-cyan-500/10 text-cyan-300 border-cyan-500/20 text-[10px]">{t}</span>)}
            </div>
          )}
          <ul className="text-sm text-slate-400 space-y-0.5 mt-1">
            {(it.bullets || []).map((b: string, j: number) => <li key={j} className="flex gap-2"><span className="text-cyan-400">▪</span>{b}</li>)}
          </ul>
        </div>
      ))}
      {sec.type === "education" && (sec.items || []).map((it: any, i: number) => (
        <div key={i} className="flex justify-between text-sm text-slate-300">
          <span>{it.school} · {it.major}（{it.degree}）</span>
          <span className="text-xs text-slate-500">{it.period}</span>
        </div>
      ))}
      {sec.type === "certifications" && (sec.items || []).map((it: any, i: number) => (
        <div key={i} className="flex justify-between text-sm text-slate-300">
          <span>{it.name}{it.issuer ? ` · ${it.issuer}` : ""}</span>
          <span className="text-xs text-slate-500">{it.date}</span>
        </div>
      ))}
    </div>
  );
}

export default function ResumesPage() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [jds, setJds] = useState<JD[]>([]);
  const [active, setActive] = useState<Resume | null>(null);
  const [exportTemplate, setExportTemplate] = useState<ResumeTemplate>("default");
  const [genOpen, setGenOpen] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [delTarget, setDelTarget] = useState<Resume | null>(null);
  const [picked, setPicked] = useState<number[]>([]);
  const [placementTargets, setPlacementTargets] = useState<Record<number, string>>({});
  const [writeBackFlags, setWriteBackFlags] = useState<Record<number, boolean>>({});
  const [stats, setStats] = useState<ResumeStats | null>(null);
  const [applying, setApplying] = useState(false);
  const [confirmEnhanceOpen, setConfirmEnhanceOpen] = useState(false);
  const [truthConfirmed, setTruthConfirmed] = useState(false);
  const [tab, setTab] = useState("preview");
  const [prep, setPrep] = useState<InterviewPrep | null>(null);
  const [prepLoading, setPrepLoading] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [pref, setPref] = useState({
    jd_id: "", target_level: "senior", page_limit: "1",
    language: "zh", template: "default" as ResumeTemplate, highlight_direction: [] as string[],
  });

  // 返回最新列表：补强后要同步刷新 active，否则详情区还是旧内容
  const reload = async (): Promise<Resume[]> => {
    try {
      const rs = await listResumes();
      setResumes(rs);
      return rs;
    } catch {
      return [];
    }
  };
  useEffect(() => { reload(); listJDs().then(setJds).catch(() => {}); }, []);

  // 存在后台生成中的简历时自动轮询，直到全部完成/失败
  const hasPending = resumes.some((r) => r.status === "pending");
  useEffect(() => {
    if (!hasPending) return;
    const t = setInterval(() => reload(), 4000);
    return () => clearInterval(t);
  }, [hasPending]);

  // 轮询期静默刷新，避免 loading 态闪一下把加载动画顶掉
  // silent=true 时出错也要保留现有状态：一旦把 prep 清成 null，prepPending 就变 false，
  // 轮询随之停止，界面会退回「还没有面试准备」——可后台任务其实还在跑。
  // 保留状态让定时器继续重试，等服务端把任务置为终态后自然收敛。
  const loadPrep = (silent = false) => {
    if (!active) return Promise.resolve();
    if (!silent) setPrepLoading(true);
    return getInterviewPrep(active.id)
      .then(setPrep)
      .catch(() => { if (!silent) setPrep(null); })
      .finally(() => { if (!silent) setPrepLoading(false); });
  };

  // 切换简历时重置 Tab 并加载已有面试准备
  useEffect(() => {
    setTab("preview");
    setPrep(null);
    setStats(null);
    if (active) {
      setExportTemplate((active.html_template as ResumeTemplate) || "default");
      void loadPrep();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active?.id]);

  // 内容统计（字数/预计页数/JD 关键词覆盖）：切换简历、保存编辑、应用补强、回滚后刷新
  const refreshStats = (r: Resume | null = active) => {
    if (!r || !["generated", "exported"].includes(r.status)) { setStats(null); return; }
    getResumeStats(r.id).then(setStats).catch(() => setStats(null));
  };
  useEffect(() => {
    refreshStats(active);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active?.id, active?.updated_at]);

  // 当前简历关联 JD 的解析结果：编辑器/历史组件本地算关键词覆盖用
  const jdParsed = jds.find((j) => j.id === active?.jd_id)?.parsed_data || null;

  // 面试准备是后台任务，pending 期间每 5 秒拉一次状态
  const prepPending = prep?.status === "pending";
  const prevPrepStatus = useRef<string | undefined>(prep?.status);
  useEffect(() => {
    if (!prepPending) return;
    const t = setInterval(() => void loadPrep(true), 5000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prepPending, active?.id]);

  // 后台任务落地时提示一次（pending → 终态）
  useEffect(() => {
    const prev = prevPrepStatus.current;
    prevPrepStatus.current = prep?.status;
    if (prev !== "pending") return;
    if (prep?.status === "generated") { toast.success("面试准备已生成"); reload(); }
    if (prep?.status === "failed") toast.error(prep.error_message || "面试准备生成失败");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prep?.status]);

  const doPrepare = async (regen: boolean) => {
    if (!active) return;
    setPreparing(true);
    try {
      const p = regen ? await regenerateInterview(active.id) : await prepareInterview(active.id);
      setPrep(p);
      if (active) setActive({ ...active, has_interview_prep: true });
      toast.success(p?.status === "pending" ? "任务已提交，AI 正在后台生成，完成后本页自动更新" : "面试准备已生成");
    } catch (e: any) { toast.error(e.message); }
    setPreparing(false);
  };

  const doGenerate = async () => {
    if (!pref.jd_id) return toast.warning("请选择一个 JD");
    setGenerating(true);
    try {
      await generateResume(pref.jd_id, {
        target_level: pref.target_level, page_limit: Number(pref.page_limit),
        language: pref.language, template: pref.template, highlight_direction: pref.highlight_direction,
      });
      toast.success("生成任务已提交，AI 正在后台生成，稍后自动刷新查看");
      setGenOpen(false);
      await reload();
    } catch (e: any) { toast.error(e.message); }
    setGenerating(false);
  };

  const doExport = async (r: Resume) => {
    setExporting(true);
    try {
      await exportResume(r, exportTemplate);
      toast.success("已导出（演示模式导出 HTML，联调后端后导出 PDF）");
      reload();
    } catch (e: any) { toast.error(e.message); }
    setExporting(false);
  };

  // 失败/中断任务一键重试：走后端 retry 接口，原地重跑，不新增简历记录
  const retryTask = async (r: Resume) => {
    if (!r.jd_id) return toast.error("该任务未关联 JD，请删除后用「生成定制简历」重新提交");
    try {
      await retryResume(r.id);
      toast.success("已重新提交生成任务，完成后列表自动刷新");
      reload();
    } catch (e: any) { toast.error(e.message); }
  };

  // 删除简历（失败任务、不想要的版本都走这里）。后端会连带清掉它的面试准备。
  const doDelete = async (r: Resume) => {
    setDeleting(true);
    try {
      await deleteResume(r.id);
      toast.success("已删除");
      setDelTarget(null);
      if (active?.id === r.id) setActive(null);
      await reload();
    } catch (e) { toast.error((e as Error).message); }
    setDeleting(false);
  };

  const candidates: Enhancement[] = active?.enhancements || [];
  const workOptions = (active?.resume_data?.sections || [])
    .filter((section) => section.type === "experience")
    .flatMap((section) => section.items || [])
    .filter((item) => /^work_experiences\[\d+\]$/.test(item.source_ref || ""))
    .map((item) => ({
      value: item.source_ref as string,
      label: `${item.company || "未命名公司"}${item.position ? ` · ${item.position}` : ""}`,
    }));
  const togglePick = (i: number) => {
    setPicked((current) => {
      if (current.includes(i)) return current.filter((value) => value !== i);
      const recommended = candidates[i]?.target_source_ref;
      const target = workOptions.some((option) => option.value === recommended)
        ? recommended!
        : workOptions[0]?.value;
      if (target) setPlacementTargets((old) => ({ ...old, [i]: target }));
      return [...current, i];
    });
  };

  // 切换简历时清空勾选，避免把 A 的选择带到 B 上
  useEffect(() => { setPicked([]); setPlacementTargets({}); setWriteBackFlags({}); }, [active?.id]);

  const doApplyEnhancements = async () => {
    if (!active || picked.length === 0) return;
    const placements = picked.map((index) => ({
      index,
      target_source_ref: placementTargets[index] || "",
      write_back_profile: !!writeBackFlags[index],
    }));
    if (placements.some((placement) => !placement.target_source_ref)) {
      toast.warning("请为每条建议选择要融入的已有公司经历");
      return;
    }
    setApplying(true);
    try {
      const res = await applyEnhancements(active.id, placements);
      const wb = res.written_back_to_profile || 0;
      toast.success(
        `已将 ${res.added_bullets} 条职责描述融入 ${res.applied} 条现有工作经历`
        + (wb ? `，其中 ${wb} 条已同步补充到档案中心` : ""),
      );
      setPicked([]);
      setPlacementTargets({});
      setWriteBackFlags({});
      setTruthConfirmed(false);
      setConfirmEnhanceOpen(false);
      const rs = await reload();
      const fresh = rs.find((r) => r.id === active.id);
      if (fresh) { setActive(fresh); refreshStats(fresh); }
    } catch (e) { toast.error((e as Error).message); }
    setApplying(false);
  };

  const pendingCount = resumes.filter((r) => r.status === "pending").length;
  const failedCount = resumes.filter((r) => r.status === "failed").length;

  return (
    <div>
      <PageHeader title="简历工坊" desc="一岗一版：JD × 档案 × 偏好 → AI 定制简历"
        actions={<Button className="gradient-btn" onClick={() => setGenOpen(true)}><Wand2 className="w-4 h-4 mr-2" />生成定制简历</Button>} />

      <div className="grid xl:grid-cols-5 gap-4">
        {/* 简历列表（含任务监控） */}
        <div className="xl:col-span-2 space-y-3">
          {/* 任务监控条：生成中/失败一目了然 */}
          <div className="glass px-4 py-2.5 flex items-center gap-4 text-xs">
            <span className="font-semibold text-slate-300">任务监控</span>
            <span className="text-slate-400">共 {resumes.length} 个</span>
            {pendingCount > 0 && (
              <span className="flex items-center gap-1.5 text-amber-300">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />生成中 {pendingCount}，页面每 4 秒自动刷新
              </span>
            )}
            {failedCount > 0 && <span className="text-rose-300">失败 {failedCount}，可在卡片上重试</span>}
            {pendingCount === 0 && failedCount === 0 && resumes.length > 0 && (
              <span className="text-emerald-300">全部完成</span>
            )}
          </div>
          {resumes.length === 0 && (
            <div className="glass p-10 text-center text-slate-600 text-sm">还没有简历，点击右上角生成第一份</div>
          )}
          {resumes.map((r, i) => (
            <motion.button
              key={r.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
              onClick={() => setActive(r)}
              className={`w-full text-left glass glass-hover p-5 flex items-center gap-4 ${active?.id === r.id ? "border-cyan-500/40 bg-cyan-500/[0.06]" : ""}`}
            >
              <ScoreRing value={r.match_score || 0} size={64} stroke={6} label="匹配" />
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm truncate">{r.version_name}</div>
                <div className="text-xs text-slate-500 mt-1">
                  {new Date(r.created_at).toLocaleDateString("zh-CN")} · {templateName(r.html_template)} · 目标 {r.preferences?.page_limit || 1} 页
                  {r.status === "pending" && <span className="text-amber-300"> · 已等待 {fmtDuration(Date.now() - new Date(r.created_at).getTime())}</span>}
                  {(r.status === "generated" || r.status === "exported") && r.updated_at && (
                    <span className="text-slate-500"> · 耗时 {fmtDuration(new Date(r.updated_at).getTime() - new Date(r.created_at).getTime())}</span>
                  )}
                </div>
                <span className={`chip mt-2 ${RESUME_STATUS[r.status]?.cls}`} title={r.error_message || undefined}>
                  {r.status === "pending" && <Loader2 className="w-3 h-3 mr-1 inline animate-spin" />}
                  {RESUME_STATUS[r.status]?.label || r.status}
                </span>
                {r.has_interview_prep && (
                  <span className="chip mt-2 ml-1.5 bg-emerald-500/15 text-emerald-300 border-emerald-500/30">面试就绪</span>
                )}
                {(r.status === "failed" || isStuck(r)) && (
                  <>
                    <span
                      className="chip mt-2 ml-1.5 bg-cyan-500/15 text-cyan-300 border-cyan-500/30 cursor-pointer hover:bg-cyan-500/25"
                      onClick={(e) => { e.stopPropagation(); retryTask(r); }}
                    >
                      <RefreshCw className="w-3 h-3 mr-1 inline" />重试
                    </span>
                    <span
                      className="chip mt-2 ml-1.5 bg-rose-500/15 text-rose-300 border-rose-500/30 cursor-pointer hover:bg-rose-500/25"
                      onClick={(e) => { e.stopPropagation(); setDelTarget(r); }}
                    >
                      <Trash2 className="w-3 h-3 mr-1 inline" />删除
                    </span>
                  </>
                )}
                {r.status === "failed" && r.error_message && (
                  <div className="mt-1.5 text-[11px] leading-relaxed text-rose-300/80 break-all" title={r.error_message}>
                    {r.error_message.length > 80 ? r.error_message.slice(0, 80) + "…" : r.error_message}
                  </div>
                )}
              </div>
              <FileText className="w-5 h-5 text-slate-600 shrink-0" />
            </motion.button>
          ))}
        </div>

        {/* 详情预览 */}
        <div className="xl:col-span-3">
          {!active ? (
            <div className="glass p-24 flex flex-col items-center justify-center text-slate-600">
              <Sparkles className="w-12 h-12 mb-3 opacity-40" />
              <p className="text-sm">选择左侧简历查看详情</p>
            </div>
          ) : (
            <motion.div key={active.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass p-6 space-y-5">
              <div className="flex items-start justify-between pb-4 border-b border-white/[0.07]">
                <div>
                  <h3 className="text-lg font-bold gradient-text">{active.resume_data?.header?.name}</h3>
                  <p className="text-sm text-slate-400">{active.resume_data?.header?.title}</p>
                  <p className="text-xs text-slate-500 mt-1">{Object.values(active.resume_data?.header?.contact || {}).filter(Boolean).join(" · ")}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Select value={exportTemplate} onValueChange={(v) => setExportTemplate(v as ResumeTemplate)}>
                    <SelectTrigger className="w-36 bg-white/[0.05] border-white/10" aria-label="导出风格">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
                      {TEMPLATE_STYLES.map((style) => (
                        <SelectItem key={style.value} value={style.value}>{style.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button className="gradient-btn" onClick={() => doExport(active)}
                    disabled={exporting || active.status === "pending" || active.status === "failed"}>
                    {exporting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                    导出
                  </Button>
                  <Button variant="outline" className="border-rose-500/40 text-rose-300 hover:bg-rose-500/15"
                    onClick={() => setDelTarget(active)}>
                    <Trash2 className="w-4 h-4 mr-2" />删除
                  </Button>
                </div>
              </div>

              {active.status === "pending" && !isStuck(active) && (
                <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
                  <Loader2 className="w-4 h-4 animate-spin" /> AI 正在后台生成这份简历，通常需要 2–5 分钟，完成后列表会自动刷新。
                </div>
              )}
              {isStuck(active) && (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
                  <div className="font-semibold mb-1">生成已超时未返回</div>
                  <div className="text-xs text-amber-300/80 mb-2">
                    任务等待已超过 12 分钟，多半是被服务重启打断或模型迟迟未返回。可点「重试」原地重新生成。
                  </div>
                  <Button size="sm" variant="outline" className="border-amber-500/40 text-amber-200 hover:bg-amber-500/15"
                    onClick={() => retryTask(active)}>
                    <RefreshCw className="w-3.5 h-3.5 mr-1.5" />重试生成
                  </Button>
                </div>
              )}
              {active.status === "failed" && (
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                  <div className="font-semibold mb-1">生成失败</div>
                  <div className="text-xs text-rose-300/80 break-all">{active.error_message || "未知错误，请重新生成"}</div>
                </div>
              )}

              <Tabs value={tab} onValueChange={setTab}>
                <TabsList className="bg-white/[0.05]">
                  <TabsTrigger value="preview"><FileText className="w-4 h-4 mr-1.5" />简历预览</TabsTrigger>
                  {["generated", "exported"].includes(active.status) && (
                    <TabsTrigger value="edit"><Pencil className="w-4 h-4 mr-1.5" />编辑</TabsTrigger>
                  )}
                  {["generated", "exported"].includes(active.status) && (
                    <TabsTrigger value="history"><History className="w-4 h-4 mr-1.5" />历史</TabsTrigger>
                  )}
                  <TabsTrigger value="interview">
                    <ClipboardList className="w-4 h-4 mr-1.5" />面试准备
                    {active.has_interview_prep && <span className="ml-1.5 w-1.5 h-1.5 rounded-full bg-emerald-400" />}
                  </TabsTrigger>
                  {candidates.length > 0 && (
                    <TabsTrigger value="enhance">
                      <Sparkles className="w-4 h-4 mr-1.5" />经历优化
                      <span className="ml-1.5 rounded-full bg-amber-400/20 text-amber-300 px-1.5 text-[10px]">
                        {candidates.length}
                      </span>
                    </TabsTrigger>
                  )}
                </TabsList>

                <TabsContent value="preview" className="space-y-5 mt-4">
                  {stats && (
                    <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] px-4 py-2.5 flex items-center gap-4 text-xs flex-wrap">
                      <span className="text-slate-400">字数 <b className="text-slate-200">{stats.char_count}</b></span>
                      <span className="text-slate-400">预计 <b className="text-slate-200">{stats.estimated_pages}</b> 页</span>
                      <span className="text-slate-400">条目 <b className="text-slate-200">{stats.item_count}</b> · bullets <b className="text-slate-200">{stats.bullet_count}</b></span>
                      {stats.keyword_coverage !== null && (
                        <span className="text-slate-400">
                          JD 关键词覆盖 <b className="text-cyan-300">{stats.keyword_coverage}%</b>（{stats.keyword_covered}/{stats.keyword_total}）
                        </span>
                      )}
                      {!!stats.missing_keywords.length && (
                        <span className="text-slate-500" title={stats.missing_keywords.join("、")}>
                          未覆盖：{stats.missing_keywords.slice(0, 4).join("、")}{stats.missing_keywords.length > 4 ? "…" : ""}
                        </span>
                      )}
                    </div>
                  )}
                  {(active.resume_data?.sections || []).map((sec, i) => <SectionView key={i} sec={sec} />)}

                  {!!active.resume_data?.match_details?.length && (
                    <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/[0.04] overflow-hidden">
                      <div className="px-4 py-2.5 text-sm font-semibold text-cyan-300 border-b border-cyan-500/15">JD 要求与档案证据</div>
                      <div className="divide-y divide-white/[0.06]">
                        {active.resume_data.match_details.map((detail, index) => (
                          <div key={index} className="grid md:grid-cols-[1.2fr_.8fr_1.2fr] gap-3 px-4 py-2.5 text-xs">
                            <div><span className="text-slate-500">要求：</span><span className="text-slate-200">{detail.requirement}</span></div>
                            <div className={detail.status === "direct" ? "text-emerald-300" : detail.status === "adjacent" ? "text-amber-300" : "text-rose-300"}>
                              {detail.status === "direct" ? "直接匹配" : detail.status === "adjacent" ? "邻近经验" : "档案缺失"}
                            </div>
                            <div className="text-slate-400">{detail.resume_usage || (detail.evidence_refs.length ? detail.evidence_refs.join("、") : "未写入正式简历")}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="grid md:grid-cols-3 gap-3 pt-4 border-t border-white/[0.07]">
                    <div className="rounded-xl bg-emerald-500/[0.07] border border-emerald-500/20 p-3.5">
                      <div className="text-xs text-emerald-300 mb-2 flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" />强匹配</div>
                      {active.highlights.map((h) => <div key={h} className="text-xs text-slate-300 mb-1">· {h}</div>)}
                    </div>
                    <div className="rounded-xl bg-amber-500/[0.07] border border-amber-500/20 p-3.5">
                      <div className="text-xs text-amber-300 mb-2 flex items-center gap-1"><AlertTriangle className="w-3.5 h-3.5" />待补强</div>
                      {active.gaps.map((g) => <div key={g} className="text-xs text-slate-300 mb-1">· {g}</div>)}
                    </div>
                    <div className="rounded-xl bg-violet-500/[0.07] border border-violet-500/20 p-3.5">
                      <div className="text-xs text-violet-300 mb-2 flex items-center gap-1"><Lightbulb className="w-3.5 h-3.5" />AI 建议</div>
                      {active.suggestions.map((s) => <div key={s} className="text-xs text-slate-300 mb-1">· {s}</div>)}
                    </div>
                  </div>
                </TabsContent>

                {["generated", "exported"].includes(active.status) && (
                  <TabsContent value="edit" className="mt-4">
                    <ResumeEditor
                      key={`${active.id}-${active.updated_at || ""}`}
                      resume={active}
                      jdParsed={jdParsed}
                      onSaved={(updated) => { setActive(updated); reload(); refreshStats(updated); }}
                      onCancel={() => setTab("preview")}
                    />
                  </TabsContent>
                )}

                {["generated", "exported"].includes(active.status) && (
                  <TabsContent value="history" className="mt-4">
                    <ResumeHistory
                      resume={active}
                      jdParsed={jdParsed}
                      onRolledBack={(updated) => { setActive(updated); reload(); refreshStats(updated); setTab("preview"); }}
                    />
                  </TabsContent>
                )}

                <TabsContent value="interview" className="mt-4">
                  <InterviewPrepPanel prep={prep} loading={prepLoading} preparing={preparing} onGenerate={doPrepare} />
                </TabsContent>

                {candidates.length > 0 && (
                  <TabsContent value="enhance" className="mt-4 space-y-4">
                    <div className="rounded-xl border border-cyan-500/25 bg-cyan-500/[0.06] p-4">
                      <div className="flex items-start gap-2.5">
                        <Sparkles className="w-4 h-4 text-cyan-300 mt-0.5 shrink-0" />
                        <div className="text-xs leading-relaxed text-slate-300 space-y-1">
                          <div className="font-semibold text-sm text-cyan-200">把漏写的技术经历融入已有公司</div>
                          <p>选择你确实做过的职责或技术，并指定发生在哪段现有工作经历中。应用后会自然加入该公司的职责描述，不创建新项目，也不会在正式简历显示系统标志。</p>
                        </div>
                      </div>
                    </div>

                    {candidates.map((c, i) => {
                      const on = picked.includes(i);
                      const risk = RISK_STYLE[c.risk] || RISK_STYLE.medium;
                      return (
                        <div key={i} className={`rounded-xl border p-4 transition-colors ${
                          on ? "border-amber-500/40 bg-amber-500/[0.06]" : "border-white/[0.07] bg-white/[0.02]"
                        }`}>
                          <div className="flex items-start gap-3">
                            <Checkbox
                              checked={on}
                              onCheckedChange={() => togglePick(i)}
                              className="mt-0.5"
                            />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap cursor-pointer" onClick={() => togglePick(i)}>
                                <span className="font-semibold text-sm">{c.legacy ? "旧版建议职责" : "建议补充职责"}</span>
                                <span className={`chip ${risk.cls}`}>{risk.label}</span>
                              </div>
                              {c.gap && <div className="text-xs text-slate-400 mt-1.5">JD 缺口：{c.gap}</div>}
                              {c.basis && <div className="text-xs text-slate-500 mt-1">建议依据：{c.basis}</div>}
                              <ul className="mt-2.5 space-y-1">
                                {(c.suggested_bullets || c.project?.bullets || []).map((bullet, j) => (
                                  <li key={j} className="text-xs text-slate-300 leading-relaxed">· {bullet}</li>
                                ))}
                              </ul>
                              {on && (
                                <div className="mt-3 space-y-2">
                                  <div className="space-y-1.5">
                                    <Label className="text-[11px] text-slate-400">融入已有公司经历</Label>
                                    <Select value={placementTargets[i] || ""} onValueChange={(value) => setPlacementTargets((old) => ({ ...old, [i]: value }))}>
                                      <SelectTrigger className="bg-white/[0.04] border-white/10"><SelectValue placeholder="选择公司和职位" /></SelectTrigger>
                                      <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
                                        {workOptions.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}
                                      </SelectContent>
                                    </Select>
                                  </div>
                                  <label className="flex items-start gap-2 cursor-pointer">
                                    <Checkbox
                                      checked={!!writeBackFlags[i]}
                                      onCheckedChange={(v) => setWriteBackFlags((old) => ({ ...old, [i]: v === true }))}
                                      className="mt-0.5"
                                    />
                                    <span className="text-[11px] text-slate-400 leading-relaxed">
                                      同时补充到档案中心（写入该段工作经历的「成果」）——这段经历确认后就是事实，
                                      以后生成其他简历时系统会直接使用，不必每份简历重复确认
                                    </span>
                                  </label>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}

                    <Button className="w-full gradient-btn" disabled={applying || picked.length === 0}
                      onClick={() => { setTruthConfirmed(false); setConfirmEnhanceOpen(true); }}>
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                      {picked.length === 0 ? "选择要融入的职责建议" : `确认并融入选中的 ${picked.length} 条`}
                    </Button>
                  </TabsContent>
                )}
              </Tabs>
            </motion.div>
          )}
        </div>
      </div>

      <AlertDialog open={confirmEnhanceOpen} onOpenChange={setConfirmEnhanceOpen}>
        <AlertDialogContent className="bg-[#0b1120] border-white/10 text-slate-100">
          <AlertDialogHeader>
            <AlertDialogTitle>确认融入所选公司经历</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-400 space-y-3">
              <span className="block">确认后，建议描述会直接加入所选公司的工作职责列表，正式简历不会显示系统来源标志。</span>
              <label className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/[0.08] p-3 text-amber-100 cursor-pointer">
                <Checkbox checked={truthConfirmed} onCheckedChange={(v) => setTruthConfirmed(v === true)} className="mt-0.5" />
                <span>我确认这些职责或技术确实发生在所选公司经历中，只是原档案没有完整记录，并已逐条核对描述。</span>
              </label>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>返回核实</AlertDialogCancel>
            <AlertDialogAction disabled={!truthConfirmed || applying} onClick={(e) => {
              e.preventDefault();
              void doApplyEnhancements();
            }} className="gradient-btn">
              {applying && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}确认采用
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 生成对话框 */}
      <Dialog open={genOpen} onOpenChange={setGenOpen}>
        <DialogContent className="bg-[#0b1120] border-white/10 text-slate-100 max-w-md">
          <DialogHeader><DialogTitle className="gradient-text">生成定制简历</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-xs">选择 JD</Label>
              <Select value={pref.jd_id} onValueChange={(v) => setPref({ ...pref, jd_id: v })}>
                <SelectTrigger className="bg-white/[0.05] border-white/10"><SelectValue placeholder="选择已解析的 JD" /></SelectTrigger>
                <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
                  {jds.map((j) => <SelectItem key={j.id} value={j.id}>{j.company_name} · {j.position_title}</SelectItem>)}
                </SelectContent>
              </Select>
              {jds.length === 0 && <p className="text-xs text-amber-300">暂无 JD，请先到「JD 解析」页解析一个</p>}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-slate-400 text-xs">目标级别</Label>
                <Select value={pref.target_level} onValueChange={(v) => setPref({ ...pref, target_level: v })}>
                  <SelectTrigger className="bg-white/[0.05] border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
                    <SelectItem value="junior">初级</SelectItem>
                    <SelectItem value="mid">中级</SelectItem>
                    <SelectItem value="senior">高级</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-slate-400 text-xs">页数限制</Label>
                <Select value={pref.page_limit} onValueChange={(v) => setPref({ ...pref, page_limit: v })}>
                  <SelectTrigger className="bg-white/[0.05] border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
                    <SelectItem value="1">单页</SelectItem>
                    <SelectItem value="2">两页</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-slate-400 text-xs">语言</Label>
                <Select value={pref.language} onValueChange={(v) => setPref({ ...pref, language: v })}>
                  <SelectTrigger className="bg-white/[0.05] border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
                    <SelectItem value="zh">中文</SelectItem>
                    <SelectItem value="en">English</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label className="text-slate-400 text-xs">简历风格</Label>
              <div className="grid grid-cols-2 gap-2">
                {TEMPLATE_STYLES.map((style) => {
                  const selected = pref.template === style.value;
                  return (
                    <button key={style.value} type="button" onClick={() => setPref({ ...pref, template: style.value })}
                      className={`relative rounded-xl border p-3 text-left transition-all ${
                        selected ? "border-cyan-400/60 bg-cyan-500/[0.08]" : "border-white/10 bg-white/[0.025] hover:border-white/20"
                      }`}>
                      <div className="mb-2 h-12 rounded-md bg-white p-2 shadow-inner">
                        <div className="h-1.5 w-2/5 rounded-sm" style={{ background: style.accent }} />
                        <div className="mt-1 h-px w-full bg-slate-300" />
                        <div className="mt-1.5 space-y-1">
                          <div className="h-px w-4/5 bg-slate-400" />
                          <div className="h-px w-full bg-slate-300" />
                          <div className="h-px w-3/5 bg-slate-300" />
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-semibold text-slate-200">{style.name}</span>
                        {selected && <CheckCircle2 className="h-3.5 w-3.5 text-cyan-300" />}
                      </div>
                      <div className="mt-0.5 text-[10px] leading-relaxed text-slate-500">{style.desc}</div>
                      {style.badge && <span className="mt-1.5 inline-flex text-[9px] text-cyan-300">{style.badge}</span>}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="space-y-2">
              <Label className="text-slate-400 text-xs">突出方向（可多选）</Label>
              <div className="flex flex-wrap gap-3">
                {HIGHLIGHT_OPTIONS.map((o) => (
                  <label key={o} className="flex items-center gap-1.5 text-sm text-slate-300 cursor-pointer">
                    <Checkbox
                      checked={pref.highlight_direction.includes(o)}
                      onCheckedChange={(c) => setPref({
                        ...pref,
                        highlight_direction: c ? [...pref.highlight_direction, o] : pref.highlight_direction.filter((x) => x !== o),
                      })}
                    />{o}
                  </label>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/[0.05] px-3 py-2 text-[11px] leading-relaxed text-slate-400">
              系统会按 JD 证据优先组织：岗位摘要 → 分类技能 → 高相关工作/项目 → 教育资质，并自动在宽松、标准、紧凑排版间选择，使内容尽量充实且严格不超过目标页数。
            </div>
            <Button className="gradient-btn w-full h-11" onClick={doGenerate} disabled={generating}>
              {generating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Wand2 className="w-4 h-4 mr-2" />}
              {generating ? "AI 生成中…" : "开始生成"}
            </Button>
            {generating && (
              <p className="text-xs text-slate-500 text-center mt-2">
                推理模型生成约需 1–3 分钟，请保持页面打开，不要刷新或关闭。
              </p>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!delTarget} onOpenChange={(o) => !o && !deleting && setDelTarget(null)}>
        <AlertDialogContent className="bg-[#0b1120] border-white/10 text-slate-200">
          <AlertDialogHeader>
            <AlertDialogTitle>删除这份简历？</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-400">
              「{delTarget?.version_name}」以及它的面试准备会被永久删除，无法恢复。
              {delTarget?.status === "pending" && (
                <span className="block mt-2 text-amber-300">
                  这份还在生成中，删除后正在跑的任务也会被丢弃。
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-white/10 text-slate-300 hover:bg-white/5">取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-rose-600 text-white hover:bg-rose-500"
              disabled={deleting}
              onClick={(e) => {
                e.preventDefault();
                if (delTarget) void doDelete(delTarget);
              }}
            >
              {deleting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              确认删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
