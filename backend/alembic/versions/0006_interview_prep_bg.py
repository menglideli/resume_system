"""interview prep background generation

面试准备改后台任务：interview_preps 新增 status / error_message 列。
存量数据默认 'generated'（数据已完整），保证升级后历史记录照常可见。幂等。

Revision ID: 0006_interview_prep_bg
Revises: 0005_resume_bg_task
Create Date: 2026-09-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0006_interview_prep_bg"
down_revision = "0005_resume_bg_task"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("interview_preps")}

    if "status" not in cols:
        op.add_column(
            "interview_preps",
            sa.Column(
                "status", sa.String(20), nullable=False,
                server_default="generated",
                comment="pending/generated/failed",
            ),
        )
    if "error_message" not in cols:
        op.add_column(
            "interview_preps",
            sa.Column("error_message", sa.Text(), nullable=True, comment="后台生成失败原因"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("interview_preps")}
    with op.batch_alter_table("interview_preps") as batch:
        if "error_message" in cols:
            batch.drop_column("error_message")
        if "status" in cols:
            batch.drop_column("status")
