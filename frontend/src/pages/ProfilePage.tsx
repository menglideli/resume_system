import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, Pencil, Plus, Save, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/PageHeader";
import { ScoreRing } from "@/components/ScoreRing";
import {
  addBlockEntry, createBlock, createFieldDef, deleteBlock, deleteBlockEntry, deleteFieldDef,
  getProfile, subEntityAdd, subEntityDelete, subEntityUpdate,
  updateBlock, updateBlockEntry, updateFieldDef, updateProfile,
} from "@/lib/db";
import type { BlockEntry, FieldDef, ProfileBlock, ProfileBlockField, ProfileFull, SubEntity } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";

type ResField = { name: string; label: string; type?: "text" | "date" | "number" | "textarea" | "list" };

const RESOURCES: Record<string, {
  label: string; listKey: string;
  fields: ResField[];
  title: (i: SubEntity) => string;
  sub: (i: SubEntity) => string;
}> = {
  educations: {
    label: "教育经历", listKey: "educations",
    fields: [
      { name: "school", label: "学校" }, { name: "major", label: "专业" },
      { name: "degree", label: "学历" }, { name: "gpa", label: "GPA" },
      { name: "start_date", label: "开始日期", type: "date" }, { name: "end_date", label: "结束日期", type: "date" },
      { name: "courses", label: "主修课程（每行一门）", type: "list" },
    ],
    title: (i) => `${i.school || ""} · ${i.major || ""}`,
    sub: (i) => [i.degree, i.start_date, i.end_date ? `~ ${i.end_date}` : ""].filter(Boolean).join(" "),
  },
  "work-experiences": {
    label: "工作经历", listKey: "work_experiences",
    fields: [
      { name: "company", label: "公司" }, { name: "position", label: "职位" },
      { name: "start_date", label: "开始日期", type: "date" }, { name: "end_date", label: "结束日期", type: "date" },
      { name: "description", label: "工作内容（每行一条 bullet）", type: "list" },
      { name: "achievements", label: "量化成果（每行一条）", type: "list" },
      { name: "priority", label: "优先级(0-10)", type: "number" },
    ],
    title: (i) => `${i.company || ""} · ${i.position || ""}`,
    sub: (i) => `${i.start_date || ""} ~ ${i.is_current ? "至今" : i.end_date || ""}`,
  },
  projects: {
    label: "项目经历", listKey: "projects",
    fields: [
      { name: "name", label: "项目名" }, { name: "role", label: "角色" },
      { name: "tech_stack", label: "技术栈（每行一个）", type: "list" },
      { name: "start_date", label: "开始日期", type: "date" }, { name: "end_date", label: "结束日期", type: "date" },
      { name: "highlights", label: "项目亮点（每行一条）", type: "list" },
      { name: "url", label: "链接" }, { name: "priority", label: "优先级(0-10)", type: "number" },
    ],
    title: (i) => `${i.name || ""} · ${i.role || ""}`,
    sub: (i) => (i.tech_stack || []).join(" / "),
  },
  skills: {
    label: "技能", listKey: "skills",
    fields: [
      { name: "name", label: "技能名" }, { name: "category", label: "分类" },
      { name: "proficiency", label: "熟练度(1-5)", type: "number" },
    ],
    title: (i) => `${i.name || ""}（${i.category || "通用"}）`,
    sub: (i) => "★".repeat(i.proficiency || 0),
  },
  certifications: {
    label: "证书", listKey: "certifications",
    fields: [
      { name: "name", label: "证书名" }, { name: "issuer", label: "颁发机构" },
      { name: "issue_date", label: "颁发日期", type: "date" }, { name: "credential_id", label: "证书编号" },
    ],
    title: (i) => i.name || "",
    sub: (i) => [i.issuer, i.issue_date].filter(Boolean).join(" · "),
  },
  "family-members": {
    label: "家庭成员", listKey: "family_members",
    fields: [
      { name: "name", label: "姓名" }, { name: "relationship", label: "关系" },
      { name: "work_unit", label: "工作单位" }, { name: "position", label: "职务" },
      { name: "phone", label: "电话" },
    ],
    title: (i) => `${i.name || ""}（${i.relationship || ""}）`,
    sub: (i) => [i.work_unit, i.position, i.phone].filter(Boolean).join(" · "),
  },
};

