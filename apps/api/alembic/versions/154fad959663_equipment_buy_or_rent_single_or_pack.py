"""equipment buy or rent, single or pack

Revision ID: 154fad959663
Revises: b43913998fa3
Create Date: 2026-08-07 21:44:22.958186

An add-on can now be rented, bought, or both, and sold loose or by the pack.
Previously `rental_price` was the only price and `consumable` decided, as a UI
hint, whether the item came back.

Backfilled so nothing changes price or availability on the way through:

  * for_rent  -> true for every existing row. Selections default to renting, so
    flipping any row to sale-only here would make the current booking flow start
    rejecting kit it accepted yesterday.
  * for_sale  -> true where `consumable`, since those are the ones already being
    sold and gone; sale_price copies rental_price, which is the number they were
    actually charged at.
  * pack_size -> 1 (no packs configured until someone sets one up).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '154fad959663'
down_revision: Union[str, None] = 'b43913998fa3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default on every one: these are NOT NULL and the table already has
    # rows, so without it the ALTER fails outright.
    op.add_column(
        'equipment',
        sa.Column('sale_price', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    )
    op.add_column(
        'equipment',
        sa.Column('for_rent', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    )
    op.add_column(
        'equipment',
        sa.Column('for_sale', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.add_column(
        'equipment',
        sa.Column('pack_size', sa.Integer(), server_default='1', nullable=False),
    )
    op.add_column(
        'equipment',
        sa.Column('pack_price', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    )

    # Carry the old single-price, consumable-means-sold model forward.
    #
    # The FORCE has to come off first. Migrations run as the table owner, and FORCE
    # ROW LEVEL SECURITY subjects even the owner to the tenant policy — with no
    # `app.current_tenant` set, this UPDATE matches zero rows across every tenant
    # and reports success. Any data migration in this codebase has to do this, or
    # be silently a no-op.
    op.execute("ALTER TABLE equipment NO FORCE ROW LEVEL SECURITY")
    op.execute(
        "UPDATE equipment SET for_sale = true, sale_price = rental_price WHERE consumable"
    )
    op.execute("ALTER TABLE equipment FORCE ROW LEVEL SECURITY")

    op.create_check_constraint('pack_size_at_least_one', 'equipment', 'pack_size >= 1')


def downgrade() -> None:
    op.drop_constraint('pack_size_at_least_one', 'equipment', type_='check')
    op.drop_column('equipment', 'pack_price')
    op.drop_column('equipment', 'pack_size')
    op.drop_column('equipment', 'for_sale')
    op.drop_column('equipment', 'for_rent')
    op.drop_column('equipment', 'sale_price')
