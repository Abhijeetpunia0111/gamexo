"""payment provider config

An academy's own payment gateway accounts — Razorpay, Cashfree, PhonePe, PayU,
Stripe — so it can collect online instead of only cash and UPI at the counter.

One table. What is worth reading twice:

  * `secrets_ciphertext` holds every secret field for the gateway as a single
    Fernet token, encrypted with a key that lives in the environment and not in
    this database. A dump of these rows is inert.

  * The two partial unique indexes are the point of the table. They make "at most
    one gateway collects for the dashboard, and at most one for the counter" a
    property Postgres enforces, rather than something the API remembers to do.
    `WHERE collect_on_web` restricts the uniqueness of `tenant_id` to the rows that
    actually claim the surface.

  * The CHECK stops a gateway being routed live payments with no credentials to
    sign them with — which would otherwise fail at the moment a customer taps pay.

Revision ID: b68088ce38ae
Revises: c8d41a7b6e52
Create Date: 2026-08-21 20:24:43.020557
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from alembic_rls import protect, unprotect

# NOTE: autogenerate also proposed dropping the server defaults on seven
# `equipment` columns. That is long-standing drift unrelated to this change — the
# model declares those defaults Python-side — and executing it would alter a table
# this migration has no business touching. Removed deliberately.

revision: str = 'b68088ce38ae'
down_revision: str | None = 'c8d41a7b6e52'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'payment_provider_config',
        sa.Column(
            'provider',
            sa.Enum(
                'razorpay', 'cashfree', 'phonepe', 'payu', 'stripe',
                name='payment_provider', native_enum=False, length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            'mode',
            sa.Enum('test', 'live', name='payment_provider_mode', native_enum=False, length=32),
            nullable=False,
        ),
        # Public halves — key ids, merchant ids, salt indexes. In the clear because
        # they reach the browser during a checkout regardless.
        sa.Column('public_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        # Every secret field for this gateway, as one Fernet token.
        sa.Column('secrets_ciphertext', sa.Text(), nullable=False),
        # Last four characters per secret, so the UI can show which key is saved
        # without the secret ever being sent back.
        sa.Column('secret_hints', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('collect_on_web', sa.Boolean(), nullable=False),
        sa.Column('collect_on_pos', sa.Boolean(), nullable=False),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_verification_error', sa.Text(), nullable=True),
        sa.Column('updated_by_email', sa.String(length=320), nullable=True),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.CheckConstraint(
            'NOT (collect_on_web OR collect_on_pos) OR char_length(secrets_ciphertext) > 0',
            name=op.f('ck_payment_provider_config_routed_gateway_has_credentials'),
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenant.id'],
            name=op.f('fk_payment_provider_config_tenant_id'), ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_provider_config')),
    )
    op.create_index(
        op.f('ix_payment_provider_config_tenant_id'),
        'payment_provider_config',
        ['tenant_id'],
    )
    # Connecting Razorpay twice is always a double-submit, never an intent.
    op.create_index(
        'uq_payment_provider_tenant_provider',
        'payment_provider_config',
        ['tenant_id', 'provider'],
        unique=True,
    )
    # One gateway per surface. See the module docstring.
    op.create_index(
        'uq_payment_provider_one_web',
        'payment_provider_config',
        ['tenant_id'],
        unique=True,
        postgresql_where=sa.text('collect_on_web'),
    )
    op.create_index(
        'uq_payment_provider_one_pos',
        'payment_provider_config',
        ['tenant_id'],
        unique=True,
        postgresql_where=sa.text('collect_on_pos'),
    )

    protect(['payment_provider_config'])


def downgrade() -> None:
    unprotect(['payment_provider_config'])

    op.drop_index(
        'uq_payment_provider_one_pos',
        table_name='payment_provider_config',
        postgresql_where=sa.text('collect_on_pos'),
    )
    op.drop_index(
        'uq_payment_provider_one_web',
        table_name='payment_provider_config',
        postgresql_where=sa.text('collect_on_web'),
    )
    op.drop_index('uq_payment_provider_tenant_provider', table_name='payment_provider_config')
    op.drop_index(
        op.f('ix_payment_provider_config_tenant_id'), table_name='payment_provider_config'
    )
    op.drop_table('payment_provider_config')
