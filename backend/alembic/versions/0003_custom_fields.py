"""add custom_fields columns and custom_field_defs table

档案七大版块支持自定义字段：固定列不动，各表追加 custom_fields JSON，
新增 custom_field_defs 存用户字段定义。幂等：已存在则跳过。

Revision ID: 0003_custom_fields
Revises: 0002_interview_preps
Create Date: 2026-08-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_custom_fields"
down_revision = "0002_interview_preps"
branch_labels = None
depends_on = None

_TABLES = [
    "profiles", "educations", "work_experiences", "projects",
    "skills", "certifications", "family_members",
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table in _TABLES:
        if table not in tables:
            continue
        cols = {c["name"] for c in inspector.get_columns(table)}
        if "custom_fields" not in cols:
            op.execute(f"ALTER TABLE {table} ADD COLUMN custom_fields JSON NULL COMMENT '自定义字段'")
        # 存量行回填空对象，避免读取时为 NULL
        op.execute(f"UPDATE {table} SET custom_fields = JSON_OBJECT() WHERE custom_fields IS NULL")

    if "custom_field_defs" not in tables:
        op.create_table(
            "custom_field_defs",
            sa.Column("id", sa.CHAR(length=32), primary_key=True),
            sa.Column("profile_id", sa.CHAR(length=32), nullable=False),
            sa.Column("section", sa.String(length=30), nullable=False,
                      comment="basic/educations/work-experiences/projects/skills/certifications/family-members"),
            sa.Column("name", sa.String(length=50), nullable=False, comment="字段键（英文）"),
            sa.Column("label", sa.String(length=50), nullable=False, comment="显示名"),
            sa.Column("type", sa.String(length=20), nullable=False, server_default=sa.text("'text'")),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("profile_id", "section", "name", name="uk_field_def"),
            sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            comment="档案版块自定义字段定义",
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS custom_field_defs")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} DROP COLUMN custom_fields")
