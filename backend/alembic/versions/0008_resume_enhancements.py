"""resume enhancements (AI 候选补强项目，待用户逐条确认后才进简历)

生成简历时，AI 会额外给出「JD 要求但档案里找不到对应经历」的候选项目。
这些内容是推测草稿，不能直接进 resume_data —— 否则就是替用户编造履历。
单独存一列，由用户勾选后再合并。存量行填 NULL，前端按空数组处理。幂等。

Revision ID: 0008_resume_enhancements
Revises: 0007_resume_preferences
Create Date: 2026-09-02
"""
import sqlalchemy as sa
from alembic import op

revision = "0008_resume_enhancements"
down_revision = "0007_resume_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("resumes")}
    if "enhancements" not in cols:
        op.add_column(
            "resumes",
            sa.Column("enhancements", sa.JSON(), nullable=True,
                      comment="AI 候选补强项目，需用户确认后才合并进简历"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("resumes")}
    if "enhancements" in cols:
        op.drop_column("resumes", "enhancements")
