"""Add log_type column to app_services table."""

from alembic import op
import sqlalchemy as sa


def upgrade():
    # 添加 log_type 字段
    op.add_column(
        'app_services',
        sa.Column('log_type', sa.String(length=50), nullable=True, comment='日志类型: HOST_DIR/DOCKER_LOGS')
    )


def downgrade():
    # 删除 log_type 字段
    op.drop_column('app_services', 'log_type')
