/** 统一数据访问层：按运行模式（真实后端 / 演示模式）路由 */
import { api, apiBlobUrl, apiDownload, isDemo, notifyLogin, setAdmin } from "./api";
import * as M from "./mock";
import type {
  AdminUser, Application, ApplicationSnapshot, AppStats, BlockEntry, FieldDef, FormMappingResult, FormRecord,
  InterviewPrep, JD, KimiConfig, Photo, ProfileBlock, ProfileBlockField, ProfileFull, Resume,
  ResumeStats, ResumeTemplate, ResumeVersionDetail, ResumeVersionMeta, SubEntity,
} from "./types";

// ---------------- 认证 ----------------
export async function login(username: string, password: string) {
  if (isDemo()) {
    await M.sleep(500);
    setAdmin(true); // 演示模式下默认给管理员权限，便于体验后台管理
    notifyLogin();
    return { access_token: "demo-token-" + Date.now(), token_type: "bearer", is_admin: true };
  }
  const res = await api<{ access_token: string; is_admin?: boolean }>("/auth/login", {
    method: "POST", body: JSON.stringify({ username, password }),
  });
  setAdmin(!!res.is_admin);
  notifyLogin();
  return res;
}

export async function register(username: string, email: string, password: string) {
  if (isDemo()) { await M.sleep(500); return { id: "demo" }; }
  return api("/auth/register", { method: "POST", body: JSON.stringify({ username, email, password }) });
}

// ---------------- 档案 ----------------
export async function getProfile(): Promise<ProfileFull> {
  if (isDemo()) { await M.sleep(300); return M.mockProfile; }
  return api<ProfileFull>("/profile");
}

export async function updateProfile(data: Partial<ProfileFull>) {
  if (isDemo()) { Object.assign(M.mockProfile, data); await M.sleep(300); return M.mockProfile; }
  return api("/profile", { method: "PUT", body: JSON.stringify(data) });
}

export async function subEntityAdd(resource: string, data: any): Promise<SubEntity> {
  if (isDemo()) {
    await M.sleep(250);
    return M.subAdd((M.mockProfile as any)[resource], data);
  }
  return api(`/profile/${resource}`, { method: "POST", body: JSON.stringify(data) });
}

