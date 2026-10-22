/** 演示模式数据：内存态存储，CRUD 操作真实生效（刷新还原） */
import type {
  AdminUser, Application, AppStats, FormRecord,
  InterviewPrep, JD, KimiConfig, Photo, ProfileFull, Resume, ResumeStats,
  ResumeVersionDetail, SubEntity,
} from "./types";

const uid = () => Math.random().toString(16).slice(2, 10) + Date.now().toString(16);
export const sleep = (ms = 600) => new Promise((r) => setTimeout(r, ms));

const now = new Date();
const daysAgo = (n: number) => new Date(now.getTime() - n * 86400000).toISOString();

// ---------------- 档案 ----------------
export const mockProfile: ProfileFull = {
  id: "p1", user_id: "u1", name: "张文路", gender: "男", birth_date: "1998-05-12",
  phone: "13800001111", email: "wenlu@example.com", location: "上海",
  political_status: "共青团员", avatar_url: null,
  summary: "3 年后端开发经验，主导过高并发订单系统与微服务架构迁移，熟悉 Go / Java 生态，关注系统稳定性与工程效率。",
  completeness_score: 86,
  custom_fields: { native_place: "江苏南京" },
  field_defs: [
    { id: "fd1", profile_id: "p1", section: "basic", name: "native_place", label: "籍贯", type: "text", order_index: 0 },
    { id: "fd2", profile_id: "p1", section: "educations", name: "major_rank", label: "专业排名", type: "text", order_index: 0 },
  ],
  educations: [
    { id: "e1", school: "华东理工大学", major: "计算机科学与技术", degree: "本科", start_date: "2016-09-01", end_date: "2020-06-30", gpa: "3.6/4.0", courses: ["数据结构", "操作系统", "分布式系统"], is_current: false, visibility: true, priority: 5, order_index: 0, custom_fields: { major_rank: "前 10%" } },
  ],
  work_experiences: [
    { id: "w1", company: "星云科技", position: "后端开发工程师", start_date: "2023-06-01", end_date: null, is_current: true, visibility: true, priority: 9, order_index: 0,
      description: ["负责订单中台后端服务设计与开发", "主导微服务架构迁移，单体拆分为 8 个独立服务"],
      achievements: ["订单系统 QPS 从 1k 提升至 5k", "接口平均响应时间下降 42%"] },
    { id: "w2", company: "远航信息", position: "Java 开发工程师", start_date: "2020-07-01", end_date: "2023-05-31", is_current: false, visibility: true, priority: 7, order_index: 1,
      description: ["参与电商供应链系统迭代"], achievements: ["库存扣减方案优化，超卖率降为 0"] },
  ],
  projects: [
    { id: "pr1", name: "高并发秒杀系统", role: "核心开发", tech_stack: ["Go", "Redis", "Kafka", "MySQL"], start_date: "2024-01-01", end_date: "2024-06-30", visibility: true, priority: 9, order_index: 0,
      description: ["支撑 10w+ 峰值流量的秒杀活动"], highlights: ["Redis 预减库存 + 消息队列异步下单", "令牌桶限流，峰值稳定运行零故障"] },
    { id: "pr2", name: "智能简历投递系统", role: "独立开发", tech_stack: ["FastAPI", "React", "MySQL", "Kimi API"], start_date: "2026-07-01", end_date: null, visibility: true, priority: 8, order_index: 1,
      description: ["AI 驱动的简历定制与报名表自动填写平台"], highlights: ["JD 解析 → 简历生成 → PDF 导出全链路"] },
  ],
  skills: [
    { id: "s1", name: "Go", category: "编程语言", proficiency: 5, visibility: true, order_index: 0 },
    { id: "s2", name: "Java", category: "编程语言", proficiency: 4, visibility: true, order_index: 1 },
    { id: "s3", name: "Redis", category: "中间件", proficiency: 4, visibility: true, order_index: 2 },
    { id: "s4", name: "MySQL", category: "数据库", proficiency: 4, visibility: true, order_index: 3 },
    { id: "s5", name: "Docker", category: "工具", proficiency: 3, visibility: true, order_index: 4 },
  ],
  certifications: [
    { id: "c1", name: "阿里云 ACP 云计算工程师", issuer: "阿里云", issue_date: "2024-03-15", expiry_date: null, credential_id: "ACP-2024-0315", visibility: true, order_index: 0 },
  ],
  family_members: [
    { id: "f1", name: "张建国", relationship: "父子", work_unit: "已退休", position: "", phone: "13900002222" },
  ],
  custom_blocks: [
    {
      id: "b1", profile_id: "p1", name: "父母信息", order_index: 0,
      fields: [
        { name: "name", label: "姓名", type: "text" },
        { name: "relationship", label: "关系", type: "text" },
        { name: "work_unit", label: "工作单位", type: "text" },
      ],
      entries: [
        { id: "be1", block_id: "b1", order_index: 0, data: { name: "张建国", relationship: "父亲", work_unit: "已退休" } },
        { id: "be2", block_id: "b1", order_index: 1, data: { name: "李秀兰", relationship: "母亲", work_unit: "社区卫生站" } },
      ],
    },
  ],
};

