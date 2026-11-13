"""data per user

Give each application and each profile an owner.

Rows that already exist (your local data from before login) are given to the dev user, the
same user that AUTH_DISABLED=true uses. So after this migration, local development still
shows all of your old data.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12 20:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEV_SUB = "dev-user"


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add the columns as nullable, so existing rows are allowed for a moment
    op.add_column('applications', sa.Column('user_id', sa.Uuid(), nullable=True))
    op.add_column('profile', sa.Column('user_id', sa.Uuid(), nullable=True))

    # 2. Give every existing row to the dev user (made only if there is something to give)
    op.execute(sa.text("""
        INSERT INTO users (id, cognito_sub, email)
        SELECT gen_random_uuid(), :sub, 'dev@localhost'
        WHERE (EXISTS (SELECT 1 FROM applications) OR EXISTS (SELECT 1 FROM profile))
        ON CONFLICT (cognito_sub) DO NOTHING
    """).bindparams(sub=DEV_SUB))
    for table in ('applications', 'profile'):
        op.execute(sa.text(
            f"UPDATE {table} SET user_id = (SELECT id FROM users WHERE cognito_sub = :sub)"
        ).bindparams(sub=DEV_SUB))

    # 3. Now every row has an owner: make it required
    op.alter_column('applications', 'user_id', nullable=False)
    op.alter_column('profile', 'user_id', nullable=False)
    op.create_foreign_key(
        'applications_user_id_fkey', 'applications', 'users', ['user_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'profile_user_id_fkey', 'profile', 'users', ['user_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index(op.f('ix_applications_user_id'), 'applications', ['user_id'], unique=False)

    # 4. profile: the owner is the key. The old fixed id (always 1) is not needed any more.
    op.drop_constraint('profile_pkey', 'profile', type_='primary')
    op.drop_column('profile', 'id')
    op.create_primary_key('profile_pkey', 'profile', ['user_id'])


def downgrade() -> None:
    """Downgrade schema. Rows stay. Only the owner link is removed."""
    op.drop_constraint('profile_pkey', 'profile', type_='primary')
    op.execute(sa.text("ALTER TABLE profile ADD COLUMN id SERIAL"))
    op.create_primary_key('profile_pkey', 'profile', ['id'])

    op.drop_index(op.f('ix_applications_user_id'), table_name='applications')
    op.drop_constraint('profile_user_id_fkey', 'profile', type_='foreignkey')
    op.drop_constraint('applications_user_id_fkey', 'applications', type_='foreignkey')
    op.drop_column('profile', 'user_id')
    op.drop_column('applications', 'user_id')
