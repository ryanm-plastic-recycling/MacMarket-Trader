"""initial schema"""

from alembic import op
import sqlalchemy as sa

revision = "20260331_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from macmarket_trader.domain.models import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    from macmarket_trader.domain.models import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind)
