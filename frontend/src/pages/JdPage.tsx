import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Building2, Loader2, ScanSearch, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/PageHeader";
import { ScoreRing } from "@/components/ScoreRing";
import { listJDs, parseJD } from "@/lib/db";
import type { JD, JDParsed } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

function ChipList({ title, items, color }: { title: string; items?: string[]; color: string }) {
  if (!items?.length) return null;
  return (
    <div>
      <div className="text-xs text-slate-500 mb-1.5">{title}</div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((k) => <span key={k} className={`chip ${color}`}>{k}</span>)}
      </div>
    </div>
  );
}

function ReqList({ title, items, dot }: { title: string; items?: string[]; dot: string }) {
  if (!items?.length) return null;
  return (
    <div>
      <div className="text-xs text-slate-500 mb-1.5">{title}</div>
      <ul className="space-y-1">
        {items.map((r) => (
          <li key={r} className="text-sm text-slate-300 flex gap-2">
            <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />{r}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function JdPage() {
  const [jds, setJds] = useState<JD[]>([]);
  const [text, setText] = useState("");
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [parsing, setParsing] = useState(false);
  const [result, setResult] = useState<JDParsed | null>(null);
  const [preview, setPreview] = useState<{ profile_completeness: number; estimated_match: number } | null>(null);

  useEffect(() => { listJDs().then(setJds).catch(() => {}); }, []);

  const doParse = async () => {
    if (text.trim().length < 10) return toast.warning("请粘贴至少 10 个字的 JD 原文");
    setParsing(true);
    setResult(null);
    try {
      const res = await parseJD(text, company || undefined, position || undefined);
      setResult(res.parsed_data);
      setPreview(res.match_preview);
      setJds(await listJDs());
      toast.success("JD 解析完成");
    } catch (e: any) { toast.error(e.message); }
    setParsing(false);
  };

  return (
    <div>
      <PageHeader title="JD 解析" desc="粘贴岗位描述，AI 提取硬性要求、关键词与加分项" />

      <div className="grid xl:grid-cols-2 gap-4">
        {/* 输入 */}
        <motion.div initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} className="glass p-6 space-y-4 h-fit">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-xs">公司（可选，AI 自动识别）</Label>
              <Input className="bg-white/[0.05] border-white/10" value={company} onChange={(e) => setCompany(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-xs">岗位（可选）</Label>
              <Input className="bg-white/[0.05] border-white/10" value={position} onChange={(e) => setPosition(e.target.value)} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-slate-400 text-xs">JD 原文</Label>
            <Textarea rows={12} placeholder="把招聘网站上的岗位描述完整粘贴到这里……"
              className="bg-white/[0.05] border-white/10 text-sm leading-relaxed"
              value={text} onChange={(e) => setText(e.target.value)} />
          </div>
          <Button className="gradient-btn w-full h-11" onClick={doParse} disabled={parsing}>
            {parsing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ScanSearch className="w-4 h-4 mr-2" />}
            {parsing ? "AI 解析中…" : "开始解析"}
          </Button>

          {/* 历史 */}
          <div className="pt-2 border-t border-white/[0.07]">
            <div className="text-xs text-slate-500 mb-2">解析历史（{jds.length}）</div>
            <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
              {jds.map((j) => (
                <button key={j.id}
                  onClick={() => { setResult(j.parsed_data); setPreview(null); }}
                  className="w-full text-left p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:border-cyan-500/30 transition-colors">
                  <div className="text-sm font-medium flex items-center gap-2">
                    <Building2 className="w-3.5 h-3.5 text-cyan-400" />{j.company_name || "未知公司"} · {j.position_title || "未知岗位"}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{new Date(j.created_at).toLocaleString("zh-CN")}</div>
                </button>
              ))}
            </div>
          </div>
        </motion.div>

        {/* 结果 */}
        <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} className="glass p-6">
          {parsing && (
            <div className="flex flex-col items-center justify-center py-24 gap-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-400 to-violet-600 flex items-center justify-center animate-pulse shadow-[0_0_40px_-8px] shadow-cyan-500/70">
                <Sparkles className="w-7 h-7 text-white" />
              </div>
              <p className="text-sm text-slate-400">Kimi AI 正在深度解析岗位…</p>
            </div>
          )}
          {!parsing && !result && (
            <div className="flex flex-col items-center justify-center py-24 text-slate-600">
              <ScanSearch className="w-12 h-12 mb-3 opacity-40" />
              <p className="text-sm">解析结果将展示在这里</p>
            </div>
          )}
          {!parsing && result && (
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-bold gradient-text">{result.company || "未知公司"}</h3>
                  <p className="text-sm text-slate-400">{result.position}</p>
                  <div className="flex gap-2 mt-2 text-xs text-slate-500">
                    {result.education_requirement && <span className="chip bg-white/[0.06] text-slate-300 border-white/10">{result.education_requirement}</span>}
                    {result.experience_years && <span className="chip bg-white/[0.06] text-slate-300 border-white/10">{result.experience_years}</span>}
                    {result.salary_range && <span className="chip bg-emerald-500/15 text-emerald-300 border-emerald-500/30">{result.salary_range}</span>}
                  </div>
                </div>
                {preview && (
                  <div className="flex gap-3">
                    <ScoreRing value={preview.profile_completeness} size={72} stroke={6} label="完整度" color="#34d399" />
                    <ScoreRing value={preview.estimated_match} size={72} stroke={6} label="预估匹配" />
                  </div>
                )}
              </div>
              <ReqList title="硬性要求" items={result.hard_requirements} dot="bg-rose-400" />
              <ReqList title="核心职责" items={result.core_responsibilities} dot="bg-cyan-400" />
              <ReqList title="软性要求" items={result.soft_requirements} dot="bg-violet-400" />
              <ReqList title="加分项" items={result.bonus_items} dot="bg-amber-400" />
              <div className="grid md:grid-cols-2 gap-4 pt-2 border-t border-white/[0.07]">
                <ChipList title="中文关键词" items={result.keywords} color="bg-cyan-500/15 text-cyan-300 border-cyan-500/30" />
                <ChipList title="ATS 关键词" items={result.ats_keywords} color="bg-violet-500/15 text-violet-300 border-violet-500/30" />
              </div>
            </motion.div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
