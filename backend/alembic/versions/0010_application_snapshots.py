"""application snapshot columns (lock what the recruiter actually received)

Resumes keep evolving after an application is submitted; without a snapshot,
looking back later shows the *current* resume, not the submitted one.
Existing rows stay NULL. Defensive and idempotent.

Revision ID: 0010_application_snapshots
Revises: 0009_resume_versions
Create Date: 2026-09-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0010_application_snapshots"
down_revision = "0009_resume_versions"
branch_labels = None
depends_on = None

COLUMNS = {
    "resume_snapshot": sa.Column("resume_snapshot", sa.JSON(), nullable=True,
                                 comment="resume_data at application time (exportable form)"),
    "snapshot_template": sa.Column("snapshot_template", sa.String(50), nullable=True),
    "snapshot_pdf_path": sa.Column("snapshot_pdf_path", sa.String(500), nullable=True),
    "snapshot_match_score": sa.Column("snapshot_match_score", sa.Integer(), nullable=True),
    "jd_snapshot": sa.Column("jd_snapshot", sa.JSON(), nullable=True,
                             comment="JD raw_text + parsed_data at application time"),
}


def upgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("applications")}
    for name, column in COLUMNS.items():
        if name not in existing:
            op.add_column("applications", column)


def downgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("applications")}
    for name in COLUMNS:
        if name in existing:
            op.drop_column("applications", name)