const BASIC_FIELDS: { name: string; label: string; type?: string }[] = [
  { name: "name", label: "姓名" }, { name: "gender", label: "性别" },
  { name: "birth_date", label: "出生日期", type: "date" }, { name: "phone", label: "电话" },
  { name: "email", label: "邮箱" }, { name: "location", label: "所在地" },
  { name: "political_status", label: "政治面貌" },
];

export default function ProfilePage() {
  const [profile, setProfile] = useState<ProfileFull | null>(null);
  const [basic, setBasic] = useState<Record<string, any>>({});
  const [saving, setSaving] = useState(false);
  const [dialog, setDialog] = useState<{ resource: string; item: SubEntity | null } | null>(null);
  const [form, setForm] = useState<Record<string, any>>({});
  // 自定义信息块（blockCreateOpen 同时承载新建/编辑）
  const [blockCreateOpen, setBlockCreateOpen] = useState(false);
  const [editingBlock, setEditingBlock] = useState<ProfileBlock | null>(null);
  const [newBlock, setNewBlock] = useState<{ name: string; fields: ProfileBlockField[] }>(
    { name: "", fields: [{ name: "", label: "", type: "text" }] }
  );
  const [entryDialog, setEntryDialog] = useState<{ block: ProfileBlock; entry: BlockEntry | null } | null>(null);
  const [entryForm, setEntryForm] = useState<Record<string, any>>({});
  // 版块自定义字段（fieldDialog.def 存在时为编辑模式）
  const [fieldDialog, setFieldDialog] = useState<{ section: string; def?: FieldDef } | null>(null);
  const [newField, setNewField] = useState<{ name: string; label: string; type: FieldDef["type"] }>(
    { name: "", label: "", type: "text" }
  );

  const reload = () => getProfile().then((p) => {
    setProfile(p);
    setBasic(Object.fromEntries(BASIC_FIELDS.map((f) => [f.name, (p as any)[f.name] ?? ""])) as any);
    setBasic((b) => ({ ...b, summary: p.summary ?? "", custom_fields: p.custom_fields ?? {} }));
  }).catch((e) => toast.error(e.message));

  useEffect(() => { reload(); }, []);

  const saveBasic = async () => {
    setSaving(true);
    try {
      await updateProfile({ ...basic, birth_date: basic.birth_date || null } as any);
      toast.success("基础信息已保存");
      reload();
    } catch (e: any) { toast.error(e.message); }
    setSaving(false);
  };

  const openDialog = (resource: string, item: SubEntity | null) => {
    const init: Record<string, any> = {};
    RESOURCES[resource].fields.forEach((f) => {
      const v = item ? item[f.name] : "";
      init[f.name] = Array.isArray(v) ? v.join("\n") : v ?? (f.type === "number" ? 0 : "");
    });
    defsOf(resource).forEach((d) => { init[d.name] = item?.custom_fields?.[d.name] ?? ""; });
    setForm(init);
    setDialog({ resource, item });
  };

  const saveDialog = async () => {
    if (!dialog) return;
    const data: Record<string, any> = {};
    RESOURCES[dialog.resource].fields.forEach((f) => {
      const v = form[f.name];
      if (f.type === "list") data[f.name] = String(v || "").split("\n").map((s) => s.trim()).filter(Boolean);
      else if (f.type === "number") data[f.name] = Number(v) || 0;
      else data[f.name] = v === "" ? null : v;
    });
    const custom: Record<string, any> = {};
    defsOf(dialog.resource).forEach((d) => {
      const v = form[d.name];
      custom[d.name] = d.type === "number" ? (v === "" || v == null ? null : Number(v)) : (v === "" ? null : v);
    });
    data.custom_fields = custom;
    try {
      if (dialog.item) await subEntityUpdate(dialog.resource, dialog.item.id, data);
      else await subEntityAdd(dialog.resource, data);
      toast.success("已保存");
      setDialog(null);
      reload();
    } catch (e: any) { toast.error(e.message); }
  };

  const removeItem = async (resource: string, id: string) => {
    try {
      await subEntityDelete(resource, id);
      toast.success("已删除");
      reload();
    } catch (e: any) { toast.error(e.message); }
  };

  const toggleVisibility = async (resource: string, item: SubEntity) => {
    try {
      await subEntityUpdate(resource, item.id, { visibility: !item.visibility });
      reload();
    } catch (e: any) { toast.error(e.message); }
  };

  // ---------------- 自定义信息块 ----------------
  const blocks = profile?.custom_blocks ?? [];

  const openCreateBlock = () => {
    setEditingBlock(null);
    setNewBlock({ name: "", fields: [{ name: "", label: "", type: "text" }] });
    setBlockCreateOpen(true);
  };

  const openEditBlock = (b: ProfileBlock) => {
    setEditingBlock(b);
    setNewBlock({ name: b.name, fields: b.fields.map((f) => ({ ...f })) });
    setBlockCreateOpen(true);
  };

  const doSaveBlock = async () => {
    const fields = newBlock.fields.filter((f) => f.name.trim());
    if (!newBlock.name.trim()) return toast.warning("请输入信息块名称");
    if (fields.length === 0) return toast.warning("至少定义一个字段");
    if (new Set(fields.map((f) => f.name)).size !== fields.length) return toast.warning("字段名不能重复");
    const normalized = fields.map((f) => ({ ...f, label: f.label || f.name }));
    try {
      if (editingBlock) {
        await updateBlock(editingBlock.id, { name: newBlock.name.trim(), fields: normalized });
        toast.success("信息块已更新（已删除字段的旧值仍保留在记录存储中）");
      } else {
        await createBlock(newBlock.name.trim(), normalized);
        toast.success("信息块已创建，现在可以添加记录");
      }
      setBlockCreateOpen(false);
      setEditingBlock(null);
      setNewBlock({ name: "", fields: [{ name: "", label: "", type: "text" }] });
      reload();
    } catch (e: any) { toast.error(e.message); }
  };

  const doDeleteBlock = async (b: ProfileBlock) => {
    if (!confirm(`确认删除信息块「${b.name}」？其下全部记录将一并删除。`)) return;
    try { await deleteBlock(b.id); toast.success("已删除"); reload(); }
    catch (e: any) { toast.error(e.message); }
  };

  const openEntryDialog = (block: ProfileBlock, entry: BlockEntry | null) => {
    const init: Record<string, any> = {};
    block.fields.forEach((f) => { init[f.name] = entry ? entry.data[f.name] ?? "" : ""; });
    setEntryForm(init);
    setEntryDialog({ block, entry });
  };

  const saveEntry = async () => {
    if (!entryDialog) return;
    try {
      if (entryDialog.entry) await updateBlockEntry(entryDialog.block.id, entryDialog.entry.id, entryForm);
      else await addBlockEntry(entryDialog.block.id, entryForm);
      toast.success("已保存");
      setEntryDialog(null);
      reload();
    } catch (e: any) { toast.error(e.message); }
  };

  const removeEntry = async (block: ProfileBlock, entry: BlockEntry) => {
    try { await deleteBlockEntry(block.id, entry.id); toast.success("已删除"); reload(); }
    catch (e: any) { toast.error(e.message); }
  };

  // ---------------- 版块自定义字段 ----------------
  const defsOf = (section: string) => (profile?.field_defs ?? []).filter((d) => d.section === section);

  const openFieldDialog = (section: string) => {
    setNewField({ name: "", label: "", type: "text" });
    setFieldDialog({ section });
  };

  const openEditField = (d: FieldDef) => {
    setNewField({ name: d.name, label: d.label, type: d.type });
    setFieldDialog({ section: d.section, def: d });
  };

  const doSaveField = async () => {
    if (!fieldDialog) return;
    const editing = fieldDialog.def;
    if (!newField.label.trim()) return toast.warning("请填写显示名");
    if (!editing && !newField.name.trim()) return toast.warning("请填写字段名");
    try {
      if (editing) {
        await updateFieldDef(editing.id, { label: newField.label.trim(), type: newField.type });
        toast.success("字段已更新");
      } else {
        await createFieldDef(fieldDialog.section, newField.name.trim(), newField.label.trim(), newField.type);
        toast.success("字段已添加，现在可以在记录中填写");
      }
      setFieldDialog(null);
      reload();
    } catch (e: any) { toast.error(e.message); }
  };

  const doDeleteField = async (d: FieldDef) => {
    if (!confirm(`确认删除字段「${d.label}」？已填写的值仍保留在存储中，但不再显示。`)) return;
    try { await deleteFieldDef(d.id); toast.success("已删除"); reload(); }
    catch (e: any) { toast.error(e.message); }
  };

  const renderFieldBadges = (section: string) => (
    <div className="flex flex-wrap items-center gap-1.5">
      {defsOf(section).map((d) => (
        <span key={d.id} className="chip bg-cyan-500/10 text-cyan-300 border-cyan-500/25 inline-flex items-center gap-1">
          {d.label}
          <button type="button" className="text-slate-500 hover:text-cyan-300" title="修改显示名/类型" onClick={() => openEditField(d)}>
            <Pencil className="w-3 h-3" />
          </button>
          <button type="button" className="text-slate-500 hover:text-rose-300" title="删除字段" onClick={() => doDeleteField(d)}>
            <X className="w-3 h-3" />
          </button>
        </span>
      ))}
    </div>
  );

  if (!profile) return <div className="flex justify-center py-32"><Loader2 className="w-8 h-8 animate-spin text-cyan-400" /></div>;

  return (
    <div>
      <PageHeader title="档案中心" desc="一份档案喂饱所有场景：简历生成、报名表填写、投递追踪" />

      <div className="grid xl:grid-cols-4 gap-4">
        {/* 左：档案卡片 */}
        <motion.div initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} className="glass p-6 flex flex-col items-center text-center h-fit">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-cyan-500/40 to-violet-500/40 flex items-center justify-center text-2xl font-bold text-white mb-3 shadow-[0_0_30px_-8px] shadow-cyan-500/50">
            {profile.name?.[0] || "简"}
          </div>
          <div className="font-bold text-lg">{profile.name || "未命名"}</div>
          <div className="text-xs text-slate-500 mb-4">{profile.location || "未填写所在地"} · {profile.phone || "未填写电话"}</div>
          <ScoreRing value={profile.completeness_score} size={110} label="档案完整度" />
          <div className="grid grid-cols-3 gap-2 w-full mt-5 text-center">
            {[
              ["工作", profile.work_experiences.length], ["项目", profile.projects.length],
              ["技能", profile.skills.length], ["教育", profile.educations.length],
              ["证书", profile.certifications.length], ["家庭", profile.family_members.length],
            ].map(([label, n]) => (
              <div key={label as string} className="rounded-xl bg-white/[0.04] py-2">
                <div className="font-bold text-cyan-300">{n}</div>
                <div className="text-[10px] text-slate-500">{label}</div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* 右：Tabs */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }} className="xl:col-span-3">
          <Tabs defaultValue="basic">
            <TabsList className="bg-white/[0.05] mb-4 flex-wrap h-auto">
              <TabsTrigger value="basic">基础信息</TabsTrigger>
              {Object.entries(RESOURCES).map(([k, r]) => (
                <TabsTrigger key={k} value={k}>{r.label}</TabsTrigger>
              ))}
              <TabsTrigger value="blocks">自定义信息块</TabsTrigger>
            </TabsList>

            <TabsContent value="basic">
              <div className="glass p-6">
                <div className="flex items-center justify-between mb-3">
                  {renderFieldBadges("basic")}
                  <Button size="sm" variant="ghost" className="text-cyan-300 h-7 shrink-0" onClick={() => openFieldDialog("basic")}>
                    <Plus className="w-4 h-4 mr-1" /> 添加字段
                  </Button>
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                  {BASIC_FIELDS.map((f) => (
                    <div key={f.name} className="space-y-1.5">
                      <Label className="text-slate-400">{f.label}</Label>
                      <Input type={f.type} className="bg-white/[0.05] border-white/10"
                        value={basic[f.name] || ""}
                        onChange={(e) => setBasic({ ...basic, [f.name]: e.target.value })} />
                    </div>
                  ))}
                  <div className="space-y-1.5 md:col-span-2">
                    <Label className="text-slate-400">自我评价</Label>
                    <Textarea rows={4} className="bg-white/[0.05] border-white/10"
                      value={basic.summary || ""}
                      onChange={(e) => setBasic({ ...basic, summary: e.target.value })} />
                  </div>
                  {defsOf("basic").map((d) => (
                    <div key={d.id} className="space-y-1.5">
                      <Label className="text-slate-400">{d.label} <span className="text-cyan-500/70">· 自定义</span></Label>
                      {d.type === "textarea" ? (
                        <Textarea rows={3} className="bg-white/[0.05] border-white/10"
                          value={basic.custom_fields?.[d.name] ?? ""}
                          onChange={(e) => setBasic({ ...basic, custom_fields: { ...(basic.custom_fields || {}), [d.name]: e.target.value } })} />
                      ) : (
                        <Input type={d.type} className="bg-white/[0.05] border-white/10"
                          value={basic.custom_fields?.[d.name] ?? ""}
                          onChange={(e) => setBasic({ ...basic, custom_fields: { ...(basic.custom_fields || {}), [d.name]: e.target.value } })} />
                      )}
                    </div>
                  ))}
                </div>
                <Button className="gradient-btn mt-5" onClick={saveBasic} disabled={saving}>
                  {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                  保存基础信息
                </Button>
              </div>
            </TabsContent>

            {Object.entries(RESOURCES).map(([key, res]) => (
              <TabsContent key={key} value={key}>
                <div className="glass p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-sm text-slate-300">{res.label}（{(profile[res.listKey as keyof ProfileFull] as SubEntity[])?.length || 0}）</h3>
                    <div className="flex items-center gap-1">
                      <Button size="sm" variant="ghost" className="text-cyan-300 h-8" onClick={() => openFieldDialog(key)}>
                        <Plus className="w-4 h-4 mr-1" /> 添加字段
                      </Button>
                      <Button size="sm" className="gradient-btn" onClick={() => openDialog(key, null)}>
                        <Plus className="w-4 h-4 mr-1" /> 添加
                      </Button>
                    </div>
                  </div>
                  {defsOf(key).length > 0 && <div className="mb-3">{renderFieldBadges(key)}</div>}
                  <div className="space-y-2.5">
                    {(profile[res.listKey as keyof ProfileFull] as SubEntity[]).length === 0 && (
                      <p className="text-xs text-slate-500 text-center py-8">暂无记录，点击右上角添加</p>
                    )}
                    {(profile[res.listKey as keyof ProfileFull] as SubEntity[]).map((item) => (
                      <div key={item.id} className="flex items-center gap-3 p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:border-cyan-500/30 transition-colors">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate flex items-center gap-2">
                            {res.title(item)}
                            {item.is_current && <span className="chip bg-emerald-500/15 text-emerald-300 border-emerald-500/30">至今</span>}
                          </div>
                          <div className="text-xs text-slate-500 truncate">{res.sub(item)}</div>
                        </div>
                        {"visibility" in item && (
                          <div className="flex items-center gap-1.5 text-[10px] text-slate-500 shrink-0">
                            进简历
                            <Switch checked={!!item.visibility} onCheckedChange={() => toggleVisibility(key, item)} />
                          </div>
                        )}
                        <Button size="icon" variant="ghost" className="h-8 w-8 text-slate-400 hover:text-cyan-300" onClick={() => openDialog(key, item)}>
                          <Pencil className="w-4 h-4" />
                        </Button>
                        <Button size="icon" variant="ghost" className="h-8 w-8 text-slate-400 hover:text-rose-300" onClick={() => removeItem(key, item.id)}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              </TabsContent>
            ))}

            {/* 自定义信息块：先建块（定义字段），再逐条添加记录 */}
            <TabsContent value="blocks">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-slate-500">
                    用于报名表等场景的额外信息（如“父母信息”）：先创建信息块并定义字段，再在块内逐条添加记录。
                  </p>
                  <Button size="sm" className="gradient-btn shrink-0 ml-4" onClick={openCreateBlock}>
                    <Plus className="w-4 h-4 mr-1" /> 新建信息块
                  </Button>
                </div>

                {blocks.length === 0 && (
                  <div className="glass p-10 text-center text-xs text-slate-500">
                    暂无自定义信息块，点击右上角“新建信息块”开始（例：块名“父母信息”，字段：姓名 / 关系 / 工作单位）
                  </div>
                )}

                {blocks.map((b) => (
                  <div key={b.id} className="glass p-5">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-semibold text-sm text-slate-200">{b.name} <span className="text-xs text-slate-500">（{b.entries.length} 条记录）</span></h3>
                      <div className="flex gap-1">
                        <Button size="sm" variant="ghost" className="text-slate-300 h-7" onClick={() => openEditBlock(b)}>
                          <Pencil className="w-4 h-4 mr-1" /> 编辑块
                        </Button>
                        <Button size="sm" variant="ghost" className="text-cyan-300 h-7" onClick={() => openEntryDialog(b, null)}>
                          <Plus className="w-4 h-4 mr-1" /> 添加记录
                        </Button>
                        <Button size="sm" variant="ghost" className="text-rose-300 h-7" onClick={() => doDeleteBlock(b)}>
                          <Trash2 className="w-4 h-4 mr-1" /> 删除块
                        </Button>
                      </div>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-xs text-slate-500 border-b border-white/[0.07]">
                            {b.fields.map((f) => <th key={f.name} className="py-2 pr-4 font-medium">{f.label || f.name}</th>)}
                            <th className="py-2 font-medium text-right">操作</th>
                          </tr>
                        </thead>
                        <tbody>
                          {b.entries.map((e) => (
                            <tr key={e.id} className="border-b border-white/[0.05] hover:bg-white/[0.03]">
                              {b.fields.map((f) => (
                                <td key={f.name} className="py-2.5 pr-4 text-slate-300">{e.data?.[f.name] ?? ""}</td>
                              ))}
                              <td className="py-2.5 text-right space-x-1">
                                <Button size="icon" variant="ghost" className="h-7 w-7 text-slate-400 hover:text-cyan-300" onClick={() => openEntryDialog(b, e)}>
                                  <Pencil className="w-3.5 h-3.5" />
                                </Button>
                                <Button size="icon" variant="ghost" className="h-7 w-7 text-slate-400 hover:text-rose-300" onClick={() => removeEntry(b, e)}>
                                  <Trash2 className="w-3.5 h-3.5" />
                                </Button>
                              </td>
                            </tr>
                          ))}
                          {b.entries.length === 0 && (
                            <tr><td colSpan={b.fields.length + 1} className="text-center text-slate-600 py-6 text-xs">暂无记录，点击“添加记录”</td></tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </motion.div>
      </div>

      {/* 编辑对话框 */}
      <Dialog open={!!dialog} onOpenChange={(o) => !o && setDialog(null)}>
        <DialogContent className="bg-[#0b1120] border-white/10 text-slate-100 max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{dialog?.item ? "编辑" : "添加"}{dialog && RESOURCES[dialog.resource].label}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3.5 py-2">
            {dialog && RESOURCES[dialog.resource].fields.map((f) => (
              <div key={f.name} className="space-y-1.5">
                <Label className="text-slate-400 text-xs">{f.label}</Label>
                {f.type === "list" || f.type === "textarea" ? (
                  <Textarea rows={3} className="bg-white/[0.05] border-white/10 text-sm"
                    value={form[f.name] || ""}
                    onChange={(e) => setForm({ ...form, [f.name]: e.target.value })} />
                ) : (
                  <Input type={f.type || "text"} className="bg-white/[0.05] border-white/10 text-sm"
                    value={form[f.name] ?? ""}
                    onChange={(e) => setForm({ ...form, [f.name]: e.target.value })} />
                )}
              </div>
            ))}
            {dialog && defsOf(dialog.resource).map((d) => (
              <div key={d.name} className="space-y-1.5">
                <Label className="text-slate-400 text-xs">{d.label} <span className="text-cyan-500/70">· 自定义</span></Label>
                {d.type === "textarea" ? (
                  <Textarea rows={3} className="bg-white/[0.05] border-white/10 text-sm"
                    value={form[d.name] ?? ""}
                    onChange={(e) => setForm({ ...form, [d.name]: e.target.value })} />
                ) : (
                  <Input type={d.type} className="bg-white/[0.05] border-white/10 text-sm"
                    value={form[d.name] ?? ""}
                    onChange={(e) => setForm({ ...form, [d.name]: e.target.value })} />
                )}
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDialog(null)}>取消</Button>
            <Button className="gradient-btn" onClick={saveDialog}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 新建信息块对话框：先块名 + 字段定义 */}
      <Dialog open={blockCreateOpen} onOpenChange={setBlockCreateOpen}>
        <DialogContent className="bg-[#0b1120] border-white/10 text-slate-100 max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingBlock ? "编辑信息块" : "新建信息块"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-xs">信息块名称（如：父母信息）</Label>
              <Input className="bg-white/[0.05] border-white/10 text-sm" placeholder="父母信息"
                value={newBlock.name}
                onChange={(e) => setNewBlock({ ...newBlock, name: e.target.value })} />
            </div>
            <div>
              <Label className="text-slate-400 text-xs">字段定义（每条记录包含的字段）</Label>
              <div className="space-y-2 mt-2">
                {newBlock.fields.map((f, i) => (
                  <div key={i} className="flex gap-2 items-center">
                    <Input className="bg-white/[0.05] border-white/10 text-sm flex-1" placeholder="字段名（如 name）"
                      value={f.name}
                      onChange={(e) => {
                        const fields = [...newBlock.fields];
                        fields[i] = { ...fields[i], name: e.target.value };
                        setNewBlock({ ...newBlock, fields });
                      }} />
                    <Input className="bg-white/[0.05] border-white/10 text-sm flex-1" placeholder="显示名（如 姓名，可空）"
                      value={f.label}
                      onChange={(e) => {
                        const fields = [...newBlock.fields];
                        fields[i] = { ...fields[i], label: e.target.value };
                        setNewBlock({ ...newBlock, fields });
                      }} />
                    <Select value={f.type} onValueChange={(v) => {
                      const fields = [...newBlock.fields];
                      fields[i] = { ...fields[i], type: v as ProfileBlockField["type"] };
                      setNewBlock({ ...newBlock, fields });
                    }}>
                      <SelectTrigger className="w-28 bg-white/[0.05] border-white/10 text-sm h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
                        <SelectItem value="text">文本</SelectItem>
                        <SelectItem value="number">数字</SelectItem>
                        <SelectItem value="date">日期</SelectItem>
                        <SelectItem value="textarea">多行</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button size="icon" variant="ghost" className="h-8 w-8 text-slate-500 hover:text-rose-300 shrink-0"
                      disabled={newBlock.fields.length <= 1}
                      onClick={() => setNewBlock({ ...newBlock, fields: newBlock.fields.filter((_, j) => j !== i) })}>
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
              <Button size="sm" variant="ghost" className="text-cyan-300 mt-2"
                onClick={() => setNewBlock({ ...newBlock, fields: [...newBlock.fields, { name: "", label: "", type: "text" }] })}>
                <Plus className="w-4 h-4 mr-1" /> 添加字段
              </Button>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setBlockCreateOpen(false)}>取消</Button>
            <Button className="gradient-btn" onClick={doSaveBlock}>{editingBlock ? "保存修改" : "创建信息块"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 信息块记录编辑对话框 */}
      <Dialog open={!!entryDialog} onOpenChange={(o) => !o && setEntryDialog(null)}>
        <DialogContent className="bg-[#0b1120] border-white/10 text-slate-100 max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{entryDialog?.entry ? "编辑" : "添加"}记录 · {entryDialog?.block.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3.5 py-2">
            {entryDialog?.block.fields.map((f) => (
              <div key={f.name} className="space-y-1.5">
                <Label className="text-slate-400 text-xs">{f.label || f.name}</Label>
                {f.type === "textarea" ? (
                  <Textarea rows={3} className="bg-white/[0.05] border-white/10 text-sm"
                    value={entryForm[f.name] ?? ""}
                    onChange={(e) => setEntryForm({ ...entryForm, [f.name]: e.target.value })} />
                ) : (
                  <Input type={f.type} className="bg-white/[0.05] border-white/10 text-sm"
                    value={entryForm[f.name] ?? ""}
                    onChange={(e) => setEntryForm({ ...entryForm, [f.name]: e.target.value })} />
                )}
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEntryDialog(null)}>取消</Button>
            <Button className="gradient-btn" onClick={saveEntry}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 添加自定义字段对话框 */}
      <Dialog open={!!fieldDialog} onOpenChange={(o) => !o && setFieldDialog(null)}>
        <DialogContent className="bg-[#0b1120] border-white/10 text-slate-100 max-w-md">
          <DialogHeader>
            <DialogTitle>{fieldDialog?.def ? "修改自定义字段" : "添加自定义字段"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3.5 py-2">
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-xs">字段名（英文 key，如 major_rank）</Label>
              <Input className="bg-white/[0.05] border-white/10 text-sm" placeholder="major_rank"
                value={newField.name}
                disabled={!!fieldDialog?.def}
                title={fieldDialog?.def ? "字段名是存储 key，不可修改" : undefined}
                onChange={(e) => setNewField({ ...newField, name: e.target.value })} />
              {fieldDialog?.def && <p className="text-[10px] text-slate-600">字段名是已存数据的 key，不可修改；可调整显示名与类型</p>}
            </div>
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-xs">显示名（如 专业排名）</Label>
              <Input className="bg-white/[0.05] border-white/10 text-sm" placeholder="专业排名"
                value={newField.label}
                onChange={(e) => setNewField({ ...newField, label: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-xs">字段类型</Label>
              <Select value={newField.type} onValueChange={(v) => setNewField({ ...newField, type: v as FieldDef["type"] })}>
                <SelectTrigger className="bg-white/[0.05] border-white/10 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
                  <SelectItem value="text">文本</SelectItem>
                  <SelectItem value="number">数字</SelectItem>
                  <SelectItem value="date">日期</SelectItem>
                  <SelectItem value="textarea">多行</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setFieldDialog(null)}>取消</Button>
            <Button className="gradient-btn" onClick={doSaveField}>{fieldDialog?.def ? "保存修改" : "添加字段"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
