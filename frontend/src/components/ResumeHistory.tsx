/** 版本历史：时间线 + 两版本内容 diff + 回滚。
 *
 * 后端约定「当前内容永远是最新版本」，每次落地（AI 生成/手动编辑/经历优化/回滚）追加一条。
 * diff 全部在前端确定性计算：section 按 type 对齐、条目按 source_ref/名称对齐、bullet 集合对比、
 * 文字级改写用 diffWords 高亮。匹配分变化还会给出 JD 关键词覆盖的增减，回答「分数从哪里来」。
 */
import { useEffect, useMemo, useState } from "react";
import { diffWords } from "diff";
import { GitCompareArrows, History, Loader2, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { getResumeVersion, listResumeVersions, rollbackResumeVersion } from "@/lib/db";
import { computeLocalStats, visibleText } from "@/lib/stats";
import { VERSION_LABEL_META, type JDParsed, type Resume, type ResumeVersionDetail, type ResumeVersionMeta } from "@/lib/types";

const labelMeta = (label: string) =>
  VERSION_LABEL_META[label] || { label, cls: "bg-slate-500/15 text-slate-300 border-slate-500/30" };

const fmtTime = (iso: string) => new Date(iso).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });

/** 条目的对齐键：优先 source_ref，其次身份字段 */
function itemKey(it: any): string {
  return String(it?.source_ref || it?.company || it?.name || it?.school || it?.position || JSON.stringify(it).slice(0, 40));
}

function itemTitle(it: any): string {
  return [it.company || it.name || it.school, it.position || it.role || it.major].filter(Boolean).join(" · ") || "（未命名条目）";
}

/** 文字级 diff：删除红色删除线、新增绿色 */
function WordDiff({ before, after }: { before: string; after: string }) {
  if (before === after) return <span className="text-slate-300">{after}</span>;
  return (
    <span>
      {diffWords(before, after).map((part, i) =>
        part.added ? <span key={i} className="text-emerald-300 bg-emerald-500/10 rounded px-0.5">{part.value}</span>
        : part.removed ? <span key={i} className="text-rose-300/80 line-through decoration-rose-500/50">{part.value}</span>
        : <span key={i} className="text-slate-400">{part.value}</span>)}
    </span>
  );
}

function DeltaChip({ label, before, after, suffix = "" }: { label: string; before: number | null; after: number | null; suffix?: string }) {
  const delta = before != null && after != null ? after - before : null;
  return (
    <span className="chip bg-white/[0.04] border-white/10 text-slate-300">
      {label}：{before ?? "-"}{suffix} → <b className="text-slate-100">{after ?? "-"}{suffix}</b>
      {delta !== null && delta !== 0 && (
        <b className={delta > 0 ? "text-emerald-300 ml-1" : "text-rose-300 ml-1"}>
          {delta > 0 ? `+${delta}` : delta}{suffix}
        </b>
      )}
    </span>
  );
}

function ItemDiff({ before, after }: { before?: any; after?: any }) {
  const it = after || before;
  const added = !before;
  const removed = !after;
  const bulletsBefore: string[] = before?.bullets || [];
  const bulletsAfter: string[] = after?.bullets || [];
  const norm = (s: string) => s.replace(/\s/g, "").toLowerCase();
  const addedBullets = bulletsAfter.filter((b) => !bulletsBefore.some((x) => norm(x) === norm(b)));
  const removedBullets = bulletsBefore.filter((b) => !bulletsAfter.some((x) => norm(x) === norm(b)));
  const fieldChanges = ["position", "role", "period", "date", "degree", "major"].filter(
    (k) => before && after && String(before[k] ?? "") !== String(after[k] ?? ""));

  if (!added && !removed && !addedBullets.length && !removedBullets.length && !fieldChanges.length
    && (before?.hidden ?? false) === (after?.hidden ?? false)
    && (before?.relevance ?? null) === (after?.relevance ?? null)) return null;

  return (
    <div className={`rounded-lg border px-3 py-2 text-xs space-y-1 ${
      added ? "border-emerald-500/30 bg-emerald-500/[0.05]"
      : removed ? "border-rose-500/30 bg-rose-500/[0.05]"
      : "border-white/[0.08] bg-white/[0.02]"}`}>
      <div className="flex items-center gap-2">
        <span className={`font-medium ${removed ? "text-rose-300 line-through" : "text-slate-200"}`}>{itemTitle(it)}</span>
        {added && <span className="chip bg-emerald-500/15 text-emerald-300 border-emerald-500/30 text-[10px]">新增条目</span>}
        {removed && <span className="chip bg-rose-500/15 text-rose-300 border-rose-500/30 text-[10px]">删除条目</span>}
        {!added && !removed && after?.hidden !== before?.hidden && (
          <span className="chip bg-amber-500/15 text-amber-300 border-amber-500/30 text-[10px]">{after?.hidden ? "被隐藏" : "恢复显示"}</span>
        )}
        {!added && !removed && before?.relevance !== after?.relevance && (
          <span className="text-[10px] text-slate-500">相关性 {before?.relevance ?? "-"} → {after?.relevance ?? "-"}</span>
        )}
      </div>
      {fieldChanges.map((k) => (
        <div key={k} className="text-slate-400"><WordDiff before={String(before?.[k] ?? "")} after={String(after?.[k] ?? "")} /></div>
      ))}
      {removedBullets.map((b, i) => <div key={`r${i}`} className="text-rose-300/80 line-through decoration-rose-500/40">− {b}</div>)}
      {addedBullets.map((b, i) => <div key={`a${i}`} className="text-emerald-300">+ {b}</div>)}
    </div>
  );
}