// ---------------- JD ----------------
export const mockJDs: JD[] = [
  {
    id: "jd1", company_name: "字节跳动", position_title: "后端开发工程师",
    raw_text: "负责抖音电商订单系统后端开发……（演示 JD）",
    created_at: daysAgo(2),
    parsed_data: {
      company: "字节跳动", position: "后端开发工程师",
      hard_requirements: ["3 年以上后端经验", "精通 Go 或 Java", "熟悉分布式系统与高并发"],
      soft_requirements: ["良好的沟通能力", "结果导向"],
      core_responsibilities: ["负责订单系统后端服务设计与开发", "参与系统架构优化与稳定性建设"],
      bonus_items: ["有开源项目贡献", "熟悉 Kubernetes"],
      keywords: ["Go", "gRPC", "Redis", "MySQL", "微服务", "高并发"],
      ats_keywords: ["backend", "distributed systems", "high concurrency"],
      education_requirement: "本科及以上", experience_years: "3-5 年", salary_range: "25k-40k",
    },
  },
  {
    id: "jd2", company_name: "蚂蚁集团", position_title: "Java 高级开发",
    raw_text: "负责支付清结算系统研发……（演示 JD）",
    created_at: daysAgo(6),
    parsed_data: {
      company: "蚂蚁集团", position: "Java 高级开发",
      hard_requirements: ["5 年以上 Java 经验", "熟悉分布式事务"],
      soft_requirements: ["抗压能力强"], core_responsibilities: ["支付核心链路研发"],
      bonus_items: ["有金融系统经验"], keywords: ["Java", "Spring Cloud", "分布式事务", "RocketMQ"],
      ats_keywords: ["payment", "fintech"], education_requirement: "本科及以上",
      experience_years: "5 年以上", salary_range: "30k-50k",
    },
  },
];

