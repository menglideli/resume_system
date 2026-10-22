"""resume_versions (content history snapshots for editor / diff / rollback)

Every content change (AI generation, user edit, enhancement apply, rollback)
appends one row; resumes.resume_data always equals the latest version.
Defensive and idempotent: skips when the table already exists (init.sql).

Revision ID: 0009_resume_versions
Revises: 0008_resume_enhancements
Create Date: 2026-09-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0009_resume_versions"
down_revision = "0008_resume_enhancements"
branch_labels = None
depends_on = None

TABLE = "resume_versions"


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("resume_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(30), nullable=False),
        sa.Column("resume_data", sa.JSON(), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE in sa.inspect(bind).get_table_names():
        op.drop_table(TABLE)
