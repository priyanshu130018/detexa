"""Indian Banking Transactions Schema Migration

Revision ID: 0002_indian_banking_transactions_schema
Revises: 0001_initial_neon_schema
Create Date: 2026-10-07 20:35:00.000000

Migrates transactions table from Kaggle PCA columns (V1-V28) to Indian Banking transaction schema.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_banking_schema'
down_revision = '0001_initial_neon_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add Indian banking transaction columns
    op.add_column('transactions', sa.Column('customer_id', sa.String(length=64), nullable=True))
    op.add_column('transactions', sa.Column('transaction_amount', sa.Float(), nullable=True))
    op.add_column('transactions', sa.Column('account_type', sa.String(length=30), nullable=True))
    op.add_column('transactions', sa.Column('transaction_type', sa.String(length=30), nullable=True))
    op.add_column('transactions', sa.Column('transaction_direction', sa.String(length=10), nullable=True))
    op.add_column('transactions', sa.Column('account_balance', sa.Float(), nullable=True))
    op.add_column('transactions', sa.Column('merchant_category', sa.String(length=60), nullable=True))
    op.add_column('transactions', sa.Column('state', sa.String(length=40), nullable=True))
    op.add_column('transactions', sa.Column('credit_score', sa.Integer(), nullable=True))
    op.add_column('transactions', sa.Column('has_loan', sa.Integer(), nullable=True))
    op.add_column('transactions', sa.Column('loan_type', sa.String(length=30), nullable=True))
    op.add_column('transactions', sa.Column('emi_amount', sa.Float(), nullable=True))
    op.add_column('transactions', sa.Column('transaction_status', sa.String(length=30), nullable=True))
    op.add_column('transactions', sa.Column('channel', sa.String(length=30), nullable=True))
    op.add_column('transactions', sa.Column('kyc_status', sa.String(length=30), nullable=True))
    op.add_column('transactions', sa.Column('transaction_hour', sa.Integer(), nullable=True))
    op.add_column('transactions', sa.Column('transaction_date', sa.String(length=10), nullable=True))
    op.add_column('transactions', sa.Column('transaction_time', sa.String(length=8), nullable=True))

    op.create_index('ix_transactions_customer_id', 'transactions', ['customer_id'])

    # 2. Drop obsolete PCA V1-V28 columns
    for i in range(1, 29):
        try:
            op.drop_column('transactions', f'v{i}')
        except Exception:
            pass


def downgrade() -> None:
    # Re-add PCA columns
    for i in range(1, 29):
        op.add_column('transactions', sa.Column(f'v{i}', sa.Float(), nullable=True))

    # Drop index and columns
    op.drop_index('ix_transactions_customer_id', table_name='transactions')
    op.drop_column('transactions', 'transaction_time')
    op.drop_column('transactions', 'transaction_date')
    op.drop_column('transactions', 'transaction_hour')
    op.drop_column('transactions', 'kyc_status')
    op.drop_column('transactions', 'channel')
    op.drop_column('transactions', 'transaction_status')
    op.drop_column('transactions', 'emi_amount')
    op.drop_column('transactions', 'loan_type')
    op.drop_column('transactions', 'has_loan')
    op.drop_column('transactions', 'credit_score')
    op.drop_column('transactions', 'state')
    op.drop_column('transactions', 'merchant_category')
    op.drop_column('transactions', 'account_balance')
    op.drop_column('transactions', 'transaction_direction')
    op.drop_column('transactions', 'transaction_type')
    op.drop_column('transactions', 'account_type')
    op.drop_column('transactions', 'transaction_amount')
    op.drop_column('transactions', 'customer_id')
