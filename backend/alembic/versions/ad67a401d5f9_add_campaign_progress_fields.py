"""add campaign progress fields

Revision ID: ad67a401d5f9
Revises: 85d1d9e58b47
Create Date: 2026-08-06 16:30:48.117315

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad67a401d5f9'
down_revision: Union[str, Sequence[str], None] = '85d1d9e58b47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cleared_module_ids', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('current_module_index', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_column('current_module_index')
        batch_op.drop_column('cleared_module_ids')
