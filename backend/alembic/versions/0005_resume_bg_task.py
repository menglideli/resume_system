"""resume background generation

简历生成改后台任务：新增 error_message 列；放宽 status CHECK 约束（pending/failed）。幂等。

Revision ID: 0005_resume_bg_task
Revises: 0004_photos
Create Date: 2026-08-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0005_resume_bg_task"
down_revision = "0004_photos"
branch_labels = None
depends_on = None

_NEW_CHECK = (
    "ALTER TABLE resumes ADD CONSTRAINT chk_resumes_status "
    "CHECK (status IN ('draft','pending','generated','exported','failed'))"
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cols = {c["name"] for c in inspector.get_columns("resumes")}
    if "error_message" not in cols:
        op.add_column(
            "resumes",
            sa.Column("error_message", sa.Text(), nullable=True, comment="后台生成失败原因"),
        )

    checks = {c.get("name") for c in inspector.get_check_constraints("resumes")}
    if "chk_resumes_status" in checks:
        op.execute("ALTER TABLE resumes DROP CHECK chk_resumes_status")
        op.execute(_NEW_CHECK)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    checks = {c.get("name") for c in inspector.get_check_constraints("resumes")}
    if "chk_resumes_status" in checks:
        op.execute("ALTER TABLE resumes DROP CHECK chk_resumes_status")
        op.execute(
            "ALTER TABLE resumes ADD CONSTRAINT chk_resumes_status "
            "CHECK (status IN ('draft','generated','exported'))"
        )
    with op.batch_alter_table("resumes") as batch:
        batch.drop_column("error_message")