function DiffView({ a, b, jdParsed }: { a: any; b: any; jdParsed?: JDParsed | null }) {
  const statsA = useMemo(() => computeLocalStats(a, jdParsed), [a, jdParsed]);
  const statsB = useMemo(() => computeLocalStats(b, jdParsed), [b, jdParsed]);
  const gainedKw = statsB.covered_keywords.filter((k) => !statsA.covered_keywords.includes(k));
  const lostKw = statsA.covered_keywords.filter((k) => !statsB.covered_keywords.includes(k));

  const sectionsA: any[] = a?.sections || [];
  const sectionsB: any[] = b?.sections || [];
  const types = Array.from(new Set([...sectionsA, ...sectionsB].map((s) => s.type)));

  const summaryA = sectionsA.find((s) => s.type === "summary")?.content || "";
  const summaryB = sectionsB.find((s) => s.type === "summary")?.content || "";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5">
        <DeltaChip label="字数" before={statsA.char_count} after={statsB.char_count} />
        <DeltaChip label="预计页数" before={statsA.estimated_pages} after={statsB.estimated_pages} suffix=" 页" />
        {statsA.keyword_coverage !== null && statsB.keyword_coverage !== null && (
          <DeltaChip label="JD 关键词覆盖" before={statsA.keyword_coverage} after={statsB.keyword_coverage} suffix="%" />
        )}
      </div>
      {(gainedKw.length > 0 || lostKw.length > 0) && (
        <div className="text-xs space-y-1">
          {gainedKw.length > 0 && <div className="text-emerald-300">新覆盖关键词：{gainedKw.join("、")}</div>}
          {lostKw.length > 0 && <div className="text-rose-300">丢失关键词：{lostKw.join("、")}</div>}
        </div>
      )}

      {["name", "title"].some((k) => String(a?.header?.[k] ?? "") !== String(b?.header?.[k] ?? "")) && (
        <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-3.5 space-y-1.5">
          <div className="text-xs font-semibold text-slate-300">头部信息</div>
          {["name", "title"].filter((k) => String(a?.header?.[k] ?? "") !== String(b?.header?.[k] ?? "")).map((k) => (
            <div key={k} className="text-xs">
              <span className="text-slate-500 mr-1.5">{k === "name" ? "姓名" : "职位"}：</span>
              <WordDiff before={String(a?.header?.[k] ?? "")} after={String(b?.header?.[k] ?? "")} />
            </div>
          ))}
        </div>
      )}

      {summaryA !== summaryB && (
        <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-3.5 space-y-1.5">
          <div className="text-xs font-semibold text-slate-300">个人总结</div>
          <div className="text-xs leading-relaxed"><WordDiff before={summaryA} after={summaryB} /></div>
        </div>
      )}

      {types.filter((t) => t !== "summary").map((type) => {
        const secA = sectionsA.find((s) => s.type === type);
        const secB = sectionsB.find((s) => s.type === type);
        const itemsA: any[] = secA?.items || [];
        const itemsB: any[] = secB?.items || [];
        const keys = Array.from(new Set([...itemsA.map(itemKey), ...itemsB.map(itemKey)]));
        const rows = keys.map((k) => ({
          key: k,
          before: itemsA.find((x) => itemKey(x) === k),
          after: itemsB.find((x) => itemKey(x) === k),
        })).filter((r) => r.before || r.after);
        // 顺序变化提示
        const orderA = itemsA.map(itemKey).filter((k) => keys.includes(k));
        const orderB = itemsB.map(itemKey).filter((k) => keys.includes(k));
        const common = orderA.filter((k) => orderB.includes(k));
        const reordered = common.length > 1 && JSON.stringify(common) !== JSON.stringify(common.map((k) => orderB[orderA.indexOf(k)]).filter(Boolean));
        const changed = rows.filter((r) => {
          if (!r.before || !r.after) return true;
          return JSON.stringify(r.before) !== JSON.stringify(r.after);
        });
        if (!changed.length && !reordered) return null;
        return (
          <div key={type} className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-3.5 space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-300">{secB?.title || secA?.title || type}</span>
              {reordered && <span className="chip bg-violet-500/15 text-violet-300 border-violet-500/30 text-[10px]">顺序有调整</span>}
            </div>
            {changed.map((r) => <ItemDiff key={r.key} before={r.before} after={r.after} />)}
          </div>
        );
      })}

      {visibleText(a) === visibleText(b) && (
        <div className="text-xs text-slate-500 text-center py-2">两个版本的可见内容完全一致</div>
      )}
    </div>
  );
}

