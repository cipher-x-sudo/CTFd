"""Add hostname column to container_info_model for Railway backend

Revision ID: a1b2c3d4e5f6
Revises: 67ebab6de598
Create Date: 2025-02-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "67ebab6de598"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "container_info_model",
        sa.Column("hostname", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("container_info_model", "hostname")
