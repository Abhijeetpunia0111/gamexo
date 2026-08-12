"""add kiosk role

Adds the `kiosk` member to the user_role CHECK constraint — the shared login on the
walk-in counter tablet. It sits below `reception` in ROLE_HIERARCHY, so every
dashboard endpoint (reporting, admin, finance) refuses it while the POS endpoints
admit it.

Exactly the one-line constraint swap that db/types.py's `native_enum=False` was
chosen to make possible: no ALTER TYPE, no table rewrite, no dependent-column churn.

Revision ID: a1c7f3e29b40
Revises: 154fad959663
Create Date: 2026-08-12 10:14:22.108931
"""

from typing import Sequence, Union

from alembic import op


revision: str = 'a1c7f3e29b40'
down_revision: Union[str, None] = '154fad959663'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# SQLAlchemy names the CHECK after the Enum's `name=`, so the constraint guarding
# app_user.role is itself called "user_role".
CONSTRAINT = "user_role"
TABLE = "app_user"

OLD_VALUES = ("admin", "manager", "reception")
NEW_VALUES = ("admin", "manager", "reception", "kiosk")


def _swap(values: tuple[str, ...]) -> None:
    """Point the CHECK at a new value set.

    IF EXISTS on the drop: this constraint is created as part of a column definition
    rather than by an explicit op.create_check_constraint, and a database restored
    from a dump that inlined it under a different name should not brick the upgrade.
    """
    rendered = ", ".join(f"'{value}'" for value in values)
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
    op.execute(
        f"ALTER TABLE {TABLE} ADD CONSTRAINT {CONSTRAINT} "
        f"CHECK (role IN ({rendered}))"
    )


def upgrade() -> None:
    _swap(NEW_VALUES)


def downgrade() -> None:
    # Any kiosk account would violate the narrowed constraint and abort the
    # downgrade halfway. Demote them first: reception is the nearest role that can
    # still run the POS, so a rollback degrades access rather than deleting logins.
    op.execute(f"UPDATE {TABLE} SET role = 'reception' WHERE role = 'kiosk'")
    _swap(OLD_VALUES)
