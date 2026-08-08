"""add campaign journey fields

Revision ID: f3a7c2d1e8b9
Revises: ad67a401d5f9
Create Date: 2026-08-08 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a7c2d1e8b9'
down_revision: Union[str, Sequence[str], None] = '6626016fe420'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('quests', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('reputation', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('journey_notes', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_column('journey_notes')
        batch_op.drop_column('reputation')
        batch_op.drop_column('quests')
