"""integration partner gateway

The externalisation gateway: third-party platforms (Playo, Hudle) read availability
and claim slots under a revocable identity, so a court is never sold twice.

Two pieces:

  * `integration_partner` — one row per platform per academy, holding a hashed API
    key. Tenant-scoped and under RLS like every other business table, so one
    academy's integrations are invisible to another's.

  * Three columns on `booking` recording provenance. `created_by_partner_id` is what
    the gateway authorises on; `source_platform` is the denormalised name that
    survives the integration being deleted; `external_ref` is the partner's own id,
    which the partial unique index turns into an idempotency key.

Revision ID: c8d41a7b6e52
Revises: a1c7f3e29b40
Create Date: 2026-08-21 11:02:44.815203
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from alembic_rls import protect, unprotect


revision: str = 'c8d41a7b6e52'
down_revision: Union[str, None] = 'a1c7f3e29b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'integration_partner',
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('key_prefix', sa.String(length=32), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        # server_default, matching every other table: UUIDPrimaryKeyMixin declares
        # gen_random_uuid() on the column rather than generating ids in Python, so a
        # migration that omits it produces a table nothing can insert into.
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_integration_partner_tenant_id'), 'integration_partner', ['tenant_id'])
    # lower(slug): "Playo" and "playo" must not both exist for one academy.
    op.create_index(
        'uq_partner_tenant_slug',
        'integration_partner',
        ['tenant_id', sa.text('lower(slug)')],
        unique=True,
    )
    # Globally unique — an inbound key is looked up by prefix alone, and that lookup
    # must resolve to exactly one row or authentication becomes ambiguous.
    op.create_index('uq_partner_key_prefix', 'integration_partner', ['key_prefix'], unique=True)

    op.add_column('booking', sa.Column('created_by_partner_id', sa.UUID(), nullable=True))
    op.add_column('booking', sa.Column('source_platform', sa.String(length=50), nullable=True))
    op.add_column('booking', sa.Column('external_ref', sa.String(length=120), nullable=True))
    op.create_foreign_key(
        'fk_booking_created_by_partner',
        'booking',
        'integration_partner',
        ['created_by_partner_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    # Partial: every counter booking has a NULL external_ref, and those must not
    # collide with one another. Only real partner references are constrained.
    op.create_index(
        'uq_booking_partner_external_ref',
        'booking',
        ['tenant_id', 'created_by_partner_id', 'external_ref'],
        unique=True,
        postgresql_where=sa.text('external_ref IS NOT NULL'),
    )

    protect(['integration_partner'])


def downgrade() -> None:
    unprotect(['integration_partner'])

    op.drop_index('uq_booking_partner_external_ref', table_name='booking')
    op.drop_constraint('fk_booking_created_by_partner', 'booking', type_='foreignkey')
    op.drop_column('booking', 'external_ref')
    op.drop_column('booking', 'source_platform')
    op.drop_column('booking', 'created_by_partner_id')

    op.drop_index('uq_partner_key_prefix', table_name='integration_partner')
    op.drop_index('uq_partner_tenant_slug', table_name='integration_partner')
    op.drop_index(op.f('ix_integration_partner_tenant_id'), table_name='integration_partner')
    op.drop_table('integration_partner')