// ---------------- 简历 ----------------
export const mockResumes: Resume[] = [
  {
    id: "r1", jd_id: "jd1", version_name: "字节跳动_后端开发_20260717",
    match_score: 82, status: "exported", has_interview_prep: true, created_at: daysAgo(1),
    highlights: ["3 年 Go 后端经验与 JD 高度匹配", "高并发订单系统经验直接对口", "微服务迁移实战成果可量化"],
    gaps: ["缺少 Kubernetes 生产经验", "无开源项目贡献记录"],
    suggestions: ["在项目经历中补充容器化部署内容", "准备 QPS 提升的技术细节以应对追问"],
    html_template: "technical",
    resume_data: {
      header: { name: "张文路", title: "后端开发工程师", contact: { phone: "138****1111", email: "wenlu@example.com", location: "上海" } },
      sections: [
        { type: "summary", title: "个人总结", content: "3 年后端开发经验，擅长高并发系统设计与优化，主导订单系统 QPS 从 1k 提升至 5k，熟悉 Go 微服务生态。" },
        { type: "skills", title: "专业技能", items: [
          { name: "Go", level: "精通", relevance: 10 }, { name: "gRPC", level: "熟练", relevance: 9 },
          { name: "Redis", level: "熟练", relevance: 8 }, { name: "MySQL", level: "熟练", relevance: 7 },
          { name: "Java", level: "熟练", relevance: 6 } ] },
        { type: "experience", title: "工作经历", items: [
          { company: "星云科技", position: "后端开发工程师", period: "2023.06 - 至今",
            bullets: ["设计并实现高并发订单系统，QPS 从 1k 提升到 5k，使用 Go + gRPC + Redis",
                      "主导微服务架构迁移，将单体应用拆分为 8 个独立服务，发布效率提升 3 倍"] },
          { company: "远航信息", position: "Java 开发工程师", period: "2020.07 - 2023.05",
            bullets: ["负责供应链库存模块，设计预扣减方案，超卖率降为 0"] } ] },
        { type: "projects", title: "项目经历", items: [
          { name: "高并发秒杀系统", role: "核心开发", tech_stack: ["Go", "Redis", "Kafka"], period: "2024.01 - 2024.06",
            bullets: ["Redis 预减库存 + Kafka 异步下单，支撑 10w+ 峰值流量", "令牌桶限流保障大促零故障"] } ] },
        { type: "education", title: "教育经历", items: [
          { school: "华东理工大学", major: "计算机科学与技术", degree: "本科", period: "2016.09 - 2020.06" } ] },
      ],
    },
  },
  {
    id: "r2", jd_id: "jd2", version_name: "蚂蚁集团_Java高级开发_20260712",
    match_score: 68, status: "generated", created_at: daysAgo(5),
    highlights: ["Java 基础扎实", "有分布式系统经验"],
    gaps: ["分布式事务实战经验不足", "金融支付领域经验缺失"],
    suggestions: ["补充 Seata / TCC 相关学习或实践"], html_template: "technical",
    resume_data: { header: { name: "张文路", title: "Java 高级开发", contact: {} }, sections: [] },
  },
];

// ---------------- 简历版本历史（演示数据） ----------------
// 内存态：编辑/优化/回滚都会追加一条，与后端「当前内容永远是最新版本」约定一致
export const mockResumeVersions: Record<string, ResumeVersionDetail[]> = {};

function seedVersion(resumeId: string, label: string, data: any, match_score: number | null, whenDaysAgo: number) {
  const list = (mockResumeVersions[resumeId] ||= []);
  list.push({
    id: uid(), version_no: list.length + 1, label, match_score,
    created_at: daysAgo(whenDaysAgo), resume_data: JSON.parse(JSON.stringify(data)),
  });
}
// r1 预置一条 AI 初始版本（summary 略不同，便于演示 diff）
seedVersion("r1", "ai_generated", {
  ...mockResumes[0].resume_data,
  sections: mockResumes[0].resume_data.sections!.map((s) =>
    s.type === "summary" ? { ...s, content: "后端开发工程师，熟悉 Go 微服务生态，有高并发系统经验。" } : s),
}, 78, 1);
seedVersion("r1", "user_edit", mockResumes[0].resume_data, 82, 0.5);

/** 追加一条版本快照（演示模式编辑/优化/回滚共用） */
export function pushMockVersion(resumeId: string, label: string, data: any, match_score: number | null) {
  seedVersion(resumeId, label, data, match_score, 0);
}

