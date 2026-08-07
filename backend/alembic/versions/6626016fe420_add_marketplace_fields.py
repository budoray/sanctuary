"""add_marketplace_fields

Revision ID: 6626016fe420
Revises: e227f9204261
Create Date: 2026-08-07 17:35:54.348000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6626016fe420'
down_revision: Union[str, Sequence[str], None] = 'e227f9204261'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Adventures
    op.add_column('adventures', sa.Column('status', sa.String(), nullable=False, server_default='draft'))
    op.add_column('adventures', sa.Column('visibility', sa.String(), nullable=False, server_default='private'))
    op.add_column('adventures', sa.Column('rating_sum', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('adventures', sa.Column('rating_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('adventures', sa.Column('download_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('adventures', sa.Column('tags', sa.Text(), nullable=False, server_default='[]'))
    op.add_column('adventures', sa.Column('parent_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_adventures_parent_id'), 'adventures', ['parent_id'], unique=False)

    # Rulesets
    op.add_column('rulesets', sa.Column('status', sa.String(), nullable=False, server_default='draft'))
    op.add_column('rulesets', sa.Column('visibility', sa.String(), nullable=False, server_default='private'))
    op.add_column('rulesets', sa.Column('rating_sum', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('rulesets', sa.Column('rating_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('rulesets', sa.Column('download_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('rulesets', sa.Column('tags', sa.Text(), nullable=False, server_default='[]'))
    op.add_column('rulesets', sa.Column('parent_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_rulesets_parent_id'), 'rulesets', ['parent_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_rulesets_parent_id'), table_name='rulesets')
    op.drop_column('rulesets', 'parent_id')
    op.drop_column('rulesets', 'tags')
    op.drop_column('rulesets', 'download_count')
    op.drop_column('rulesets', 'rating_count')
    op.drop_column('rulesets', 'rating_sum')
    op.drop_column('rulesets', 'visibility')
    op.drop_column('rulesets', 'status')

    op.drop_index(op.f('ix_adventures_parent_id'), table_name='adventures')
    op.drop_column('adventures', 'parent_id')
    op.drop_column('adventures', 'tags')
    op.drop_column('adventures', 'download_count')
    op.drop_column('adventures', 'rating_count')
    op.drop_column('adventures', 'rating_sum')
    op.drop_column('adventures', 'visibility')
    op.drop_column('adventures', 'status')
