"""add room width height

Revision ID: d0e4deeb3778
Revises: e16f217e1e8a
Create Date: 2026-08-07 01:29:46.324325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0e4deeb3778'
down_revision: Union[str, Sequence[str], None] = 'e16f217e1e8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("rooms", sa.Column("width", sa.Integer(), nullable=True))
    op.add_column("rooms", sa.Column("height", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("rooms", "height")
    op.drop_column("rooms", "width")