export async function subEntityUpdate(resource: string, id: string, data: any) {
  if (isDemo()) { await M.sleep(250); return M.subUpdate((M.mockProfile as any)[resource], id, data); }
  return api(`/profile/${resource}/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function subEntityDelete(resource: string, id: string) {
  if (isDemo()) { await M.sleep(250); M.subDelete((M.mockProfile as any)[resource], id); return; }
  return api(`/profile/${resource}/${id}`, { method: "DELETE" });
}

// ---------------- JD ----------------
export async function listJDs(): Promise<JD[]> {
  if (isDemo()) { await M.sleep(250); return M.mockJDs; }
  return api<JD[]>("/jd/list");
}

export async function parseJD(raw_text: string, company_name?: string, position_title?: string): Promise<{ id: string; parsed_data: any; match_preview: any }> {
  if (isDemo()) {
    await M.sleep(1400); // 模拟 AI 解析耗时
    const jd: JD = {
      id: M.uid(), company_name: company_name || "示例科技", position_title: position_title || "后端开发工程师",
      raw_text, created_at: new Date().toISOString(),
      parsed_data: {
        company: company_name || "示例科技", position: position_title || "后端开发工程师",
        hard_requirements: ["3 年以上后端经验", "精通 Go / Java", "熟悉 MySQL 与缓存"],
        soft_requirements: ["沟通顺畅", "自驱力强"],
        core_responsibilities: ["核心业务后端开发", "参与架构设计与性能优化"],
        bonus_items: ["有开源贡献", "熟悉云原生"],
        keywords: ["Go", "Redis", "MySQL", "微服务"],
        ats_keywords: ["backend", "microservices"],
        education_requirement: "本科及以上", experience_years: "3-5 年", salary_range: null,
      },
    };
    M.mockJDs.unshift(jd);
    return { id: jd.id, parsed_data: jd.parsed_data, match_preview: { profile_completeness: 86, estimated_match: 74 } };
  }
  return api("/jd/parse", { method: "POST", body: JSON.stringify({ raw_text, company_name, position_title }) });
}

// ---------------- 简历 ----------------
export async function listResumes(): Promise<Resume[]> {
  if (isDemo()) { await M.sleep(250); return M.mockResumes; }
  return api<Resume[]>("/resumes");
}

export async function generateResume(jd_id: string, preferences: any): Promise<Resume> {
  if (isDemo()) {
    await M.sleep(1800);
    const jd = M.mockJDs.find((j) => j.id === jd_id);
    const r: Resume = JSON.parse(JSON.stringify(M.mockResumes[0]));
    r.id = M.uid(); r.jd_id = jd_id;
    r.version_name = `${jd?.company_name || "目标公司"}_${jd?.position_title || "定制岗位"}_20260717`;
    r.match_score = 78; r.status = "generated"; r.created_at = new Date().toISOString();
    M.mockResumes.unshift(r);
    return r;
  }
  return api("/resumes/generate", { method: "POST", body: JSON.stringify({ jd_id, preferences }) });
}

export interface Me {
  id: string; username: string; email: string; is_admin: boolean;
}

// 模块级缓存：App 启动时用它校验令牌，AppLayout 用它渲染昵称头像，只发一次请求
let meCache: Me | null = null;

// 启动校验走的是首屏关键路径：接口挂起会把用户永久卡在 splash，所以单独给一个短超时，
// 而不是用 api() 默认的 30 秒。
const ME_TIMEOUT_MS = 8_000;

/** 取当前登录用户。force=true 时忽略缓存（用于启动时校验令牌是否仍有效）。 */
export async function getMe(force = false): Promise<Me | null> {
  // 演示模式没有后端可问，别发一个注定失败的请求
  if (isDemo()) return null;
  if (meCache && !force) return meCache;
  try {
    meCache = await api<Me>("/auth/me", {}, ME_TIMEOUT_MS);
  } catch {
    meCache = null;
  }
  return meCache;
}

export function cachedMe(): Me | null {
  return meCache;
}

export function clearMe() {
  meCache = null;
}

/** 重试失败/中断的生成任务：复用原记录，不新增一条简历 */
export async function retryResume(resumeId: string): Promise<Resume> {
  if (isDemo()) {
    await M.sleep(900);
    const r = M.mockResumes.find((x) => x.id === resumeId);
    if (r) { r.status = "generated"; r.error_message = undefined; }
    return r as Resume;
  }
  return api<Resume>(`/resumes/${resumeId}/retry`, { method: "POST" });
}

/** 将用户确认的建议 bullet 融入指定的已有工作经历。write_back_profile=同时补充到档案中心。 */
export async function applyEnhancements(
  resumeId: string,
  placements: { index: number; target_source_ref: string; write_back_profile?: boolean }[],
): Promise<{ applied: number; added_bullets: number; written_back_to_profile?: number; remaining: number }> {
  return api(`/resumes/${resumeId}/enhancements/apply`, {
    method: "POST",
    body: JSON.stringify({ placements, confirmed: true }),
  });
}

// ---------------- 简历编辑器 ----------------
/** 保存编辑后的简历内容（不调 AI）。后端会作废旧 PDF 并追加一条版本快照。 */
export async function updateResumeData(resumeId: string, resume_data: any): Promise<Resume> {
  if (isDemo()) {
    await M.sleep(400);
    const r = M.mockResumes.find((x) => x.id === resumeId);
    if (!r) throw new Error("简历不存在");
    r.resume_data = resume_data;
    r.status = "generated";
    M.pushMockVersion(resumeId, "user_edit", resume_data, r.match_score);
    return r;
  }
  return api<Resume>(`/resumes/${resumeId}/data`, { method: "PUT", body: JSON.stringify({ resume_data }) });
}

/** 字数 / 预计页数 / JD 关键词覆盖（确定性统计，编辑保存后刷新） */
export async function getResumeStats(resumeId: string): Promise<ResumeStats> {
  if (isDemo()) {
    await M.sleep(150);
    const r = M.mockResumes.find((x) => x.id === resumeId);
    if (!r) throw new Error("简历不存在");
    return M.computeMockStats(r);
  }
  return api<ResumeStats>(`/resumes/${resumeId}/stats`);
}

// ---------------- 版本历史 ----------------
export async function listResumeVersions(resumeId: string): Promise<ResumeVersionMeta[]> {
  if (isDemo()) {
    await M.sleep(200);
    return [...(M.mockResumeVersions[resumeId] || [])].reverse();
  }
  return api<ResumeVersionMeta[]>(`/resumes/${resumeId}/versions`);
}

export async function getResumeVersion(resumeId: string, versionId: string): Promise<ResumeVersionDetail> {
  if (isDemo()) {
    await M.sleep(150);
    const v = (M.mockResumeVersions[resumeId] || []).find((x) => x.id === versionId);
    if (!v) throw new Error("版本不存在");
    return v;
  }
  return api<ResumeVersionDetail>(`/resumes/${resumeId}/versions/${versionId}`);
}

export async function rollbackResumeVersion(resumeId: string, versionId: string): Promise<Resume> {
  if (isDemo()) {
    await M.sleep(400);
    const r = M.mockResumes.find((x) => x.id === resumeId);
    const v = (M.mockResumeVersions[resumeId] || []).find((x) => x.id === versionId);
    if (!r || !v) throw new Error("简历或版本不存在");
    r.resume_data = JSON.parse(JSON.stringify(v.resume_data));
    r.match_score = v.match_score;
    r.status = "generated";
    M.pushMockVersion(resumeId, "rollback", r.resume_data, r.match_score);
    return r;
  }
  return api<Resume>(`/resumes/${resumeId}/versions/${versionId}/rollback`, { method: "POST" });
}

/** 删除简历记录（失败任务、不想要的版本都走这里）。后端会连带删除其面试准备。 */
export async function deleteResume(resumeId: string): Promise<void> {
  if (isDemo()) {
    await M.sleep(400);
    const i = M.mockResumes.findIndex((x) => x.id === resumeId);
    if (i >= 0) M.mockResumes.splice(i, 1);
    return;
  }
  await api(`/resumes/${resumeId}`, { method: "DELETE" });
}

export async function exportResume(resume: Resume, template?: ResumeTemplate) {
  if (isDemo()) {
    await M.sleep(600);
    const blob = new Blob([renderResumeHTML(resume)], { type: "text/html;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${resume.version_name}.html`;
    a.click();
    URL.revokeObjectURL(a.href);
    return;
  }
  // 后端是 POST /resumes/{id}/export，不是 GET。走 GET 会 405 Method Not Allowed。
  // template 不传：后端会回退到简历自身的 html_template，无需前端猜测。
  await apiDownload(`/resumes/${resume.id}/export`, `${resume.version_name}.pdf`, {
    method: "POST",
    body: JSON.stringify({ format: "pdf", template }),
  });
}

