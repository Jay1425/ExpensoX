"""Add manager_notes to expenses

Revision ID: ed6bb82322d5
Revises: 
Create Date: 2025-10-04 13:20:10.264635

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ed6bb82322d5'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column['name'] for column in inspector.get_columns('expenses')]
    if 'manager_notes' not in columns:
        op.add_column('expenses', sa.Column('manager_notes', sa.Text(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column['name'] for column in inspector.get_columns('expenses')]
    if 'manager_notes' in columns:
        op.drop_column('expenses', 'manager_notes')