/** 前端版 stats 计算：与后端 resume_stats 同一套确定性口径（隐藏条目不计） */
export function computeMockStats(resume: Resume): ResumeStats {
  const data = resume.resume_data || {};
  const parts: string[] = [String(data.header?.title || "")];
  let item_count = 0, bullet_count = 0;
  for (const sec of data.sections || []) {
    if (sec.type === "summary") { parts.push(String(sec.content || "")); continue; }
    for (const it of (sec.items || []) as any[]) {
      if (it.hidden) continue;
      item_count++;
      for (const k of ["company", "position", "period", "name", "role", "school", "major", "degree", "issuer", "category", "level"]) {
        if (typeof it[k] === "string") parts.push(it[k]);
      }
      for (const lk of ["tech_stack", "bullets"]) {
        if (Array.isArray(it[lk])) { parts.push(...it[lk].map(String)); bullet_count += lk === "bullets" ? it[lk].length : 0; }
      }
    }
  }
  const text = parts.join("\n");
  const char_count = text.replace(/\s/g, "").length;
  const jd = mockJDs.find((j) => j.id === resume.jd_id);
  const keywords = [...(jd?.parsed_data?.keywords || []), ...(jd?.parsed_data?.ats_keywords || [])].map((k) => String(k).trim()).filter(Boolean);
  const lowered = text.toLowerCase();
  const covered = keywords.filter((k) => lowered.includes(k.toLowerCase()));
  const missing = keywords.filter((k) => !lowered.includes(k.toLowerCase()));
  return {
    char_count, item_count, bullet_count,
    estimated_pages: Math.max(1, Math.ceil(char_count / 900)),
    keyword_total: keywords.length, keyword_covered: covered.length,
    keyword_coverage: keywords.length ? Math.round((covered.length / keywords.length) * 100) : null,
    missing_keywords: missing.slice(0, 20),
  };
}

// ---------------- 面试准备（演示数据） ----------------
export const mockInterviewPreps: Record<string, InterviewPrep> = {
  r1: {
    id: "ip1", resume_id: "r1", updated_at: daysAgo(1),
    research: {
      position_analysis: "该岗位定位为高并发后端开发，核心职责包括订单/交易链路的服务设计与性能优化，预计团队对 Go 微服务体系投入较深。",
      company_points: ["业务峰值流量大，对稳定性要求高", "技术栈以 Go + gRPC + Redis 为主", "可能涉及容器化与云原生改造"],
      hot_topics: ["高并发下的缓存与限流设计", "微服务拆分与治理", "数据库分库分表实践"],
      interviewer_focus: ["QPS 从 1k 到 5k 的具体手段与数据支撑", "秒杀系统中 Redis 预减库存的一致性保障", "微服务迁移中遇到的难点与决策过程"],
      advice: ["准备 2 个可量化的项目故事，用 STAR 展开", "复习分布式系统常见八股：限流/降级/幂等", "提前了解目标团队的业务与技术分享"],
    },
    outline: {
      rounds: [
        { stage: "一面（技术基础）", duration: "45min", focus: ["Go 语言基础", "数据库与缓存", "项目初探"],
          likely_questions: ["Go 的 goroutine 调度模型？", "Redis 缓存穿透/雪崩怎么防？", "介绍一个你最有成就感的项目"] },
        { stage: "二面（项目深挖）", duration: "60min", focus: ["高并发方案细节", "架构决策", "故障处理"],
          likely_questions: ["QPS 5k 的压测数据和瓶颈在哪？", "秒杀链路如何保证不超卖？", "线上事故怎么排查？"] },
        { stage: "三面（主管面）", duration: "40min", focus: ["职业规划", "团队协作", "稳定性"],
          likely_questions: ["为什么看新机会？", "和意见不合的同事怎么协作？"] },
      ],
      self_intro_points: ["3 年后端 + 高并发订单系统经验", "QPS 1k→5k 的量化成果", "微服务迁移主导经验"],
      questions_to_ask: ["团队目前最大的技术挑战是什么？", "新人入职后的业务熟悉路径？", "团队的技术分享与成长机制？"],
    },
    questions: [
      { type: "technical", question: "你提到将订单系统 QPS 从 1k 提升到 5k，具体是怎么做的？",
        reference_answer: "先通过压测定位瓶颈在数据库单点查询，随后引入 Redis 缓存热点数据、读写分离，并将同步下单改为 Kafka 异步削峰，最终压测稳定在 5k+。",
        key_points: ["压测定位瓶颈", "缓存与读写分离", "异步削峰"] },
      { type: "project", question: "秒杀系统中 Redis 预减库存如何保证与数据库的一致性？",
        reference_answer: "用 Lua 脚本原子扣减 + 消息队列异步落库，配合幂等消费与对账任务兼顾极端场景。",
        key_points: ["Lua 原子操作", "异步落库幂等", "对账兑底"] },
      { type: "behavior", question: "微服务迁移时跨团队遇到最大的阻力是什么，你怎么推动的？",
        reference_answer: "最大阻力是各团队接口改造优先级不一，我通过制定兼容方案 + 双跑过渡 + 里程碑同步会推进，最终发布效率提升 3 倍。",
        key_points: ["兼容方案", "双跑过渡", "沟通协调"] },
    ],
  },
};

