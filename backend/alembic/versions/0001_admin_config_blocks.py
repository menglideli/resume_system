"""add admin role, system_config and custom profile blocks

首个迁移版本：为已用 sql/init.sql 初始化过的库补齐新增结构（幂等）。
新库由 init.sql 直接建表，本迁移检测到已存在则跳过。

Revision ID: 0001_admin_config_blocks
Revises:
Create Date: 2026-08-25
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_admin_config_blocks"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Python 侧检查已存在的结构，避免对 init.sql 已建好的新库重复执行
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # users.is_admin（管理员标记）
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "is_admin" not in user_cols:
        op.execute(
            "ALTER TABLE users ADD COLUMN is_admin TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否管理员'"
        )

    # system_config（运行时配置：Kimi API 等）
    if "system_config" not in tables:
        op.create_table(
            "system_config",
            sa.Column("key", sa.String(length=100), primary_key=True, comment="配置键，如 KIMI_API_KEY"),
            sa.Column("value", sa.Text(), nullable=True, comment="配置值"),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            ),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            comment="系统运行时配置",
        )

    # profile_blocks（自定义信息块：块名 + 字段定义）
    if "profile_blocks" not in tables:
        op.create_table(
            "profile_blocks",
            sa.Column("id", sa.CHAR(length=32), primary_key=True),
            sa.Column("profile_id", sa.CHAR(length=32), nullable=False),
            sa.Column("name", sa.String(length=50), nullable=False, comment="块名称，如 父母信息"),
            sa.Column("fields", sa.JSON(), nullable=False, comment="字段定义 [{name, label, type}]"),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            comment="自定义信息块",
        )

    # profile_block_entries（信息块记录：data 为 {字段名: 值}）
    if "profile_block_entries" not in tables:
        op.create_table(
            "profile_block_entries",
            sa.Column("id", sa.CHAR(length=32), primary_key=True),
            sa.Column("block_id", sa.CHAR(length=32), nullable=False),
            sa.Column("data", sa.JSON(), nullable=False, comment="记录值 {字段名: 值}"),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["block_id"], ["profile_blocks.id"], ondelete="CASCADE"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            comment="自定义信息块记录",
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS profile_block_entries")
    op.execute("DROP TABLE IF EXISTS profile_blocks")
    op.execute("DROP TABLE IF EXISTS system_config")
    op.execute("ALTER TABLE users DROP COLUMN is_admin")
