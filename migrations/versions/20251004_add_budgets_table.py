"""Create budgets table

Revision ID: 20251004_add_budgets
Revises: ed6bb82322d5
Create Date: 2025-10-04 15:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251004_add_budgets'
down_revision = 'ed6bb82322d5'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'budgets' not in tables:
        op.create_table(
            'budgets',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
            sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=False),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('currency', sa.String(length=10), nullable=False),
            sa.Column('period_start', sa.Date(), nullable=False),
            sa.Column('period_end', sa.Date(), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_budgets_company_id', 'budgets', ['company_id'])
        op.create_index('ix_budgets_category_id', 'budgets', ['category_id'])
        op.create_index('ix_budgets_period', 'budgets', ['period_start', 'period_end'])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'budgets' in tables:
        op.drop_index('ix_budgets_period', table_name='budgets')
        op.drop_index('ix_budgets_category_id', table_name='budgets')
        op.drop_index('ix_budgets_company_id', table_name='budgets')
        op.drop_table('budgets')
