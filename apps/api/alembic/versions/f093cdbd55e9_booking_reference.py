"""booking reference

`XC-B-0042` on every booking — the code a customer reads off their ticket and types
at the kiosk to check in.

Three different strings were previously shown as "the booking id": the full UUID in
the confirmation email, the last six hex characters on the ticket, and the first
eight on the check-in result. None of them could be asked for at a counter. This
adds one reference, from the same per-tenant DocumentCounter series that already
numbers invoices and members.

── The backfill, and why RLS has to be lifted for it ───────────────────────────
Every existing booking is numbered in creation order, so the oldest becomes 0001,
and each academy's counter is set to its booking count so new bookings continue the
series rather than colliding with it.

That DML has to reach every tenant's rows at once, and `booking`, `tenant_settings`
and `document_counter` all carry FORCE ROW LEVEL SECURITY — which, unlike plain
ENABLE, binds the table owner too. This migration runs as that owner with no
`app.current_tenant` set, so the policy predicate is false and a straight UPDATE
would silently touch zero rows and then fail the NOT NULL below.

So FORCE is dropped for the three tables and restored immediately after. Not
`SET row_security = off`: that raises an error rather than bypassing, by design.

Revision ID: f093cdbd55e9
Revises: b68088ce38ae
Create Date: 2026-08-21 21:41:08.552914
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f093cdbd55e9'
down_revision: str | None = 'b68088ce38ae'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Read and written across every tenant by the backfill below.
BACKFILL_TABLES = ('booking', 'tenant_settings', 'document_counter')


def _force_rls(on: bool) -> None:
    keyword = 'FORCE' if on else 'NO FORCE'
    for table in BACKFILL_TABLES:
        op.execute(f'ALTER TABLE {table} {keyword} ROW LEVEL SECURITY')


def upgrade() -> None:
    # Nullable first: there is no default that could be correct, and every existing
    # row needs a distinct value.
    op.add_column('booking', sa.Column('reference', sa.String(length=32), nullable=True))

    _force_rls(False)
    try:
        # Oldest booking becomes 0001. `created_at, id` rather than `created_at`
        # alone so two bookings taken in the same millisecond still get a stable,
        # repeatable order — this migration must produce the same numbering if it is
        # ever replayed against a restored dump.
        op.execute(
            """
            WITH numbered AS (
                SELECT id,
                       tenant_id,
                       row_number() OVER (
                           PARTITION BY tenant_id ORDER BY created_at, id
                       ) AS seq
                FROM booking
            )
            UPDATE booking AS b
            SET reference = COALESCE(s.invoice_prefix, 'XC')
                            || '-B-'
                            || lpad(n.seq::text, 4, '0')
            FROM numbered AS n
            LEFT JOIN tenant_settings AS s ON s.tenant_id = n.tenant_id
            WHERE b.id = n.id
            """
        )

        # Continue the series rather than restarting it. Without this the next
        # booking an academy takes would be allocated 0001 and collide with its own
        # oldest booking on the unique index below.
        op.execute(
            """
            INSERT INTO document_counter (tenant_id, kind, period, last_value)
            SELECT tenant_id, 'booking', '', count(*)
            FROM booking
            GROUP BY tenant_id
            ON CONFLICT (tenant_id, kind, period)
            DO UPDATE SET last_value = EXCLUDED.last_value
            """
        )
    finally:
        # In a finally so a failed backfill cannot leave the table unprotected. The
        # migration is transactional, so this rolls back with everything else — but
        # a partially-applied migration that silently disabled tenant isolation is
        # not a failure mode worth leaving to chance.
        _force_rls(True)

    op.alter_column('booking', 'reference', existing_type=sa.String(length=32), nullable=False)
    op.create_index(
        'uq_booking_tenant_reference', 'booking', ['tenant_id', 'reference'], unique=True
    )


def downgrade() -> None:
    op.drop_index('uq_booking_tenant_reference', table_name='booking')
    op.drop_column('booking', 'reference')

    _force_rls(False)
    try:
        op.execute("DELETE FROM document_counter WHERE kind = 'booking'")
    finally:
        _force_rls(True)
