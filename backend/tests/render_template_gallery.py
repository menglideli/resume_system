"""Render the four production resume styles for visual QA."""
import asyncio
from pathlib import Path

from app.services.resume_renderer import resume_renderer

SAMPLE_RESUME = {
    "header": {"name": "张明远", "title": "高级后端开发工程师",
               "contact": {"phone": "13800001111", "email": "mingyuan@example.com", "location": "上海"}},
    "sections": [
        {"type": "summary", "title": "个人总结", "content":
         "6 年后端与云原生平台建设经验，聚焦高并发服务、可观测性与交付效率。具备从需求拆解、架构设计到上线治理的完整实践，能够跨团队推动核心系统稳定性和研发效能提升。"},
        {"type": "skills", "title": "专业技能", "items": [
            {"name": "Python", "category": "编程语言", "level": "精通", "relevance": 10}, {"name": "Go", "category": "编程语言", "level": "熟练", "relevance": 9},
            {"name": "MySQL", "category": "数据存储", "level": "熟练", "relevance": 9}, {"name": "Redis", "category": "数据存储", "level": "熟练", "relevance": 9},
            {"name": "Docker", "category": "云原生", "level": "熟练", "relevance": 8}, {"name": "Kubernetes", "category": "云原生", "level": "熟悉", "relevance": 8},
            {"name": "FastAPI", "category": "后端框架", "level": "精通", "relevance": 8}, {"name": "Kafka", "category": "消息中间件", "level": "熟悉", "relevance": 7},
        ]},
        {"type": "experience", "title": "工作经历", "items": [
            {"company": "星河科技有限公司", "position": "高级后端工程师", "period": "2022.04 - 至今", "relevance": 10,
             "bullets": ["负责订单与履约平台架构演进，拆分核心服务并建立容量评估机制，支撑业务高峰稳定运行。", "推进查询链路和缓存策略优化，将核心接口平均响应时间降低 42%。", "建立代码评审、灰度发布与故障复盘规范，带领 4 人小组持续交付。"]},
            {"company": "云帆信息技术有限公司", "position": "后端开发工程师", "period": "2019.07 - 2022.03", "relevance": 8,
             "bullets": ["参与企业数据平台建设，完成任务调度、权限控制和审计模块开发。", "改造持续集成流程，将常规版本发布时间由 2 小时缩短至 25 分钟。"]},
        ]},
        {"type": "projects", "title": "项目经历", "items": [
            {"name": "统一交付与可观测平台", "role": "核心负责人", "period": "2023.03 - 2024.02", "relevance": 10,
             "tech_stack": ["Go", "Kubernetes", "Prometheus", "Grafana"],
             "bullets": ["设计部署编排和运行指标采集能力，覆盖 30 余个业务服务。", "统一告警分级与值班流程，使关键故障平均定位时间降低 35%。"]},
            {"name": "高并发订单服务", "role": "核心开发", "period": "2022.06 - 2023.02", "relevance": 9,
             "tech_stack": ["Python", "FastAPI", "MySQL", "Redis"],
             "bullets": ["负责幂等、库存一致性和热点数据缓存方案，保障峰值流量下稳定处理。"]},
        ]},
        {"type": "education", "title": "教育经历", "items": [
            {"school": "华东理工大学", "major": "计算机科学与技术", "degree": "本科", "period": "2015.09 - 2019.06"}
        ]},
        {"type": "certifications", "title": "证书与奖项", "items": [
            {"name": "云原生技术认证", "issuer": "示例认证机构", "date": "2024.03"},
            {"name": "年度优秀项目奖", "issuer": "星河科技", "date": "2023.12"},
        ]},
    ],
}


async def main() -> None:
    output_dir = Path("storage/template_gallery")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("default", "technical", "management", "compact"):
        html_path = output_dir / f"resume_{name}.html"
        pdf_path = output_dir / f"resume_{name}.pdf"
        html_path.write_text(resume_renderer.render_to_html(SAMPLE_RESUME, name), encoding="utf-8")
        await resume_renderer.render_to_pdf(SAMPLE_RESUME, name, str(pdf_path), page_limit=1)
        print(f"{name}: {pdf_path.stat().st_size} bytes")


if __name__ == "__main__":
    asyncio.run(main())
