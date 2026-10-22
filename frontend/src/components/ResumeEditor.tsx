/** 简历结构化编辑器：生成后的人工修改能力（不调 AI）。
 *
 * - 编辑 header / summary / 各类条目字段与 bullets
 * - 条目拖拽排序（@dnd-kit）、隐藏（hidden，导出时过滤）、relevance 调整
 * - 实时字数 / 预计页数 / JD 关键词覆盖（本地确定性计算，保存后以后端 stats 为准）
 * - 保存走 PUT /resumes/{id}/data：后端作废 PDF、追加版本快照
 */
import { useMemo, useState } from "react";
import {
  DndContext, PointerSensor, closestCenter, useSensor, useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext, arrayMove, useSortable, verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { EyeOff, Eye, GripVertical, Loader2, Plus, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import { updateResumeData } from "@/lib/db";
import { computeLocalStats } from "@/lib/stats";
import type { JDParsed, Resume } from "@/lib/types";

type DraftData = { header?: any; sections?: any[]; match_details?: any[] };

let keySeq = 0;
const nextKey = () => `it${Date.now().toString(36)}${(keySeq++).toString(36)}`;

/** 深拷贝并给每个 item 补稳定 _key（拖拽 id 用；保存前会剥掉） */
function cloneWithKeys(data: any): DraftData {
  const draft: DraftData = JSON.parse(JSON.stringify(data || {}));
  for (const sec of draft.sections || []) {
    for (const item of sec.items || []) {
      if (item && typeof item === "object" && !item._key) item._key = nextKey();
    }
  }
  return draft;
}

function stripKeys(draft: DraftData): DraftData {
  const out: DraftData = JSON.parse(JSON.stringify(draft));
  for (const sec of out.sections || []) {
    for (const item of sec.items || []) {
      if (item && typeof item === "object") delete item._key;
    }
  }
  return out;
}

/** 各类条目的可编辑字段定义 */
const ITEM_FIELDS: Record<string, { key: string; label: string; width?: string }[]> = {
  experience: [
    { key: "company", label: "公司", width: "flex-1" },
    { key: "position", label: "职位", width: "flex-1" },
    { key: "period", label: "时间", width: "w-40" },
  ],
  projects: [
    { key: "name", label: "项目名", width: "flex-1" },
    { key: "role", label: "角色", width: "w-40" },
    { key: "period", label: "时间", width: "w-40" },
  ],
  education: [
    { key: "school", label: "学校", width: "flex-1" },
    { key: "major", label: "专业", width: "flex-1" },
    { key: "degree", label: "学历", width: "w-24" },
    { key: "period", label: "时间", width: "w-40" },
  ],
  certifications: [
    { key: "name", label: "证书", width: "flex-1" },
    { key: "issuer", label: "颁发机构", width: "flex-1" },
    { key: "date", label: "日期", width: "w-32" },
  ],
  skills: [
    { key: "name", label: "技能", width: "w-40" },
    { key: "category", label: "分类", width: "w-32" },
    { key: "level", label: "熟练度", width: "w-24" },
  ],
};

const NEW_ITEM_TEMPLATE: Record<string, () => any> = {
  experience: () => ({ company: "", position: "", period: "", bullets: [], relevance: 6 }),
  projects: () => ({ name: "", role: "", period: "", tech_stack: [], bullets: [], relevance: 6 }),
  education: () => ({ school: "", major: "", degree: "", period: "" }),
  certifications: () => ({ name: "", issuer: "", date: "" }),
  skills: () => ({ name: "", category: "其他技能", level: "", relevance: 5 }),
};

function ItemCard({ sec, si, item, ii, update, onRemove }: {
  sec: any; si: number; item: any; ii: number;
  update: (mutator: (d: DraftData) => void) => void;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item._key });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1 };
  const fields = ITEM_FIELDS[sec.type] || [];
  const hasBullets = ["experience", "projects"].includes(sec.type);
  const setField = (key: string, value: any) =>
    update((d) => { d.sections![si].items[ii][key] = value; });

  return (
    <div ref={setNodeRef} style={style}
      className={`rounded-xl border p-3.5 space-y-2.5 ${item.hidden ? "border-white/[0.06] bg-white/[0.01] opacity-60" : "border-white/[0.08] bg-white/[0.03]"}`}>
      <div className="flex items-center gap-2">
        <button type="button" className="cursor-grab text-slate-600 hover:text-slate-400 shrink-0" {...attributes} {...listeners} title="拖动排序">
          <GripVertical className="w-4 h-4" />
        </button>
        {fields.map((f) => (
          <div key={f.key} className={`${f.width || "flex-1"} min-w-0`}>
            <Input className="bg-white/[0.04] border-white/10 h-8 text-sm" placeholder={f.label}
              value={String(item[f.key] ?? "")} onChange={(e) => setField(f.key, e.target.value)} />
          </div>
        ))}
        <div className="flex items-center gap-2 ml-auto shrink-0">
          <div className="flex items-center gap-1.5" title="相关性（影响导出时的取舍与排序）">
            <span className="text-[10px] text-slate-500">相关</span>
            <Slider className="w-20" min={0} max={10} step={1}
              value={[Number(item.relevance ?? 5)]}
              onValueChange={([v]) => setField("relevance", v)} />
            <span className="text-[10px] text-slate-400 w-4">{item.relevance ?? "-"}</span>
          </div>
          <button type="button" title={item.hidden ? "已隐藏（不会出现在导出 PDF 中）" : "隐藏此条目（不删除）"}
            className="text-slate-500 hover:text-amber-300"
            onClick={() => update((d) => { d.sections![si].items[ii].hidden = !item.hidden; })}>
            {item.hidden ? <EyeOff className="w-4 h-4 text-amber-300" /> : <Eye className="w-4 h-4" />}
          </button>
          <button type="button" className="text-slate-600 hover:text-rose-300" title="删除条目" onClick={onRemove}>
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {sec.type === "projects" && (
        <div className="pl-6">
          <Input className="bg-white/[0.04] border-white/10 h-8 text-xs" placeholder="技术栈（逗号分隔）"
            value={(item.tech_stack || []).join(", ")}
            onChange={(e) => setField("tech_stack", e.target.value.split(/[,，]/).map((s: string) => s.trim()).filter(Boolean))} />
        </div>
      )}

      {hasBullets && (
        <div className="pl-6 space-y-1.5">
          {(item.bullets || []).map((b: string, bi: number) => (
            <div key={bi} className="flex items-start gap-2">
              <span className="text-cyan-500 mt-2 text-xs">▪</span>
              <Textarea rows={Math.max(1, Math.ceil(String(b).length / 60))}
                className="bg-white/[0.04] border-white/10 text-xs min-h-8 py-1.5"
                value={b}
                onChange={(e) => update((d) => { d.sections![si].items[ii].bullets[bi] = e.target.value; })} />
              <button type="button" className="text-slate-600 hover:text-rose-300 mt-2" title="删除该条"
                onClick={() => update((d) => { d.sections![si].items[ii].bullets.splice(bi, 1); })}>
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          <Button size="sm" variant="ghost" className="h-6 text-xs text-slate-500 hover:text-cyan-300 px-1"
            onClick={() => update((d) => { (d.sections![si].items[ii].bullets ||= []).push(""); })}>
            <Plus className="w-3 h-3 mr-1" />添加一条
          </Button>
        </div>
      )}
      {item.hidden && <div className="pl-6 text-[10px] text-amber-300/80">已隐藏：不会出现在预览和导出 PDF 中，档案事实不受影响</div>}
    </div>
  );
}

export default function ResumeEditor({ resume, jdParsed, onSaved, onCancel }: {
  resume: Resume;
  jdParsed?: JDParsed | null;
  onSaved: (updated: Resume) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<DraftData>(() => cloneWithKeys(resume.resume_data));
  const [saving, setSaving] = useState(false);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const update = (mutator: (d: DraftData) => void) =>
    setDraft((prev) => { const n = JSON.parse(JSON.stringify(prev)); mutator(n); return n; });

  const stripped = useMemo(() => stripKeys(draft), [draft]);
  const dirty = useMemo(
    () => JSON.stringify(stripped) !== JSON.stringify(stripKeys(cloneWithKeys(resume.resume_data))),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [draft, resume.id],
  );
  const stats = useMemo(() => computeLocalStats(stripped, jdParsed), [stripped, jdParsed]);

  const onDragEnd = (si: number) => (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    update((d) => {
      const items = d.sections![si].items;
      const from = items.findIndex((x: any) => x._key === active.id);
      const to = items.findIndex((x: any) => x._key === over.id);
      d.sections![si].items = arrayMove(items, from, to);
    });
  };

  const doSave = async () => {
    setSaving(true);
    try {
      const updated = await updateResumeData(resume.id, stripped);
      toast.success("已保存编辑，PDF 需重新导出");
      onSaved(updated);
    } catch (e: any) { toast.error(e.message); }
    setSaving(false);
  };

  const header = draft.header || {};
  const setHeader = (key: string, value: string) =>
    update((d) => { (d.header ||= {})[key] = value; });
  const setContact = (key: string, value: string) =>
    update((d) => { ((d.header ||= {}).contact ||= {})[key] = value; });

  return (
    <div className="space-y-4">
      {/* 实时统计条 */}
      <div className="sticky top-0 z-10 rounded-xl border border-cyan-500/25 bg-[#0b1120]/95 backdrop-blur px-4 py-2.5 flex items-center gap-4 text-xs flex-wrap">
        <span className="text-slate-400">字数 <b className="text-slate-200">{stats.char_count}</b></span>
        <span className="text-slate-400">预计 <b className="text-slate-200">{stats.estimated_pages}</b> 页</span>
        <span className="text-slate-400">条目 <b className="text-slate-200">{stats.item_count}</b></span>
        {stats.keyword_coverage !== null && (
          <span className="text-slate-400">
            JD 关键词覆盖 <b className="text-cyan-300">{stats.keyword_coverage}%</b>
            （{stats.keyword_covered}/{stats.keyword_total}）
          </span>
        )}
        {!!stats.missing_keywords.length && (
          <span className="text-slate-500" title={stats.missing_keywords.join("、")}>
            未覆盖：{stats.missing_keywords.slice(0, 4).join("、")}{stats.missing_keywords.length > 4 ? "…" : ""}
          </span>
        )}
        <span className="text-[10px] text-slate-600 ml-auto">预计页数按 900 字/页估算，导出时以实际排版为准</span>
      </div>

      {/* 头部信息 */}
      <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-4 space-y-2.5">
        <Label className="text-xs text-slate-400">头部信息</Label>
        <div className="flex gap-2">
          <Input className="bg-white/[0.04] border-white/10 w-40" placeholder="姓名" value={header.name || ""} onChange={(e) => setHeader("name", e.target.value)} />
          <Input className="bg-white/[0.04] border-white/10 flex-1" placeholder="目标职位" value={header.title || ""} onChange={(e) => setHeader("title", e.target.value)} />
        </div>
        <div className="flex gap-2">
          <Input className="bg-white/[0.04] border-white/10 w-40" placeholder="电话" value={header.contact?.phone || ""} onChange={(e) => setContact("phone", e.target.value)} />
          <Input className="bg-white/[0.04] border-white/10 flex-1" placeholder="邮箱" value={header.contact?.email || ""} onChange={(e) => setContact("email", e.target.value)} />
          <Input className="bg-white/[0.04] border-white/10 w-40" placeholder="城市" value={header.contact?.location || ""} onChange={(e) => setContact("location", e.target.value)} />
        </div>
      </div>

      {/* 各内容模块 */}
      {(draft.sections || []).map((sec: any, si: number) => (
        <div key={si} className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-4 space-y-2.5">
          <div className="flex items-center gap-2">
            <span className="w-1 h-4 rounded bg-gradient-to-b from-cyan-400 to-violet-500" />
            <span className="font-semibold text-sm text-slate-200">{sec.title || sec.type}</span>
            {NEW_ITEM_TEMPLATE[sec.type] && (
              <Button size="sm" variant="ghost" className="h-6 text-xs text-slate-500 hover:text-cyan-300 ml-auto px-1.5"
                onClick={() => update((d) => {
                  const item = { ...NEW_ITEM_TEMPLATE[d.sections![si].type](), _key: nextKey() };
                  (d.sections![si].items ||= []).push(item);
                })}>
                <Plus className="w-3 h-3 mr-1" />添加条目
              </Button>
            )}
          </div>

          {sec.type === "summary" && (
            <Textarea rows={4} className="bg-white/[0.04] border-white/10 text-sm"
              value={sec.content || ""}
              onChange={(e) => update((d) => { d.sections![si].content = e.target.value; })} />
          )}

          {sec.type !== "summary" && (
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd(si)}>
              <SortableContext items={(sec.items || []).map((x: any) => x._key)} strategy={verticalListSortingStrategy}>
                <div className="space-y-2">
                  {(sec.items || []).map((item: any, ii: number) => (
                    <ItemCard key={item._key} sec={sec} si={si} item={item} ii={ii} update={update}
                      onRemove={() => update((d) => { d.sections![si].items.splice(ii, 1); })} />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          )}
        </div>
      ))}

      {/* 保存 / 取消 */}
      <div className="flex items-center gap-3 pt-1 pb-2">
        <Button className="gradient-btn" disabled={saving || !dirty} onClick={doSave}>
          {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
          {dirty ? "保存修改" : "未修改"}
        </Button>
        <Button variant="outline" className="border-white/10 text-slate-300 hover:bg-white/[0.06]"
          onClick={() => {
            if (dirty && !window.confirm("有未保存的修改，确定放弃吗？")) return;
            onCancel();
          }}>
          取消
        </Button>
        {dirty && <span className="text-xs text-amber-300">有未保存的修改 · 保存后会自动记录一个新版本，PDF 需重新导出</span>}
      </div>
    </div>
  );
}