/** 演示模式下的前端简易 HTML 渲染（真实模式由后端 Playwright 出 PDF） */
function renderResumeHTML(r: Resume): string {
  const h = r.resume_data?.header || {};
  const secs = (r.resume_data?.sections || []).map((s) => {
    let inner = `<h2 style="color:#1a56db;border-left:4px solid #1a56db;padding-left:8px;">${s.title}</h2>`;
    if (s.type === "summary") inner += `<p>${s.content || ""}</p>`;
    else if (s.type === "skills") inner += (s.items || []).map((i: any) => `<span style="display:inline-block;background:#eff4ff;color:#1a56db;border-radius:4px;padding:2px 10px;margin:2px 6px 2px 0;">${i.name} · ${i.level}</span>`).join("");
    else inner += (s.items || []).map((i: any) => `<div style="margin-bottom:10px;"><b>${i.company || i.name || i.school || ""} ${i.position || i.role || i.degree || ""}</b> <span style="color:#888;float:right;">${i.period || i.date || ""}</span><ul>${(i.bullets || []).map((b: string) => `<li>${b}</li>`).join("")}</ul></div>`).join("");
    return `<div style="margin-bottom:16px;">${inner}</div>`;
  }).join("");
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${r.version_name}</title></head>
  <body style="font-family:'Noto Sans SC','Microsoft YaHei',sans-serif;max-width:760px;margin:32px auto;color:#2b2b2b;">
  <h1 style="color:#1a56db;">${h.name || ""}</h1><p style="color:#555;">${h.title || ""} · ${Object.values(h.contact || {}).filter(Boolean).join(" · ")}</p><hr>${secs}</body></html>`;
}

// ---------------- 面试准备 ----------------
export async function getInterviewPrep(resumeId: string): Promise<InterviewPrep | null> {
  if (isDemo()) { await M.sleep(250); return M.mockInterviewPreps[resumeId] ?? null; }
  return api<InterviewPrep | null>(`/resumes/${resumeId}/interview`);
}

export async function prepareInterview(resumeId: string, questionCount = 10): Promise<InterviewPrep> {
  if (isDemo()) {
    await M.sleep(2200); // 模拟三段 AI 生成耗时
    const base = M.mockInterviewPreps["r1"];
    const prep: InterviewPrep = JSON.parse(JSON.stringify(base));
    prep.id = M.uid(); prep.resume_id = resumeId; prep.updated_at = new Date().toISOString();
    M.mockInterviewPreps[resumeId] = prep;
    const r = M.mockResumes.find((x) => x.id === resumeId);
    if (r) r.has_interview_prep = true;
    return prep;
  }
  return api(`/resumes/${resumeId}/interview/prepare`, { method: "POST", body: JSON.stringify({ question_count: questionCount }) });
}

export async function regenerateInterview(resumeId: string, questionCount = 10): Promise<InterviewPrep> {
  if (isDemo()) { return prepareInterview(resumeId, questionCount); }
  return api(`/resumes/${resumeId}/interview/regenerate`, { method: "POST", body: JSON.stringify({ question_count: questionCount }) });
}

// ---------------- 报名表 ----------------
export async function listForms(): Promise<FormRecord[]> {
  if (isDemo()) { await M.sleep(250); return M.mockForms; }
  return api<FormRecord[]>("/forms");
}

export async function uploadForm(file: File): Promise<FormRecord> {
  if (isDemo()) {
    await M.sleep(700);
    const rec: FormRecord = {
      id: M.uid(), original_filename: file.name,
      file_type: file.name.endsWith(".pdf") ? "pdf" : file.name.endsWith(".docx") || file.name.endsWith(".doc") ? "word" : "excel",
      status: "uploaded", created_at: new Date().toISOString(),
      form_structure: null, field_mapping: null, filled_data: null,
    };
    M.mockForms.unshift(rec);
    return rec;
  }
  const fd = new FormData();
  fd.append("file", file);
  return api("/forms/upload", { method: "POST", body: fd });
}

export async function analyzeForm(id: string) {
  if (isDemo()) {
    await M.sleep(900);
    const f = M.mockForms.find((x) => x.id === id)!;
    f.status = "analyzed";
    f.form_structure = f.form_structure || {
      field_count: 4,
      fields: [
        { field_name: "姓名", field_type: "text" }, { field_name: "性别", field_type: "text" },
        { field_name: "毕业院校", field_type: "text" }, { field_name: "联系电话", field_type: "text" },
      ],
      raw_text_preview: "（演示解析结果）",
    };
    return f.form_structure;
  }
  return api(`/forms/${id}/analysis`);
}

export async function mapForm(id: string): Promise<FormMappingResult> {
  if (isDemo()) {
    await M.sleep(1100);
    const f = M.mockForms.find((x) => x.id === id)!;
    f.status = "mapped";
    f.field_mapping = {
      mappings: (f.form_structure?.fields || []).map((fld, i) => ({
        form_field: fld.field_name,
        profile_field: ["profiles.name", "profiles.gender", "educations[0].school", "profiles.phone"][i] || null,
        confidence: [0.99, 0.98, 0.95, 0.9][i] || 0.6,
        value: ["张文路", "男", "华东理工大学", "138****1111"][i] || null,
      })),
      unmapped: [], needs_review: [],
    };
    return f.field_mapping;
  }
  return api(`/forms/${id}/mapping`, { method: "POST", body: JSON.stringify({}) });
}

export async function fillForm(id: string) {
  if (isDemo()) {
    await M.sleep(800);
    const f = M.mockForms.find((x) => x.id === id)!;
    f.status = "filled";
    return { filled_path: `/demo/${f.original_filename}`, filled_data: {} };
  }
  return api(`/forms/${id}/fill`, { method: "POST", body: JSON.stringify({}) });
}

export async function downloadForm(rec: FormRecord) {
  if (isDemo()) {
    const text = `报名表对照填写（演示导出）\n========================\n` +
      (rec.field_mapping?.mappings || []).map((m) => `${m.form_field}：${m.value ?? ""}`).join("\n");
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${rec.original_filename.replace(/\.[^.]+$/, "")}_已填写.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
    return;
  }
  await apiDownload(`/forms/${rec.id}/download`, `${rec.original_filename}_已填写`);
}

// ---------------- 投递 ----------------
export async function listApplications(params = ""): Promise<{ total: number; items: Application[] }> {
  if (isDemo()) { await M.sleep(250); return { total: M.mockApplications.length, items: M.mockApplications }; }
  return api(`/applications${params}`);
}

export async function createApplication(data: Partial<Application>) {
  if (isDemo()) {
    await M.sleep(300);
    const resume = data.resume_id ? M.mockResumes.find((r) => r.id === data.resume_id) : undefined;
    const app: Application = {
      id: M.uid(), company_name: data.company_name!, position_title: data.position_title!,
      channel: data.channel || "website", status: "applied",
      applied_at: new Date().toISOString(), notes: data.notes || "", follow_up_date: data.follow_up_date || null,
      resume_id: data.resume_id || null,
      resume_version_name: resume?.version_name || null,
      // 演示模式同样体现「投递版本锁定」：关联了简历就打上快照标记
      has_snapshot: !!resume, snapshot_template: resume?.html_template || null,
      snapshot_match_score: resume?.match_score ?? null, has_snapshot_pdf: false,
    };
    M.mockApplications.unshift(app);
    return app;
  }
  return api("/applications", { method: "POST", body: JSON.stringify(data) });
}

/** 投递快照详情：招聘方当时实际看到的简历与 JD */
export async function getApplicationSnapshot(appId: string): Promise<ApplicationSnapshot> {
  if (isDemo()) {
    await M.sleep(250);
    const a = M.mockApplications.find((x) => x.id === appId);
    if (!a) throw new Error("投递记录不存在");
    const resume = a.resume_id ? M.mockResumes.find((r) => r.id === a.resume_id) : undefined;
    if (!resume) throw new Error("该投递记录没有版本快照（演示数据未关联简历）");
    const jd = M.mockJDs.find((j) => j.id === resume.jd_id);
    return {
      id: a.id, company_name: a.company_name, position_title: a.position_title,
      channel: a.channel, status: a.status, applied_at: a.applied_at,
      resume_version_name: resume.version_name, snapshot_template: resume.html_template,
      snapshot_match_score: resume.match_score, has_snapshot_pdf: false,
      resume_snapshot: JSON.parse(JSON.stringify(resume.resume_data)),
      jd_snapshot: jd ? { company_name: jd.company_name, position_title: jd.position_title, raw_text: jd.raw_text, parsed_data: jd.parsed_data } : null,
    };
  }
  return api<ApplicationSnapshot>(`/applications/${appId}/snapshot`);
}

/** 下载投递时锁定的 PDF 副本（FileResponse 原始字节，走 apiDownload） */
export async function downloadSnapshotPdf(app: Application) {
  if (isDemo()) {
    const resume = app.resume_id ? M.mockResumes.find((r) => r.id === app.resume_id) : undefined;
    if (!resume) throw new Error("演示数据没有关联简历");
    const blob = new Blob([renderResumeHTML(resume)], { type: "text/html;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${app.company_name}_${app.position_title}_投递快照.html`;
    a.click();
    URL.revokeObjectURL(a.href);
    return;
  }
  await apiDownload(`/applications/${app.id}/snapshot/pdf`, `${app.company_name}_${app.position_title}_投递快照.pdf`);
}