export default function ResumeHistory({ resume, jdParsed, onRolledBack }: {
  resume: Resume;
  jdParsed?: JDParsed | null;
  onRolledBack: (updated: Resume) => void;
}) {
  const [versions, setVersions] = useState<ResumeVersionMeta[]>([]);
  // loading 用「已完成加载的简历 id」派生，避免在 effect 里同步 setState
  const [loadedFor, setLoadedFor] = useState<string>("");
  const [aId, setAId] = useState<string>("");
  const [bId, setBId] = useState<string>("current");
  const [details, setDetails] = useState<Record<string, ResumeVersionDetail>>({});
  const [showDiff, setShowDiff] = useState(false);
  const [diffLoading, setDiffLoading] = useState(false);
  const [rollbackTarget, setRollbackTarget] = useState<ResumeVersionMeta | null>(null);
  const [rolling, setRolling] = useState(false);
  const loading = loadedFor !== resume.id;

  useEffect(() => {
    let cancelled = false;
    listResumeVersions(resume.id)
      .then((list) => {
        if (cancelled) return;
        setVersions(list);
        setAId(list.length >= 2 ? list[1].id : list[0]?.id || "");
        setBId("current");
        setShowDiff(false);
      })
      .catch(() => { if (!cancelled) setVersions([]); })
      .finally(() => { if (!cancelled) setLoadedFor(resume.id); });
    return () => { cancelled = true; };
  }, [resume.id]);

  const loadDetail = async (id: string): Promise<ResumeVersionDetail | null> => {
    if (details[id]) return details[id];
    const detail = await getResumeVersion(resume.id, id);
    setDetails((prev) => ({ ...prev, [id]: detail }));
    return detail;
  };

  const doCompare = async () => {
    if (!aId) return toast.warning("请选择要对比的旧版本");
    setDiffLoading(true);
    try {
      await loadDetail(aId);
      if (bId !== "current") await loadDetail(bId);
      setShowDiff(true);
    } catch (e: any) { toast.error(e.message); }
    setDiffLoading(false);
  };

  const doRollback = async () => {
    if (!rollbackTarget) return;
    setRolling(true);
    try {
      const updated = await rollbackResumeVersion(resume.id, rollbackTarget.id);
      toast.success(`已回滚到版本 v${rollbackTarget.version_no}，PDF 需重新导出`);
      setRollbackTarget(null);
      const list = await listResumeVersions(resume.id);
      setVersions(list);
      setShowDiff(false);
      onRolledBack(updated);
    } catch (e: any) { toast.error(e.message); }
    setRolling(false);
  };

  if (loading) return <div className="p-14 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-slate-500" /></div>;

  if (versions.length === 0) return (
    <div className="rounded-xl border border-dashed border-white/10 p-14 flex flex-col items-center text-slate-600">
      <History className="w-10 h-10 mb-3 opacity-40" />
      <p className="text-sm mb-1">这份简历还没有版本历史</p>
      <p className="text-xs">在版本功能上线前生成的简历没有留档；下一次编辑、经历优化或重新生成后，这里会出现完整时间线</p>
    </div>
  );

  const optionLabel = (v: ResumeVersionMeta) => `v${v.version_no} · ${labelMeta(v.label).label} · ${fmtTime(v.created_at)}`;
  const dataA = aId ? details[aId]?.resume_data : null;
  const dataB = bId === "current" ? resume.resume_data : details[bId]?.resume_data;

  return (
    <div className="space-y-4">
      {/* 对比选择 */}
      <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-3.5 flex items-center gap-2 flex-wrap">
        <GitCompareArrows className="w-4 h-4 text-cyan-300 shrink-0" />
        <Select value={aId} onValueChange={setAId}>
          <SelectTrigger className="w-56 h-8 bg-white/[0.04] border-white/10 text-xs"><SelectValue placeholder="旧版本（A）" /></SelectTrigger>
          <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
            {versions.map((v) => <SelectItem key={v.id} value={v.id}>{optionLabel(v)}</SelectItem>)}
          </SelectContent>
        </Select>
        <span className="text-slate-600 text-xs">→</span>
        <Select value={bId} onValueChange={setBId}>
          <SelectTrigger className="w-56 h-8 bg-white/[0.04] border-white/10 text-xs"><SelectValue placeholder="新版本（B）" /></SelectTrigger>
          <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
            <SelectItem value="current">当前内容（最新）</SelectItem>
            {versions.map((v) => <SelectItem key={v.id} value={v.id}>{optionLabel(v)}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button size="sm" variant="outline" className="border-white/10 text-slate-300 hover:bg-white/[0.06] h-8" disabled={diffLoading || !aId} onClick={doCompare}>
          {diffLoading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : null}对比
        </Button>
      </div>

      {showDiff && dataA && dataB && (
        <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/[0.03] p-4 space-y-3">
          <div className="text-sm font-semibold text-cyan-300">
            内容差异：{aId ? optionLabel(versions.find((v) => v.id === aId)!) : "A"} → {bId === "current" ? "当前内容" : optionLabel(versions.find((v) => v.id === bId)!)}
          </div>
          <DiffView a={dataA} b={dataB} jdParsed={jdParsed} />
        </div>
      )}

      {/* 时间线 */}
      <div className="space-y-2">
        {versions.map((v) => (
          <div key={v.id} className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3 flex items-center gap-3">
            <span className="text-xs text-slate-600 w-8 shrink-0">v{v.version_no}</span>
            <span className={`chip shrink-0 ${labelMeta(v.label).cls}`}>{labelMeta(v.label).label}</span>
            <span className="text-xs text-slate-500">{fmtTime(v.created_at)}</span>
            {v.match_score != null && <span className="text-xs text-slate-400">匹配 {v.match_score}</span>}
            <Button size="sm" variant="ghost" className="ml-auto h-7 text-xs text-slate-400 hover:text-cyan-300 shrink-0"
              onClick={() => setRollbackTarget(v)}>
              <RotateCcw className="w-3 h-3 mr-1" />回滚到此版本
            </Button>
          </div>
        ))}
      </div>

      <AlertDialog open={!!rollbackTarget} onOpenChange={(o) => !o && !rolling && setRollbackTarget(null)}>
        <AlertDialogContent className="bg-[#0b1120] border-white/10 text-slate-100">
          <AlertDialogHeader>
            <AlertDialogTitle>回滚到 v{rollbackTarget?.version_no}（{rollbackTarget ? labelMeta(rollbackTarget.label).label : ""}）？</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-400">
              当前内容会被该版本覆盖（当前内容本身已在时间线中留档，不会丢失）。回滚会记录为新版本，已导出的 PDF 作废，需要重新导出。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-white/10 text-slate-300 hover:bg-white/5">取消</AlertDialogCancel>
            <AlertDialogAction className="gradient-btn" disabled={rolling}
              onClick={(e) => { e.preventDefault(); void doRollback(); }}>
              {rolling && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}确认回滚
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