// ---------------- 报名表 ----------------
export const mockForms: FormRecord[] = [
  {
    id: "fm1", original_filename: "事业单位公开招聘报名表.docx", file_type: "word",
    status: "filled", created_at: daysAgo(3),
    form_structure: {
      field_count: 5,
      fields: [
        { field_name: "姓名", field_type: "text" }, { field_name: "性别", field_type: "text" },
        { field_name: "毕业院校", field_type: "text" }, { field_name: "政治面貌", field_type: "text" },
        { field_name: "联系电话", field_type: "text" },
      ],
      raw_text_preview: "姓名 | ____ 性别 | ____ 毕业院校 | ____……",
    },
    field_mapping: {
      mappings: [
        { form_field: "姓名", profile_field: "profiles.name", confidence: 0.99, value: "张文路" },
        { form_field: "性别", profile_field: "profiles.gender", confidence: 0.98, value: "男" },
        { form_field: "毕业院校", profile_field: "educations[0].school", confidence: 0.95, value: "华东理工大学" },
        { form_field: "政治面貌", profile_field: "profiles.political_status", confidence: 0.72, value: "共青团员" },
      ],
      unmapped: ["特长爱好"], needs_review: ["政治面貌"],
    },
    filled_data: { "姓名": "张文路", "性别": "男", "毕业院校": "华东理工大学", "政治面貌": "共青团员" },
  },
  {
    id: "fm2", original_filename: "国企校招登记表.xlsx", file_type: "excel",
    status: "analyzed", created_at: daysAgo(1),
    form_structure: {
      field_count: 4,
      fields: [
        { field_name: "姓名", field_type: "text" }, { field_name: "出生日期", field_type: "date" },
        { field_name: "最高学历", field_type: "text" }, { field_name: "工作单位", field_type: "text" },
      ],
      raw_text_preview: "姓名 | ____ 出生日期 | ____……",
    },
    field_mapping: null, filled_data: null,
  },
];

// ---------------- 投递 ----------------
export const mockApplications: Application[] = [
  { id: "a1", company_name: "字节跳动", position_title: "后端开发工程师", channel: "website", status: "interview", applied_at: daysAgo(2), notes: "一面已过，准备二面（高并发专题）", follow_up_date: daysAgo(-1).slice(0, 10), resume_version_name: "字节跳动_后端开发_20260717" },
  { id: "a2", company_name: "蚂蚁集团", position_title: "Java 高级开发", channel: "website", status: "viewed", applied_at: daysAgo(5), notes: "HR 已查看简历", follow_up_date: daysAgo(-2).slice(0, 10), resume_version_name: "蚂蚁集团_Java高级开发_20260712" },
  { id: "a3", company_name: "拼多多", position_title: "服务端开发", channel: "email", status: "applied", applied_at: daysAgo(8), notes: "", follow_up_date: daysAgo(1).slice(0, 10), resume_version_name: null },
  { id: "a4", company_name: "某事业单位", position_title: "信息中心工程师", channel: "official", status: "applied", applied_at: daysAgo(10), notes: "报名表已提交，等笔试通知", follow_up_date: null, resume_version_name: null },
  { id: "a5", company_name: "米哈游", position_title: "后端开发", channel: "website", status: "rejected", applied_at: daysAgo(15), notes: "HC 冻结", follow_up_date: null, resume_version_name: null },
  { id: "a6", company_name: "小红书", position_title: "基础架构工程师", channel: "email", status: "offer", applied_at: daysAgo(20), notes: "口头 offer，等正式邮件", follow_up_date: null, resume_version_name: null },
];

