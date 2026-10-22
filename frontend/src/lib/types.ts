/** 与后端 schemas 对齐的前端类型定义 */

export interface ProfileFull {
  id: string; user_id: string; name: string; gender: string | null;
  birth_date: string | null; phone: string | null; email: string | null;
  location: string | null; political_status: string | null; avatar_url: string | null;
  summary: string | null; completeness_score: number;
  educations: SubEntity[]; work_experiences: SubEntity[];
  projects: SubEntity[]; skills: SubEntity[];
  certifications: SubEntity[]; family_members: SubEntity[];
  custom_blocks?: ProfileBlock[];
  field_defs?: FieldDef[];
  custom_fields?: Record<string, any>;
}

export type SubEntity = Record<string, any> & { id: string; custom_fields?: Record<string, any> };

/** 档案版块自定义字段定义 */
export interface FieldDef {
  id: string; profile_id: string; section: string; name: string;
  label: string; type: "text" | "number" | "date" | "textarea"; order_index: number;
}

/** 自定义信息块：字段定义 + 条目记录（两级） */
export interface ProfileBlockField {
  name: string; label: string; type: "text" | "number" | "date" | "textarea";
}

export interface BlockEntry {
  id: string; block_id: string; data: Record<string, any>; order_index: number;
}

export interface ProfileBlock {
  id: string; profile_id: string; name: string;
  fields: ProfileBlockField[]; order_index: number; entries: BlockEntry[];
}

/** 后台管理：用户 / 系统配置 */
export interface AdminUser {
  id: string; username: string; email: string; is_admin: boolean; created_at: string;
}

export interface KimiConfig {
  KIMI_API_KEY: string; KIMI_BASE_URL: string; KIMI_MODEL: string;
  KIMI_TIMEOUT: string; KIMI_MAX_TOKENS: string;
  /** 推理模型思考强度 low/high/max。默认 max 会把整份简历生成拖过 500 秒。 */
  KIMI_REASONING_EFFORT: string;
}

export interface JDParsed {
  company?: string | null; position?: string | null;
  hard_requirements?: string[]; soft_requirements?: string[];
  core_responsibilities?: string[]; bonus_items?: string[];
  keywords?: string[]; ats_keywords?: string[];
  education_requirement?: string | null; experience_years?: string | null;
  salary_range?: string | null;
}

export interface JD {
  id: string; company_name: string | null; position_title: string | null;
  raw_text: string; parsed_data: JDParsed | null; created_at: string;
}

export interface ResumeSection {
  type: string; title: string; content?: string; items?: any[];
}

export interface MatchDetail {
  requirement: string;
  priority: "must" | "core" | "bonus";
  status: "direct" | "adjacent" | "missing";
  evidence_refs: string[];
  resume_usage: string;
}

/** AI 针对 JD 缺口给出的已有工作经历 bullet 建议；旧数据可能仍含 project。 */
export interface Enhancement {
  gap: string; basis: string; risk: "high" | "medium" | "low";
  target_source_ref?: string;
  suggested_bullets?: string[];
  legacy?: boolean;
  project?: {
    name: string; role?: string; tech_stack?: string[];
    period?: string; bullets?: string[];
  };
}

export type ResumeTemplate = "default" | "technical" | "management" | "compact";

/** GET /resumes/{id}/stats：字数/预计页数/JD 关键词覆盖（确定性计算） */
export interface ResumeStats {
  char_count: number; item_count: number; bullet_count: number;
  estimated_pages: number;
  keyword_total: number; keyword_covered: number;
  keyword_coverage: number | null;
  missing_keywords: string[];
}

/** 版本历史：每次内容落地追加一条，当前内容永远是最新版本 */
export type ResumeVersionLabel = "ai_generated" | "user_edit" | "enhancement_applied" | "rollback";

export interface ResumeVersionMeta {
  id: string; version_no: number; label: ResumeVersionLabel | string;
  match_score: number | null; created_at: string;
}

export interface ResumeVersionDetail extends ResumeVersionMeta {
  resume_data: { header?: any; sections?: ResumeSection[]; match_details?: MatchDetail[] };
}

