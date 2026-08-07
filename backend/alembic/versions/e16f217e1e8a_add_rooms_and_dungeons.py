"""add rooms and dungeons

Revision ID: e16f217e1e8a
Revises: ad67a401d5f9
Create Date: 2026-08-07 01:08:09.505694

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e16f217e1e8a'
down_revision: Union[str, Sequence[str], None] = 'ad67a401d5f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rooms",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("theme", sa.String(), nullable=True),
        sa.Column("tiles", sa.Text(), nullable=True),
        sa.Column("entities", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rooms_account_id", "rooms", ["account_id"], unique=False)

    op.create_table(
        "dungeons",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("ruleset_id", sa.String(), nullable=True),
        sa.Column("public", sa.Integer(), nullable=True),
        sa.Column("room_order", sa.Text(), nullable=True),
        sa.Column("links", sa.Text(), nullable=True),
        sa.Column("start_room_id", sa.String(), nullable=True),
        sa.Column("start_x", sa.Integer(), nullable=True),
        sa.Column("start_y", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dungeons_account_id", "dungeons", ["account_id"], unique=False)

    op.add_column("sessions", sa.Column("dungeon_id", sa.String(), nullable=True))
    op.create_index("ix_sessions_dungeon_id", "sessions", ["dungeon_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_sessions_dungeon_id", table_name="sessions")
    op.drop_column("sessions", "dungeon_id")

    op.drop_index("ix_dungeons_account_id", table_name="dungeons")
    op.drop_table("dungeons")

    op.drop_index("ix_rooms_account_id", table_name="rooms")
    op.drop_table("rooms")