export async function updateApplication(id: string, data: any) {
  if (isDemo()) {
    await M.sleep(250);
    const a = M.mockApplications.find((x) => x.id === id)!;
    Object.assign(a, data);
    return a;
  }
  return api(`/applications/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteApplication(id: string) {
  if (isDemo()) {
    await M.sleep(250);
    const i = M.mockApplications.findIndex((x) => x.id === id);
    if (i >= 0) M.mockApplications.splice(i, 1);
    return;
  }
  return api(`/applications/${id}`, { method: "DELETE" });
}

export async function getStats(): Promise<AppStats> {
  if (isDemo()) { await M.sleep(200); return M.mockStats; }
  return api("/applications/stats");
}

export async function getFollowUps(): Promise<Application[]> {
  if (isDemo()) { await M.sleep(200); return M.mockApplications.filter((a) => a.follow_up_date && !["offer", "rejected"].includes(a.status)); }
  return api("/applications/follow-ups");
}

// ---------------- 自定义信息块 ----------------
const blocksOf = () => (M.mockProfile.custom_blocks ??= []);

export async function createBlock(name: string, fields: ProfileBlockField[]): Promise<ProfileBlock> {
  if (isDemo()) {
    await M.sleep(300);
    const block: ProfileBlock = { id: M.uid(), profile_id: M.mockProfile.id, name, fields, order_index: blocksOf().length, entries: [] };
    blocksOf().push(block);
    return block;
  }
  return api("/profile/blocks", { method: "POST", body: JSON.stringify({ name, fields }) });
}

export async function updateBlock(block_id: string, data: { name?: string; fields?: ProfileBlockField[] }) {
  if (isDemo()) {
    await M.sleep(300);
    const block = blocksOf().find((b) => b.id === block_id);
    if (block) Object.assign(block, data);
    return block;
  }
  return api(`/profile/blocks/${block_id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteBlock(block_id: string) {
  if (isDemo()) {
    await M.sleep(250);
    const list = blocksOf();
    const i = list.findIndex((b) => b.id === block_id);
    if (i >= 0) list.splice(i, 1);
    return;
  }
  return api(`/profile/blocks/${block_id}`, { method: "DELETE" });
}

export async function addBlockEntry(block_id: string, data: Record<string, any>): Promise<BlockEntry> {
  if (isDemo()) {
    await M.sleep(250);
    const block = blocksOf().find((b) => b.id === block_id)!;
    const entry: BlockEntry = { id: M.uid(), block_id, data, order_index: block.entries.length };
    block.entries.push(entry);
    return entry;
  }
  return api(`/profile/blocks/${block_id}/entries`, { method: "POST", body: JSON.stringify({ data }) });
}

export async function updateBlockEntry(block_id: string, entry_id: string, data: Record<string, any>) {
  if (isDemo()) {
    await M.sleep(250);
    const entry = blocksOf().find((b) => b.id === block_id)?.entries.find((e) => e.id === entry_id);
    if (entry) entry.data = data;
    return entry;
  }
  return api(`/profile/blocks/${block_id}/entries/${entry_id}`, { method: "PUT", body: JSON.stringify({ data }) });
}

export async function deleteBlockEntry(block_id: string, entry_id: string) {
  if (isDemo()) {
    await M.sleep(250);
    const block = blocksOf().find((b) => b.id === block_id);
    if (block) {
      const i = block.entries.findIndex((e) => e.id === entry_id);
      if (i >= 0) block.entries.splice(i, 1);
    }
    return;
  }
  return api(`/profile/blocks/${block_id}/entries/${entry_id}`, { method: "DELETE" });
}

// ---------------- 版块自定义字段 ----------------
const fieldDefsOf = () => (M.mockProfile.field_defs ??= []);

export async function createFieldDef(section: string, name: string, label: string, type: FieldDef["type"]): Promise<FieldDef> {
  if (isDemo()) {
    await M.sleep(300);
    const def: FieldDef = { id: M.uid(), profile_id: M.mockProfile.id, section, name, label, type, order_index: fieldDefsOf().length };
    fieldDefsOf().push(def);
    return def;
  }
  return api("/profile/field-defs", { method: "POST", body: JSON.stringify({ section, name, label, type }) });
}

export async function updateFieldDef(def_id: string, data: { label?: string; type?: FieldDef["type"] }) {
  if (isDemo()) {
    await M.sleep(300);
    const def = fieldDefsOf().find((d) => d.id === def_id);
    if (def) Object.assign(def, data);
    return def;
  }
  return api(`/profile/field-defs/${def_id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteFieldDef(def_id: string) {
  if (isDemo()) {
    await M.sleep(250);
    const list = fieldDefsOf();
    const i = list.findIndex((d) => d.id === def_id);
    if (i >= 0) list.splice(i, 1);
    return;
  }
  return api(`/profile/field-defs/${def_id}`, { method: "DELETE" });
}

// ---------------- 照片库 ----------------
export async function listPhotos(category?: string): Promise<Photo[]> {
  if (isDemo()) {
    await M.sleep(250);
    return category ? M.mockPhotos.filter((p) => p.category === category) : [...M.mockPhotos];
  }
  return api(`/photos${category ? `?category=${encodeURIComponent(category)}` : ""}`);
}

export async function uploadPhoto(file: File, category: string): Promise<Photo> {
  if (isDemo()) {
    await M.sleep(600);
    const photo: Photo = {
      id: M.uid(), user_id: "u1", category,
      original_filename: file.name, mime_type: file.type, size: file.size,
      created_at: new Date().toISOString(), _localUrl: URL.createObjectURL(file),
    };
    M.mockPhotos.unshift(photo);
    return photo;
  }
  const fd = new FormData();
  fd.append("file", file);
  fd.append("category", category);
  return api("/photos/upload", { method: "POST", body: fd });
}

export async function deletePhoto(photo_id: string) {
  if (isDemo()) {
    await M.sleep(250);
    const i = M.mockPhotos.findIndex((p) => p.id === photo_id);
    if (i >= 0) M.mockPhotos.splice(i, 1);
    return;
  }
  return api(`/photos/${photo_id}`, { method: "DELETE" });
}

/** 获取照片展示 URL（真实模式带鉴权拉 blob，演示模式用本地图/占位图） */
export async function photoUrl(photo: Photo): Promise<string> {
  if (isDemo()) return photo._localUrl || photo.demo_url || "";
  return apiBlobUrl(`/photos/${photo.id}/file`);
}

// ---------------- 后台管理（仅管理员） ----------------
export async function adminListUsers(keyword = ""): Promise<AdminUser[]> {
  if (isDemo()) {
    await M.sleep(250);
    return keyword ? M.mockUsers.filter((u) => u.username.includes(keyword) || u.email.includes(keyword)) : M.mockUsers;
  }
  return api(`/admin/users${keyword ? `?keyword=${encodeURIComponent(keyword)}` : ""}`);
}

export async function adminCreateUser(data: { username: string; email: string; password: string; is_admin: boolean }): Promise<AdminUser> {
  if (isDemo()) {
    await M.sleep(300);
    const u: AdminUser = { id: M.uid(), username: data.username, email: data.email, is_admin: data.is_admin, created_at: new Date().toISOString() };
    M.mockUsers.push(u);
    return u;
  }
  return api("/admin/users", { method: "POST", body: JSON.stringify(data) });
}

export async function adminUpdateUser(id: string, data: { email?: string; is_admin?: boolean }) {
  if (isDemo()) {
    await M.sleep(250);
    const u = M.mockUsers.find((x) => x.id === id);
    if (u) Object.assign(u, data);
    return u;
  }
  return api(`/admin/users/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function adminDeleteUser(id: string) {
  if (isDemo()) {
    await M.sleep(250);
    const i = M.mockUsers.findIndex((x) => x.id === id);
    if (i >= 0) M.mockUsers.splice(i, 1);
    return;
  }
  return api(`/admin/users/${id}`, { method: "DELETE" });
}

export async function adminResetPassword(id: string, new_password: string) {
  if (isDemo()) { await M.sleep(300); return; }
  return api(`/admin/users/${id}/reset-password`, { method: "POST", body: JSON.stringify({ new_password }) });
}

export async function getConfig(): Promise<KimiConfig> {
  if (isDemo()) { await M.sleep(200); return { ...M.mockConfig }; }
  return api("/admin/config");
}

export async function updateConfig(data: Partial<KimiConfig>): Promise<KimiConfig> {
  // 后端要求全部为字符串（兼容旧响应回显的数字值）
  const payload = Object.fromEntries(Object.entries(data).map(([k, v]) => [k, v == null ? null : String(v)]));
  if (isDemo()) {
    await M.sleep(300);
    Object.assign(M.mockConfig, payload);
    return { ...M.mockConfig };
  }
  return api("/admin/config", { method: "PUT", body: JSON.stringify(payload) });
}
