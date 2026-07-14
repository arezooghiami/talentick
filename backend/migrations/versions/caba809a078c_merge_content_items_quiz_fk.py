"""merge content_items_quiz_fk

Revision ID: caba809a078c
Revises: f2ee7e60894e, d1e5a7c3b9f2
Create Date: 2026-07-14 10:56:52.660679+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'caba809a078c'
down_revision: Union[str, Sequence[str], None] = ('f2ee7e60894e', 'd1e5a7c3b9f2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