export const mockTrend = Array.from({ length: 30 }, (_, i) => ({
  date: `${i + 1}日`,
  count: [0,1,0,2,1,0,3,1,0,0,2,1,1,0,4,2,0,1,0,1,2,0,3,1,0,2,1,0,1,2][i] ?? 0,
}));

export const mockStats: AppStats = {
  total: mockApplications.length,
  by_status: { applied: 2, viewed: 1, interview: 1, offer: 1, rejected: 1 },
  by_channel: { email: 2, website: 3, official: 1 },
  conversion_rate: 33.3,
  recent_7_days: 2,
  trend_30d: mockTrend,
};

// ---------------- 照片库 ----------------
const svgPhoto = (label: string, c1: string, c2: string) =>
  "data:image/svg+xml;utf8," + encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='480' height='360'>
      <defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
        <stop offset='0%' stop-color='${c1}'/><stop offset='100%' stop-color='${c2}'/>
      </linearGradient></defs>
      <rect width='480' height='360' fill='url(#g)'/>
      <text x='240' y='185' font-size='28' fill='white' text-anchor='middle' font-family='sans-serif'>${label}</text>
    </svg>`
  );

export const mockPhotos: Photo[] = [
  { id: "ph1", user_id: "u1", category: "work", original_filename: "团建合影.jpg", mime_type: "image/jpeg", size: 480000, created_at: daysAgo(2), demo_url: svgPhoto("工作照 · 团建合影", "#0891b2", "#6d28d9") },
  { id: "ph2", user_id: "u1", category: "work", original_filename: "工位一角.png", mime_type: "image/png", size: 350000, created_at: daysAgo(6), demo_url: svgPhoto("工作照 · 工位一角", "#065f46", "#0891b2") },
  { id: "ph3", user_id: "u1", category: "life", original_filename: "登山记录.jpg", mime_type: "image/jpeg", size: 620000, created_at: daysAgo(9), demo_url: svgPhoto("生活照 · 登山记录", "#b45309", "#dc2626") },
  { id: "ph4", user_id: "u1", category: "life", original_filename: "周末骑行.jpg", mime_type: "image/jpeg", size: 540000, created_at: daysAgo(15), demo_url: svgPhoto("生活照 · 周末骑行", "#7c3aed", "#db2777") },
];

// ---------------- 内存态增删改 ----------------
export function subAdd(list: SubEntity[], data: any): SubEntity {
  const item = { id: uid(), ...data };
  list.push(item);
  return item;
}
export function subUpdate(list: SubEntity[], id: string, data: any): SubEntity | null {
  const idx = list.findIndex((i) => i.id === id);
  if (idx < 0) return null;
  list[idx] = { ...list[idx], ...data };
  return list[idx];
}
export function subDelete(list: SubEntity[], id: string): void {
  const idx = list.findIndex((i) => i.id === id);
  if (idx >= 0) list.splice(idx, 1);
}
export { uid };

// ---------------- 后台管理 ----------------
export const mockUsers: AdminUser[] = [
  { id: "u-admin", username: "admin", email: "admin@localhost", is_admin: true, created_at: daysAgo(30) },
  { id: "u1", username: "张文路", email: "wenlu@example.com", is_admin: false, created_at: daysAgo(12) },
  { id: "u2", username: "李四", email: "lisi@example.com", is_admin: false, created_at: daysAgo(3) },
];

export const mockConfig: KimiConfig = {
  KIMI_API_KEY: "******abcd",
  KIMI_BASE_URL: "https://api.moonshot.cn/v1",
  KIMI_MODEL: "kimi-latest",
  KIMI_TIMEOUT: "120",
  KIMI_MAX_TOKENS: "4096",
  KIMI_REASONING_EFFORT: "high",
};
