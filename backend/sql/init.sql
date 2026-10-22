-- =====================================================================
-- 智能简历投递系统 · MySQL 8.0 初始化脚本
-- 说明：UUID 主键(CHAR(32) 存储 hex) · JSON 弹性字段 · 索引/外键/注释完整
-- 执行：mysql -uroot -p resume_system < init.sql
-- =====================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------- 1. users 用户表 ----------
CREATE TABLE IF NOT EXISTS users (
  id            CHAR(32)      NOT NULL PRIMARY KEY COMMENT 'UUID(hex)',
  username      VARCHAR(50)   NOT NULL COMMENT '登录用户名',
  email         VARCHAR(255)  NOT NULL COMMENT '登录邮箱',
  password_hash VARCHAR(255)  NOT NULL COMMENT 'bcrypt 哈希',
  is_admin      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '是否管理员',
  created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_users_username (username),
  UNIQUE KEY uk_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表：登录账号信息';

-- ---------- 2. profiles 用户档案表（与 users 一对一） ----------
CREATE TABLE IF NOT EXISTS profiles (
  id                 CHAR(32)     NOT NULL PRIMARY KEY,
  user_id            CHAR(32)     NOT NULL COMMENT '关联 users.id',
  name               VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '姓名',
  gender             VARCHAR(10)  NULL COMMENT '性别',
  birth_date         DATE         NULL COMMENT '出生日期',
  phone              VARCHAR(20)  NULL,
  email              VARCHAR(255) NULL,
  location           VARCHAR(100) NULL COMMENT '所在地',
  political_status   VARCHAR(20)  NULL COMMENT '政治面貌',
  avatar_url         VARCHAR(500) NULL COMMENT '头像/证件照',
  summary            TEXT         NULL COMMENT '自我评价',
  custom_fields      JSON         NULL COMMENT '自定义字段 {字段名: 值}',
  completeness_score INT          NOT NULL DEFAULT 0 COMMENT '档案完整性评分 0-100',
  created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_profiles_user (user_id),
  CONSTRAINT fk_profiles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户档案：基础信息+自我评价';

-- ---------- 3. educations 教育经历 ----------
CREATE TABLE IF NOT EXISTS educations (
  id          CHAR(32)     NOT NULL PRIMARY KEY,
  profile_id  CHAR(32)     NOT NULL,
  school      VARCHAR(100) NOT NULL,
  major       VARCHAR(100) NULL,
  degree      VARCHAR(20)  NULL COMMENT '本科/硕士/博士',
  start_date  DATE         NULL,
  end_date    DATE         NULL,
  gpa         VARCHAR(20)  NULL,
  courses     JSON         NULL COMMENT '主修课程数组',
  custom_fields JSON       NULL COMMENT '自定义字段 {字段名: 值}',
  is_current  TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '在读中',
  order_index INT          NOT NULL DEFAULT 0 COMMENT '展示排序',
  visibility  TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '是否出现在简历',
  priority    INT          NOT NULL DEFAULT 0 COMMENT '定制简历优先级',
  KEY idx_educations_profile (profile_id),
  CONSTRAINT fk_educations_profile FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='教育经历';

-- ---------- 4. work_experiences 工作经历 ----------
CREATE TABLE IF NOT EXISTS work_experiences (
  id           CHAR(32)     NOT NULL PRIMARY KEY,
  profile_id   CHAR(32)     NOT NULL,
  company      VARCHAR(100) NOT NULL,
  position     VARCHAR(100) NULL,
  start_date   DATE         NULL,
  end_date     DATE         NULL,
  description  JSON         NULL COMMENT 'bullet points 数组',
  achievements JSON         NULL COMMENT '量化成果数组',
  custom_fields JSON        NULL COMMENT '自定义字段 {字段名: 值}',
  is_current   TINYINT(1)   NOT NULL DEFAULT 0,
  order_index  INT          NOT NULL DEFAULT 0,
  visibility   TINYINT(1)   NOT NULL DEFAULT 1,
  priority     INT          NOT NULL DEFAULT 0,
  KEY idx_work_profile (profile_id),
  CONSTRAINT fk_work_profile FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作经历';

-- ---------- 5. projects 项目经历 ----------
CREATE TABLE IF NOT EXISTS projects (
  id          CHAR(32)     NOT NULL PRIMARY KEY,
  profile_id  CHAR(32)     NOT NULL,
  name        VARCHAR(100) NOT NULL,
  role        VARCHAR(100) NULL,
  tech_stack  JSON         NULL COMMENT '技术栈数组',
  start_date  DATE         NULL,
  end_date    DATE         NULL,
  description JSON         NULL,
  highlights  JSON         NULL COMMENT '项目亮点',
  url         VARCHAR(500) NULL,
  custom_fields JSON       NULL COMMENT '自定义字段 {字段名: 值}',
  order_index INT          NOT NULL DEFAULT 0,
  visibility  TINYINT(1)   NOT NULL DEFAULT 1,
  priority    INT          NOT NULL DEFAULT 0,
  KEY idx_projects_profile (profile_id),
  CONSTRAINT fk_projects_profile FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目经历';

-- ---------- 6. skills 技能 ----------
CREATE TABLE IF NOT EXISTS skills (
  id          CHAR(32)    NOT NULL PRIMARY KEY,
  profile_id  CHAR(32)    NOT NULL,
  name        VARCHAR(50) NOT NULL,
  category    VARCHAR(50) NULL COMMENT '编程语言/框架/工具',
  proficiency INT         NULL COMMENT '熟练度 1-5',
  custom_fields JSON      NULL COMMENT '自定义字段 {字段名: 值}',
  order_index INT         NOT NULL DEFAULT 0,
  visibility  TINYINT(1)  NOT NULL DEFAULT 1,
  KEY idx_skills_profile (profile_id),
  CONSTRAINT fk_skills_profile FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
  CONSTRAINT chk_skills_proficiency CHECK (proficiency BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='技能表';

-- ---------- 7. certifications 证书 ----------
CREATE TABLE IF NOT EXISTS certifications (
  id            CHAR(32)     NOT NULL PRIMARY KEY,
  profile_id    CHAR(32)     NOT NULL,
  name          VARCHAR(100) NOT NULL,
  issuer        VARCHAR(100) NULL COMMENT '颁发机构',
  issue_date    DATE         NULL,
  expiry_date   DATE         NULL,
  credential_id VARCHAR(100) NULL COMMENT '证书编号',
  custom_fields JSON         NULL COMMENT '自定义字段 {字段名: 值}',
  order_index   INT          NOT NULL DEFAULT 0,
  visibility    TINYINT(1)   NOT NULL DEFAULT 1,
  KEY idx_certifications_profile (profile_id),
  CONSTRAINT fk_certifications_profile FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='证书表';

-- ---------- 8. family_members 家庭成员（报名表用） ----------
CREATE TABLE IF NOT EXISTS family_members (
  id           CHAR(32)     NOT NULL PRIMARY KEY,
  profile_id   CHAR(32)     NOT NULL,
  name         VARCHAR(50)  NOT NULL,
  relationship VARCHAR(20)  NULL COMMENT '父子/母子/配偶',
  work_unit    VARCHAR(100) NULL COMMENT '工作单位',
  position     VARCHAR(100) NULL COMMENT '职务',
  phone        VARCHAR(20)  NULL,
  custom_fields JSON        NULL COMMENT '自定义字段 {字段名: 值}',
  KEY idx_family_profile (profile_id),
  CONSTRAINT fk_family_profile FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='家庭成员';

-- ---------- 9. job_descriptions 岗位描述 ----------
CREATE TABLE IF NOT EXISTS job_descriptions (
  id             CHAR(32)     NOT NULL PRIMARY KEY,
  user_id        CHAR(32)     NOT NULL,
  company_name   VARCHAR(100) NULL,
  position_title VARCHAR(100) NULL,
  raw_text       TEXT         NOT NULL COMMENT '原始 JD 文本',
  parsed_data    JSON         NULL COMMENT 'AI 解析结果',
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_jd_user (user_id),
  CONSTRAINT fk_jd_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='岗位描述';

-- ---------- 10. resumes 简历版本 ----------
CREATE TABLE IF NOT EXISTS resumes (
  id            CHAR(32)     NOT NULL PRIMARY KEY,
  user_id       CHAR(32)     NOT NULL,
  jd_id         CHAR(32)     NULL COMMENT '可选关联 JD',
  version_name  VARCHAR(200) NOT NULL COMMENT '如：字节跳动_后端开发_20260716',
  resume_data   JSON         NOT NULL COMMENT '结构化简历内容',
  match_score   INT          NULL COMMENT '匹配度 0-100',
  highlights    JSON         NULL COMMENT '强匹配项',
  gaps          JSON         NULL COMMENT '弱匹配/缺失项',
  suggestions   JSON         NULL COMMENT 'AI 建议',
  html_template VARCHAR(50)  NOT NULL DEFAULT 'technical',
  pdf_path      VARCHAR(500) NULL,
  status        VARCHAR(20)  NOT NULL DEFAULT 'draft' COMMENT 'draft/pending/generated/exported/failed',
  error_message TEXT         NULL COMMENT '后台生成失败原因',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_resumes_user (user_id),
  KEY idx_resumes_jd (jd_id),
  KEY idx_resumes_status (status),
  CONSTRAINT fk_resumes_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_resumes_jd FOREIGN KEY (jd_id) REFERENCES job_descriptions(id) ON DELETE SET NULL,
  CONSTRAINT chk_resumes_status CHECK (status IN ('draft','pending','generated','exported','failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='简历版本';

-- ---------- 11. forms 报名表 ----------
CREATE TABLE IF NOT EXISTS forms (
  id                CHAR(32)     NOT NULL PRIMARY KEY,
  user_id           CHAR(32)     NOT NULL,
  original_filename VARCHAR(255) NOT NULL,
  file_path         VARCHAR(500) NOT NULL,
  file_type         VARCHAR(10)  NOT NULL COMMENT 'pdf/word/excel',
  form_structure    JSON         NULL COMMENT '解析出的字段结构',
  field_mapping     JSON         NULL COMMENT '字段映射关系',
  filled_data       JSON         NULL COMMENT '实际填充数据',
  status            VARCHAR(20)  NOT NULL DEFAULT 'uploaded',
  created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_forms_user (user_id),
  KEY idx_forms_status (status),
  CONSTRAINT fk_forms_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT chk_forms_type CHECK (file_type IN ('pdf','word','excel')),
  CONSTRAINT chk_forms_status CHECK (status IN ('uploaded','analyzed','mapped','filled'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='报名表：uploaded→analyzed→mapped→filled';

-- ---------- 12. applications 投递记录 ----------
CREATE TABLE IF NOT EXISTS applications (
  id             CHAR(32)     NOT NULL PRIMARY KEY,
  user_id        CHAR(32)     NOT NULL,
  resume_id      CHAR(32)     NULL,
  jd_id          CHAR(32)     NULL,
  company_name   VARCHAR(100) NOT NULL,
  position_title VARCHAR(100) NOT NULL,
  channel        VARCHAR(20)  NOT NULL DEFAULT 'website' COMMENT 'email/website/official',
  status         VARCHAR(20)  NOT NULL DEFAULT 'applied' COMMENT 'applied/viewed/interview/offer/rejected',
  applied_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '投递时间',
  notes          TEXT         NULL,
  follow_up_date DATE         NULL COMMENT '下次跟进日期',
  resume_snapshot     JSON         NULL COMMENT '投递时的 resume_data 快照（导出形态）',
  snapshot_template   VARCHAR(50)  NULL COMMENT '投递时使用的模板',
  snapshot_pdf_path   VARCHAR(500) NULL COMMENT '投递时 PDF 副本路径',
  snapshot_match_score INT         NULL COMMENT '投递时匹配分',
  jd_snapshot         JSON         NULL COMMENT '投递时 JD 原文+解析结果',
  KEY idx_app_user (user_id),
  KEY idx_app_status (status),
  KEY idx_app_follow_up (follow_up_date),
  KEY idx_app_applied_at (applied_at),
  KEY idx_app_resume (resume_id),
  KEY idx_app_jd (jd_id),
  CONSTRAINT fk_app_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_app_resume FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE SET NULL,
  CONSTRAINT fk_app_jd FOREIGN KEY (jd_id) REFERENCES job_descriptions(id) ON DELETE SET NULL,
  CONSTRAINT chk_app_channel CHECK (channel IN ('email','website','official')),
  CONSTRAINT chk_app_status CHECK (status IN ('applied','viewed','interview','offer','rejected'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='投递记录';

-- ---------- 13. system_config 系统运行时配置（优先级高于 .env） ----------
CREATE TABLE IF NOT EXISTS system_config (
  `key`      VARCHAR(100) NOT NULL PRIMARY KEY COMMENT '配置键，如 KIMI_API_KEY',
  `value`    TEXT         NULL COMMENT '配置值',
  updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统运行时配置';

-- ---------- 14. profile_blocks 自定义信息块 ----------
CREATE TABLE IF NOT EXISTS profile_blocks (
  id          CHAR(32)    NOT NULL PRIMARY KEY,
  profile_id  CHAR(32)    NOT NULL,
  name        VARCHAR(50) NOT NULL COMMENT '块名称，如 父母信息',
  fields      JSON        NOT NULL COMMENT '字段定义 [{name, label, type}]',
  order_index INT         NOT NULL DEFAULT 0,
  created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_blocks_profile (profile_id),
  CONSTRAINT fk_blocks_profile FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自定义信息块';

-- ---------- 15. profile_block_entries 信息块记录 ----------
CREATE TABLE IF NOT EXISTS profile_block_entries (
  id          CHAR(32) NOT NULL PRIMARY KEY,
  block_id    CHAR(32) NOT NULL,
  data        JSON     NOT NULL COMMENT '记录值 {字段名: 值}',
  order_index INT      NOT NULL DEFAULT 0,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_entries_block (block_id),
  CONSTRAINT fk_entries_block FOREIGN KEY (block_id) REFERENCES profile_blocks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自定义信息块记录';

-- ---------- 16. interview_preps 面试准备（一份简历一条） ----------
CREATE TABLE IF NOT EXISTS interview_preps (
  id         CHAR(32) NOT NULL PRIMARY KEY,
  resume_id  CHAR(32) NOT NULL,
  research   JSON     NOT NULL COMMENT '岗位调研',
  outline    JSON     NOT NULL COMMENT '面试提纲',
  questions  JSON     NOT NULL COMMENT '题库 [{type, question, reference_answer, key_points}]',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_prep_resume (resume_id),
  CONSTRAINT fk_prep_resume FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='简历面试准备（调研/提纲/题库）';

-- ---------- 17. custom_field_defs 档案版块自定义字段定义 ----------
CREATE TABLE IF NOT EXISTS custom_field_defs (
  id          CHAR(32)    NOT NULL PRIMARY KEY,
  profile_id  CHAR(32)    NOT NULL,
  section     VARCHAR(30) NOT NULL COMMENT 'basic/educations/work-experiences/projects/skills/certifications/family-members',
  name        VARCHAR(50) NOT NULL COMMENT '字段键（英文）',
  label       VARCHAR(50) NOT NULL COMMENT '显示名',
  type        VARCHAR(20) NOT NULL DEFAULT 'text' COMMENT 'text/number/date/textarea',
  order_index INT         NOT NULL DEFAULT 0,
  created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_field_def (profile_id, section, name),
  KEY idx_field_defs_profile (profile_id),
  CONSTRAINT fk_field_defs_profile FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='档案版块自定义字段定义';

-- ---------- 18. photos 用户照片库 ----------
CREATE TABLE IF NOT EXISTS photos (
  id                CHAR(32)     NOT NULL PRIMARY KEY,
  user_id           CHAR(32)     NOT NULL,
  category          VARCHAR(30)  NOT NULL DEFAULT 'other' COMMENT 'work 工作 / life 生活 / other 其他',
  original_filename VARCHAR(255) NOT NULL,
  stored_path       VARCHAR(500) NOT NULL COMMENT '服务器存储路径（UUID 化）',
  mime_type         VARCHAR(100) NULL,
  size              BIGINT       NULL COMMENT '字节',
  created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_photos_user (user_id),
  KEY idx_photos_category (category),
  CONSTRAINT fk_photos_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户照片库（工作照/生活照）';

-- ---------- 19. resume_versions 简历内容版本快照 ----------
CREATE TABLE IF NOT EXISTS resume_versions (
  id          CHAR(32)    NOT NULL PRIMARY KEY,
  resume_id   CHAR(32)    NOT NULL,
  version_no  INT         NOT NULL COMMENT '每份简历内从 1 递增',
  label       VARCHAR(30) NOT NULL COMMENT 'ai_generated/user_edit/enhancement_applied/rollback',
  resume_data JSON        NOT NULL,
  match_score INT         NULL,
  created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_rv_resume (resume_id),
  CONSTRAINT fk_rv_resume FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='简历内容版本快照（编辑/回滚/diff 用）';

SET FOREIGN_KEY_CHECKS = 1;
