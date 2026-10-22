"""add interview_preps table

为每份简历持久化 AI 生成的面试准备（岗位调研/面试提纲/题库）。
沿用 0001 的 Python 侧幂等写法：已存在则跳过。

Revision ID: 0002_interview_preps
Revises: 0001_admin_config_blocks
Create Date: 2026-08-25
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_interview_preps"
down_revision = "0001_admin_config_blocks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "interview_preps" in inspector.get_table_names():
        return
    op.create_table(
        "interview_preps",
        sa.Column("id", sa.CHAR(length=32), primary_key=True),
        sa.Column("resume_id", sa.CHAR(length=32), nullable=False, unique=True),
        sa.Column("research", sa.JSON(), nullable=False, comment="岗位调研"),
        sa.Column("outline", sa.JSON(), nullable=False, comment="面试提纲"),
        sa.Column("questions", sa.JSON(), nullable=False, comment="题库 [{type, question, reference_answer, key_points}]"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        comment="简历面试准备（调研/提纲/题库）",
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS interview_preps")
