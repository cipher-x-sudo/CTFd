"""Add hostname column to container_info_model for Railway backend

Revision ID: a1b2c3d4e5f6
Revises: 67ebab6de598
Create Date: 2025-02-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "67ebab6de598"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    result = conn.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'container_info_model')"
        )
    )
    table_exists = result.scalar()

    if not table_exists:
        op.create_table(
            "container_info_model",
            sa.Column("container_id", sa.String(512), primary_key=True),
            sa.Column(
                "challenge_id",
                sa.Integer,
                sa.ForeignKey("challenges.id", ondelete="CASCADE"),
            ),
            sa.Column(
                "team_id",
                sa.Integer,
                sa.ForeignKey("teams.id", ondelete="CASCADE"),
            ),
            sa.Column(
                "user_id",
                sa.Integer,
                sa.ForeignKey("users.id", ondelete="CASCADE"),
            ),
            sa.Column("port", sa.Integer),
            sa.Column("hostname", sa.Text(), nullable=True),
            sa.Column("ssh_username", sa.Text(), nullable=True),
            sa.Column("ssh_password", sa.Text(), nullable=True),
            sa.Column("timestamp", sa.Integer),
            sa.Column("expires", sa.Integer),
        )
    else:
        conn.execute(
            text(
                "ALTER TABLE container_info_model "
                "ADD COLUMN IF NOT EXISTS hostname TEXT"
            )
        )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        text(
            "ALTER TABLE container_info_model "
            "DROP COLUMN IF EXISTS hostname"
        )
    )
