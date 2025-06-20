"""Add original filename and business model support

Revision ID: cc069f456bb2
Revises: d196ad3a3192
Create Date: 2025-06-15 08:38:53.823660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc069f456bb2'
down_revision: Union[str, None] = 'd196ad3a3192'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('cpe_records', sa.Column('original_filename', sa.String(), nullable=True))
    op.add_column('cpe_records', sa.Column('is_stored', sa.Boolean(), nullable=True))
    op.add_column('cpe_records', sa.Column('storage_tier', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('cpe_records', 'storage_tier')
    op.drop_column('cpe_records', 'is_stored')
    op.drop_column('cpe_records', 'original_filename')
    # ### end Alembic commands ###
