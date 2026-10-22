import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight, Check, CloudUpload, Download, FileSpreadsheet,
  FileText, FileType2, Loader2, Wand2,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/PageHeader";
import { analyzeForm, downloadForm, fillForm, listForms, mapForm, uploadForm } from "@/lib/db";
import type { FormRecord } from "@/lib/types";
import { Button } from "@/components/ui/button";

const STEPS = [
  { key: "uploaded", label: "已上传" },
  { key: "analyzed", label: "已解析" },
  { key: "mapped", label: "已映射" },
  { key: "filled", label: "已填充" },
];

const TYPE_ICON: Record<string, any> = { pdf: FileType2, word: FileText, excel: FileSpreadsheet };

function Stepper({ status }: { status: string }) {
  const idx = STEPS.findIndex((s) => s.key === status);
  return (
    <div className="flex items-center gap-1.5">
      {STEPS.map((s, i) => (
        <div key={s.key} className="flex items-center gap-1.5">
          <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold transition-all ${
            i <= idx ? "bg-gradient-to-br from-cyan-400 to-violet-600 text-white shadow-[0_0_10px_-2px] shadow-cyan-500/60" : "bg-white/[0.07] text-slate-500"
          }`}>
            {i < idx ? <Check className="w-3 h-3" /> : i + 1}
          </div>
          <span className={`text-[10px] ${i <= idx ? "text-cyan-300" : "text-slate-600"}`}>{s.label}</span>
          {i < STEPS.length - 1 && <div className={`w-5 h-px ${i < idx ? "bg-cyan-500/50" : "bg-white/[0.08]"}`} />}
        </div>
      ))}
    </div>
  );
}

export default function FormsPage() {
  const [forms, setForms] = useState<FormRecord[]>([]);
  const [active, setActive] = useState<FormRecord | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const reload = async () => {
    const list = await listForms();
    setForms(list);
    if (active) setActive(list.find((f) => f.id === active.id) || null);
  };
  useEffect(() => { listForms().then(setForms).catch(() => {}); }, []);

  const onUpload = async (file: File) => {
    setBusy("upload");
    try {
      const rec = await uploadForm(file);
      toast.success("上传成功，点击「解析」识别表单字段");
      await reload();
      setActive(rec);
    } catch (e: any) { toast.error(e.message); }
    setBusy(null);
  };

  const doAnalyze = async (f: FormRecord) => {
    setBusy("analyze");
    try { await analyzeForm(f.id); toast.success("解析完成"); await reload(); }
    catch (e: any) { toast.error(e.message); }
    setBusy(null);
  };

  const doMap = async (f: FormRecord) => {
    setBusy("map");
    try { await mapForm(f.id); toast.success("AI 字段映射完成"); await reload(); }
    catch (e: any) { toast.error(e.message); }
    setBusy(null);
  };

  const doFill = async (f: FormRecord) => {
    setBusy("fill");
    try { await fillForm(f.id); toast.success("填充完成，可以下载了"); await reload(); }
    catch (e: any) { toast.error(e.message); }
    setBusy(null);
  };

  const doDownload = async (f: FormRecord) => {
    try { await downloadForm(f); toast.success("已下载"); }
    catch (e: any) { toast.error(e.message); }
  };

  return (
    <div>
      <PageHeader title="报名表处理" desc="事业单位/国企报名表：上传 → 解析 → AI 映射 → 自动填充 → 下载" />

      {/* 上传区 */}
      <motion.div
        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
        onClick={() => fileRef.current?.click()}
        className="glass glass-hover border-dashed !border-cyan-500/30 p-8 mb-6 flex flex-col items-center justify-center cursor-pointer group"
      >
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500/25 to-violet-500/25 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
          {busy === "upload" ? <Loader2 className="w-7 h-7 text-cyan-300 animate-spin" /> : <CloudUpload className="w-7 h-7 text-cyan-300" />}
        </div>
        <div className="font-semibold text-sm">点击上传报名表</div>
        <div className="text-xs text-slate-500 mt-1">支持 PDF / DOC / DOCX / XLS / XLSX，最大 20MB</div>
        <input ref={fileRef} type="file" accept=".pdf,.doc,.docx,.xls,.xlsx" className="hidden"
          onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])} />
      </motion.div>

      <div className="grid xl:grid-cols-5 gap-4">
        {/* 列表 */}
        <div className="xl:col-span-2 space-y-3">
          {forms.map((f) => {
            const Icon = TYPE_ICON[f.file_type] || FileText;
            return (
              <button key={f.id} onClick={() => setActive(f)}
                className={`w-full text-left glass glass-hover p-4 ${active?.id === f.id ? "border-cyan-500/40 bg-cyan-500/[0.06]" : ""}`}>
                <div className="flex items-center gap-3 mb-2.5">
                  <Icon className="w-5 h-5 text-cyan-300 shrink-0" />
                  <span className="text-sm font-medium truncate flex-1">{f.original_filename}</span>
                  <span className="text-[10px] text-slate-500">{f.file_type.toUpperCase()}</span>
                </div>
                <Stepper status={f.status} />
              </button>
            );
          })}
          {forms.length === 0 && <div className="glass p-10 text-center text-slate-600 text-sm">暂无报名表</div>}
        </div>

        {/* 详情 */}
        <div className="xl:col-span-3">
          {!active ? (
            <div className="glass p-24 flex items-center justify-center text-slate-600 text-sm">选择左侧报名表查看处理详情</div>
          ) : (
            <motion.div key={active.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass p-6 space-y-5">
              <div className="flex items-center justify-between">
                <h3 className="font-bold">{active.original_filename}</h3>
                <Stepper status={active.status} />
              </div>

              {/* 操作按钮组 */}
              <div className="flex flex-wrap gap-2.5">
                <Button size="sm" className="gradient-btn" disabled={busy !== null}
                  onClick={() => doAnalyze(active)}>
                  {busy === "analyze" ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <ArrowRight className="w-4 h-4 mr-1" />}解析
                </Button>
                <Button size="sm" className="gradient-btn" disabled={busy !== null || active.status === "uploaded"}
                  onClick={() => doMap(active)}>
                  {busy === "map" ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Wand2 className="w-4 h-4 mr-1" />}AI 映射
                </Button>
                <Button size="sm" className="gradient-btn" disabled={busy !== null || !["mapped", "filled"].includes(active.status)}
                  onClick={() => doFill(active)}>
                  {busy === "fill" ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Check className="w-4 h-4 mr-1" />}填充
                </Button>
                <Button size="sm" variant="outline" className="border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10"
                  disabled={active.status !== "filled"} onClick={() => doDownload(active)}>
                  <Download className="w-4 h-4 mr-1" />下载
                </Button>
              </div>

              {/* 字段结构 */}
              {active.form_structure && (
                <div>
                  <div className="text-xs text-slate-500 mb-2">识别字段（{active.form_structure.field_count}）</div>
                  <div className="flex flex-wrap gap-1.5">
                    {active.form_structure.fields.map((fld) => (
                      <span key={fld.field_name} className="chip bg-white/[0.06] text-slate-300 border-white/10">{fld.field_name}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* 映射结果 */}
              {active.field_mapping && (
                <div>
                  <div className="text-xs text-slate-500 mb-2">AI 字段映射（表单字段 → 档案字段）</div>
                  <div className="space-y-2">
                    {active.field_mapping.mappings.map((m) => (
                      <div key={m.form_field} className="grid grid-cols-[110px_1fr_130px_90px] items-center gap-3 p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-xs">
                        <span className="font-medium text-slate-200 truncate">{m.form_field}</span>
                        <span className="text-slate-500 truncate font-mono">{m.profile_field || "-"}</span>
                        <span className="text-cyan-300 truncate">{m.value ?? "—"}</span>
                        <div className="flex items-center gap-1.5">
                          <div className="flex-1 h-1.5 rounded-full bg-white/[0.07] overflow-hidden">
                            <div className={`h-full rounded-full ${m.confidence >= 0.9 ? "bg-emerald-400" : m.confidence >= 0.7 ? "bg-amber-400" : "bg-rose-400"}`}
                              style={{ width: `${m.confidence * 100}%` }} />
                          </div>
                          <span className="text-[10px] text-slate-500">{(m.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  {(active.field_mapping.unmapped.length > 0 || active.field_mapping.needs_review.length > 0) && (
                    <div className="flex gap-4 mt-3 text-xs">
                      {active.field_mapping.unmapped.length > 0 && (
                        <span className="text-rose-300">未映射：{active.field_mapping.unmapped.join("、")}</span>
                      )}
                      {active.field_mapping.needs_review.length > 0 && (
                        <span className="text-amber-300">需复核：{active.field_mapping.needs_review.join("、")}</span>
                      )}
                    </div>
                  )}
                </div>
              )}
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
