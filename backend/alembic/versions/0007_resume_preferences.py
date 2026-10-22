"""resume generation preferences

生成参数（模板/页数/语言/目标职级/侧重方向）落库，让重试能用同一套参数重跑。
在此之前 preferences 只活在请求体里，重试时传的是 {}，
用户重试拿到的简历和当初选的（比如 management 模板 / 2 页）完全不是一回事。
存量行填 NULL，retry 时回退到 {}（与旧行为一致，不会让老任务报错）。幂等。

Revision ID: 0007_resume_preferences
Revises: 0006_interview_prep_bg
Create Date: 2026-09-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0007_resume_preferences"
down_revision = "0006_interview_prep_bg"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("resumes")}
    if "preferences" not in cols:
        op.add_column(
            "resumes",
            sa.Column("preferences", sa.JSON(), nullable=True,
                      comment="生成参数快照，供重试复用"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("resumes")}
    if "preferences" in cols:
        op.drop_column("resumes", "preferences")
