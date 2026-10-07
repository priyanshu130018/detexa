"""Initial Neon PostgreSQL Normalized Schema

Revision ID: 0001_initial_neon_schema
Revises: 
Create Date: 2026-10-06 17:15:00.000000

Normalized enterprise schema for Detexa Financial Fraud Detection & Behavioral Analytics.
Target database: Neon PostgreSQL Serverless (compatible with SQLAlchemy 2.0).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001_initial_neon_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Create Enums (PostgreSQL-safe) ──────────────────────────────────────
    risk_level_enum = postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', name='risklevel', create_type=False)
    alert_status_enum = postgresql.ENUM('open', 'reviewed', 'resolved', 'false_positive', name='alertstatus', create_type=False)
    decision_type_enum = postgresql.ENUM('ALLOW', 'REVIEW', 'BLOCK', name='decisiontype', create_type=False)

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DO $$ BEGIN CREATE TYPE risklevel AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'Low', 'Medium', 'High', 'Critical'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
        op.execute("DO $$ BEGIN ALTER TYPE risklevel ADD VALUE IF NOT EXISTS 'CHALLENGE'; EXCEPTION WHEN others THEN null; END $$;")
        op.execute("DO $$ BEGIN CREATE TYPE alertstatus AS ENUM ('open', 'reviewed', 'resolved', 'false_positive'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
        op.execute("DO $$ BEGIN CREATE TYPE decisiontype AS ENUM ('ALLOW', 'CHALLENGE', 'REVIEW', 'BLOCK'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
        op.execute("DO $$ BEGIN ALTER TYPE decisiontype ADD VALUE IF NOT EXISTS 'CHALLENGE'; EXCEPTION WHEN others THEN null; END $$;")

    # ── 2. Users Table ─────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('mobile', sa.String(length=20), nullable=True),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # ── 3. Merchants Table ─────────────────────────────────────────────────────
    op.create_table(
        'merchants',
        sa.Column('id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('category', sa.String(length=60), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=False, server_default=sa.text('0.0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_merchants_name', 'merchants', ['name'], unique=True)
    op.create_index('ix_merchants_category', 'merchants', ['category'])

    # ── 4. Devices Table ───────────────────────────────────────────────────────
    op.create_table(
        'devices',
        sa.Column('id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('device_fingerprint', sa.String(length=255), nullable=False),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('is_trusted', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'device_fingerprint', name='uq_user_device_fingerprint'),
    )
    op.create_index('ix_devices_user_id', 'devices', ['user_id'])
    op.create_index('ix_devices_device_fingerprint', 'devices', ['device_fingerprint'])

    # ── 5. IP Addresses Table ──────────────────────────────────────────────────
    op.create_table(
        'ip_addresses',
        sa.Column('id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('geo_country', sa.String(length=60), nullable=True),
        sa.Column('geo_city', sa.String(length=60), nullable=True),
        sa.Column('is_vpn', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_tor', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('reputation_score', sa.Float(), nullable=False, server_default=sa.text('0.0')),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_ip_addresses_ip_address', 'ip_addresses', ['ip_address'], unique=True)
    op.create_index('ix_ip_addresses_geo_country', 'ip_addresses', ['geo_country'])

    # ── 6. Model Metadata Registry ─────────────────────────────────────────────
    op.create_table(
        'model_metadata',
        sa.Column('id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=30), nullable=False),
        sa.Column('algorithm', sa.String(length=60), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False, server_default=sa.text('0.50')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == 'postgresql' else sa.JSON(), nullable=True),
        sa.Column('trained_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('model_name', 'version', name='uq_model_name_version'),
    )
    op.create_index('ix_model_metadata_model_name', 'model_metadata', ['model_name'])

    # ── 7. Transactions Table ──────────────────────────────────────────────────
    op.create_table(
        'transactions',
        sa.Column('id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('merchant_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='SET NULL'), nullable=True),
        sa.Column('device_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('devices.id', ondelete='SET NULL'), nullable=True),
        sa.Column('ip_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('ip_addresses.id', ondelete='SET NULL'), nullable=True),
        sa.Column('transaction_ref', sa.String(length=64), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
        sa.Column('merchant', sa.String(length=120), nullable=True),
        sa.Column('category', sa.String(length=60), nullable=True),
        sa.Column('country', sa.String(length=60), nullable=True),
        # Kaggle PCA Features
        sa.Column('v1', sa.Float(), nullable=True), sa.Column('v2', sa.Float(), nullable=True),
        sa.Column('v3', sa.Float(), nullable=True), sa.Column('v4', sa.Float(), nullable=True),
        sa.Column('v5', sa.Float(), nullable=True), sa.Column('v6', sa.Float(), nullable=True),
        sa.Column('v7', sa.Float(), nullable=True), sa.Column('v8', sa.Float(), nullable=True),
        sa.Column('v9', sa.Float(), nullable=True), sa.Column('v10', sa.Float(), nullable=True),
        sa.Column('v11', sa.Float(), nullable=True), sa.Column('v12', sa.Float(), nullable=True),
        sa.Column('v13', sa.Float(), nullable=True), sa.Column('v14', sa.Float(), nullable=True),
        sa.Column('v15', sa.Float(), nullable=True), sa.Column('v16', sa.Float(), nullable=True),
        sa.Column('v17', sa.Float(), nullable=True), sa.Column('v18', sa.Float(), nullable=True),
        sa.Column('v19', sa.Float(), nullable=True), sa.Column('v20', sa.Float(), nullable=True),
        sa.Column('v21', sa.Float(), nullable=True), sa.Column('v22', sa.Float(), nullable=True),
        sa.Column('v23', sa.Float(), nullable=True), sa.Column('v24', sa.Float(), nullable=True),
        sa.Column('v25', sa.Float(), nullable=True), sa.Column('v26', sa.Float(), nullable=True),
        sa.Column('v27', sa.Float(), nullable=True), sa.Column('v28', sa.Float(), nullable=True),
        # Prediction & Metadata
        sa.Column('fraud_score', sa.Float(), nullable=True),
        sa.Column('risk_level', risk_level_enum if bind.dialect.name == 'postgresql' else sa.String(20), nullable=True),
        sa.Column('is_fraud', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('label', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('amount > 0', name='chk_positive_transaction_amount'),
    )
    op.create_index('ix_transactions_transaction_ref', 'transactions', ['transaction_ref'], unique=True)
    op.create_index('ix_transactions_user_id', 'transactions', ['user_id'])
    op.create_index('ix_transactions_merchant_id', 'transactions', ['merchant_id'])
    op.create_index('ix_transactions_device_id', 'transactions', ['device_id'])
    op.create_index('ix_transactions_ip_id', 'transactions', ['ip_id'])
    op.create_index('ix_transactions_risk_level', 'transactions', ['risk_level'])
    op.create_index('ix_transactions_is_fraud', 'transactions', ['is_fraud'])
    op.create_index('ix_transactions_timestamp', 'transactions', ['timestamp'])
    op.create_index('ix_transactions_user_timestamp', 'transactions', ['user_id', 'timestamp'])
    op.create_index('ix_transactions_fraud_timestamp', 'transactions', ['is_fraud', 'timestamp'])

    # ── 8. Fraud Predictions Table ─────────────────────────────────────────────
    op.create_table(
        'fraud_predictions',
        sa.Column('id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('transaction_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('transactions.id', ondelete='CASCADE'), unique=True, nullable=True),
        sa.Column('model_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('model_metadata.id', ondelete='SET NULL'), nullable=True),
        sa.Column('endpoint', sa.String(length=60), nullable=False),
        sa.Column('input_hash', sa.String(length=64), nullable=True),
        sa.Column('fraud_score', sa.Float(), nullable=False),
        sa.Column('anomaly_score', sa.Float(), nullable=True),
        sa.Column('risk_level', risk_level_enum if bind.dialect.name == 'postgresql' else sa.String(20), nullable=False),
        sa.Column('is_fraud', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('decision', decision_type_enum if bind.dialect.name == 'postgresql' else sa.String(20), nullable=False, server_default='ALLOW'),
        sa.Column('shap_values', postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == 'postgresql' else sa.JSON(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=False),
        sa.Column('model_version', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('fraud_score >= 0.0 AND fraud_score <= 1.0', name='chk_fraud_score_range'),
    )
    op.create_index('ix_fraud_predictions_transaction_id', 'fraud_predictions', ['transaction_id'])
    op.create_index('ix_fraud_predictions_model_id', 'fraud_predictions', ['model_id'])
    op.create_index('ix_fraud_predictions_input_hash', 'fraud_predictions', ['input_hash'])
    op.create_index('ix_fraud_predictions_risk_level', 'fraud_predictions', ['risk_level'])
    op.create_index('ix_fraud_predictions_created_at', 'fraud_predictions', ['created_at'])

    # ── 9. Fraud Alerts Table ──────────────────────────────────────────────────
    op.create_table(
        'fraud_alerts',
        sa.Column('id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('transaction_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('transactions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('prediction_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('fraud_predictions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigned_to', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('alert_type', sa.String(length=60), nullable=False),
        sa.Column('risk_level', risk_level_enum if bind.dialect.name == 'postgresql' else sa.String(20), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', alert_status_enum if bind.dialect.name == 'postgresql' else sa.String(20), nullable=False, server_default='open'),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('shap_values', postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == 'postgresql' else sa.JSON(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == 'postgresql' else sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_fraud_alerts_user_id', 'fraud_alerts', ['user_id'])
    op.create_index('ix_fraud_alerts_transaction_id', 'fraud_alerts', ['transaction_id'])
    op.create_index('ix_fraud_alerts_prediction_id', 'fraud_alerts', ['prediction_id'])
    op.create_index('ix_fraud_alerts_assigned_to', 'fraud_alerts', ['assigned_to'])
    op.create_index('ix_fraud_alerts_risk_level', 'fraud_alerts', ['risk_level'])
    op.create_index('ix_fraud_alerts_status', 'fraud_alerts', ['status'])
    op.create_index('ix_fraud_alerts_created_at', 'fraud_alerts', ['created_at'])
    op.create_index('ix_fraud_alerts_status_risk_created', 'fraud_alerts', ['status', 'risk_level', 'created_at'])

    # ── 10. Behavior Logs Table ────────────────────────────────────────────────
    op.create_table(
        'behavior_logs',
        sa.Column('id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('device_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('devices.id', ondelete='SET NULL'), nullable=True),
        sa.Column('ip_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('ip_addresses.id', ondelete='SET NULL'), nullable=True),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('device_fingerprint', sa.String(length=255), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('login_hour', sa.Integer(), nullable=True),
        sa.Column('typing_speed', sa.Float(), nullable=True),
        sa.Column('mouse_velocity', sa.Float(), nullable=True),
        sa.Column('geo_country', sa.String(length=60), nullable=True),
        sa.Column('geo_city', sa.String(length=60), nullable=True),
        sa.Column('is_vpn', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_tor', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('failed_logins', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('device_change', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('anomaly_score', sa.Float(), nullable=True),
        sa.Column('risk_level', risk_level_enum if bind.dialect.name == 'postgresql' else sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_behavior_logs_user_id', 'behavior_logs', ['user_id'])
    op.create_index('ix_behavior_logs_device_id', 'behavior_logs', ['device_id'])
    op.create_index('ix_behavior_logs_ip_id', 'behavior_logs', ['ip_id'])
    op.create_index('ix_behavior_logs_session_id', 'behavior_logs', ['session_id'])
    op.create_index('ix_behavior_logs_anomaly_score', 'behavior_logs', ['anomaly_score'])
    op.create_index('ix_behavior_logs_risk_level', 'behavior_logs', ['risk_level'])
    op.create_index('ix_behavior_logs_created_at', 'behavior_logs', ['created_at'])

    # ── 11. Audit Logs Table ───────────────────────────────────────────────────
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.CHAR(36) if bind.dialect.name != 'postgresql' else postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.String(length=64), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == 'postgresql' else sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_entity_type', 'audit_logs', ['entity_type'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table('audit_logs')
    op.drop_table('behavior_logs')
    op.drop_table('fraud_alerts')
    op.drop_table('fraud_predictions')
    op.drop_table('transactions')
    op.drop_table('model_metadata')
    op.drop_table('ip_addresses')
    op.drop_table('devices')
    op.drop_table('merchants')
    op.drop_table('users')

    if bind.dialect.name == 'postgresql':
        op.execute("DROP TYPE IF EXISTS decisiontype;")
        op.execute("DROP TYPE IF EXISTS alertstatus;")
        op.execute("DROP TYPE IF EXISTS risklevel;")
