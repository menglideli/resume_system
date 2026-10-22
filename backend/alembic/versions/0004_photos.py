"""add photos table

用户照片库（工作照 / 生活照等分类）。幂等：已存在则跳过。

Revision ID: 0004_photos
Revises: 0003_custom_fields
Create Date: 2026-08-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_photos"
down_revision = "0003_custom_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "photos" in set(inspector.get_table_names()):
        return
    op.create_table(
        "photos",
        sa.Column("id", sa.CHAR(length=32), primary_key=True),
        sa.Column("user_id", sa.CHAR(length=32), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False, server_default=sa.text("'other'"),
                  comment="work 工作 / life 生活 / other 其他"),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=False, comment="服务器存储路径"),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("size", sa.BigInteger(), nullable=True, comment="字节"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.Index("ix_photos_user_id", "user_id"),
        sa.Index("ix_photos_category", "category"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        comment="用户照片库",
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS photos")
