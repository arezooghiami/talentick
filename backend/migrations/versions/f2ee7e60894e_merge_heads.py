"""merge heads

Revision ID: f2ee7e60894e
Revises: 27283e91d2f8, c4b8f2a6d9e1
Create Date: 2026-07-14 10:02:14.730469+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2ee7e60894e'
down_revision: Union[str, Sequence[str], None] = ('27283e91d2f8', 'c4b8f2a6d9e1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
