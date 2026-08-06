"""add events and friends tables

Revision ID: 85d1d9e58b47
Revises: ec604bad1607
Create Date: 2026-08-06 14:33:40.947334

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85d1d9e58b47'
down_revision: Union[str, Sequence[str], None] = 'ec604bad1607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_events_account_id'), 'events', ['account_id'], unique=False)
    op.create_index(op.f('ix_events_event_type'), 'events', ['event_type'], unique=False)
    op.create_index(op.f('ix_events_session_id'), 'events', ['session_id'], unique=False)

    op.create_table(
        'friends',
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('friend_account_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('account_id', 'friend_account_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('friends')
    op.drop_index(op.f('ix_events_session_id'), table_name='events')
    op.drop_index(op.f('ix_events_event_type'), table_name='events')
    op.drop_index(op.f('ix_events_account_id'), table_name='events')
    op.drop_table('events')