export const VERSION_LABEL_META: Record<string, { label: string; cls: string }> = {
  ai_generated: { label: "AI 生成", cls: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30" },
  user_edit: { label: "手动编辑", cls: "bg-violet-500/15 text-violet-300 border-violet-500/30" },
  enhancement_applied: { label: "经历优化", cls: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
  rollback: { label: "版本回滚", cls: "bg-slate-500/15 text-slate-300 border-slate-500/30" },
};

export interface Resume {
  id: string; jd_id: string | null; version_name: string;
  resume_data: { header?: any; sections?: ResumeSection[]; match_details?: MatchDetail[] };
  match_score: number | null; highlights: string[]; gaps: string[];
  suggestions: string[]; html_template: string; status: string;
  preferences?: { page_limit?: number; language?: string; target_level?: string; template?: ResumeTemplate };
  error_message?: string | null;
  enhancements?: Enhancement[] | null;
  has_interview_prep?: boolean;
  created_at: string;
  updated_at?: string;
}

export interface InterviewQuestion {
  type: string; question: string; reference_answer: string; key_points?: string[];
}

export interface InterviewPrep {
  id: string; resume_id: string;
  research: {
    position_analysis?: string; company_points?: string[]; hot_topics?: string[];
    interviewer_focus?: string[]; advice?: string[];
  };
  outline: {
    rounds?: { stage: string; duration?: string; focus?: string[]; likely_questions?: string[] }[];
    self_intro_points?: string[]; questions_to_ask?: string[];
  };
  questions: InterviewQuestion[];
  /** pending = 后台生成中；generated = 已完成；failed = 生成失败（旧内容会保留） */
  status?: "pending" | "generated" | "failed";
  error_message?: string | null;
  updated_at: string;
}

export interface FormRecord {
  id: string; original_filename: string; file_type: string;
  form_structure: FormStructure | null; field_mapping: FormMappingResult | null;
  filled_data: Record<string, any> | null; status: string; created_at: string;
}

export interface FormFieldItem {
  field_name: string; field_type: string; value?: string | null;
  page?: number | null; cell?: string | null;
}

export interface FormStructure {
  fields: FormFieldItem[]; field_count: number; raw_text_preview: string;
}

export interface MappingItem {
  form_field: string; profile_field?: string | null;
  confidence: number; value?: string | null;
}

export interface FormMappingResult {
  mappings: MappingItem[]; unmapped: string[]; needs_review: string[];
}

/** 照片库 */
export interface Photo {
  id: string; user_id: string; category: string;
  original_filename: string; mime_type: string | null;
  size: number | null; created_at: string;
  _localUrl?: string; // 演示模式：本地选择的文件 Object URL
  demo_url?: string;  // 演示模式：预置占位图
}

export type AppStatus = "applied" | "viewed" | "interview" | "offer" | "rejected";

export interface Application {
  id: string; company_name: string; position_title: string;
  channel: string; status: AppStatus; applied_at: string;
  notes: string | null; follow_up_date: string | null;
  resume_id?: string | null;
  resume_version_name?: string | null;
  jd_company?: string | null;
  jd_position?: string | null;
  /** 投递版本锁定：有快照说明记录的是招聘方当时实际看到的版本 */
  has_snapshot?: boolean;
  snapshot_template?: string | null;
  snapshot_match_score?: number | null;
  has_snapshot_pdf?: boolean;
}

/** GET /applications/{id}/snapshot：投递时锁定的简历与 JD */
export interface ApplicationSnapshot {
  id: string; company_name: string; position_title: string;
  channel: string; status: AppStatus; applied_at: string;
  resume_version_name?: string | null;
  snapshot_template?: string | null;
  snapshot_match_score?: number | null;
  has_snapshot_pdf?: boolean;
  resume_snapshot?: { header?: any; sections?: ResumeSection[] } | null;
  jd_snapshot?: { company_name?: string | null; position_title?: string | null; raw_text?: string; parsed_data?: any } | null;
}

export interface AppStats {
  total: number; by_status: Record<string, number>;
  by_channel: Record<string, number>; conversion_rate: number; recent_7_days: number;
  trend_30d?: { date: string; count: number }[];
}

export const STATUS_META: Record<string, { label: string; color: string }> = {
  applied:   { label: "已投递", color: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
  viewed:    { label: "已查看", color: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
  interview: { label: "面试中", color: "bg-violet-500/15 text-violet-300 border-violet-500/30" },
  offer:     { label: "Offer",  color: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
  rejected:  { label: "已拒绝", color: "bg-rose-500/15 text-rose-300 border-rose-500/30" },
};

export const CHANNEL_META: Record<string, string> = {
  email: "邮件", website: "网站", official: "官网/公告",
};
