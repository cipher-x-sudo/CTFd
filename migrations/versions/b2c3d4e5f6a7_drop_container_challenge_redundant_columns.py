"""Drop redundant initial/minimum/decay from container_challenge_model

These columns are defined on the parent challenges table; the container plugin
model no longer re-declares them to fix SQLAlchemy implicit-combination warnings.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-02-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _container_challenge_table_exists(conn):
    dialect = conn.dialect.name
    if dialect == "postgresql":
        result = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'container_challenge_model')"
            )
        )
        return result.scalar()
    if dialect == "sqlite":
        result = conn.execute(
            text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'table' AND name = 'container_challenge_model'"
            )
        )
        return result.fetchone() is not None
    if dialect in ("mysql", "mariadb"):
        result = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'container_challenge_model'"
            )
        )
        return result.fetchone() is not None
    return False


def _column_exists(conn, table, column):
    dialect = conn.dialect.name
    if dialect == "postgresql":
        result = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c)"
            ),
            {"t": table, "c": column},
        )
        return result.scalar()
    if dialect == "sqlite":
        result = conn.execute(text("PRAGMA table_info(container_challenge_model)"))
        return any(row[1] == column for row in result.fetchall())
    if dialect in ("mysql", "mariadb"):
        result = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        )
        return result.fetchone() is not None
    return False


def upgrade():
    conn = op.get_bind()
    if not _container_challenge_table_exists(conn):
        return
    for col in ("initial", "minimum", "decay"):
        if _column_exists(conn, "container_challenge_model", col):
            if conn.dialect.name == "postgresql":
                conn.execute(
                    text("ALTER TABLE container_challenge_model DROP COLUMN IF EXISTS " + col)
                )
            elif conn.dialect.name == "sqlite":
                conn.execute(text("ALTER TABLE container_challenge_model DROP COLUMN " + col))
            elif conn.dialect.name in ("mysql", "mariadb"):
                conn.execute(text("ALTER TABLE container_challenge_model DROP COLUMN " + col))


def downgrade():
    conn = op.get_bind()
    if not _container_challenge_table_exists(conn):
        return
    for col in ("initial", "minimum", "decay"):
        if not _column_exists(conn, "container_challenge_model", col):
            op.add_column(
                "container_challenge_model",
                sa.Column(col, sa.Integer(), nullable=True),
            )
