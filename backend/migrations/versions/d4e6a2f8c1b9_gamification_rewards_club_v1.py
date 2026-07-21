"""gamification rewards club v1 (rule engine, wallet, ledger upgrade, reward marketplace, audit)

Revision ID: d4e6a2f8c1b9
Revises: c8f2a5d9e3b7
Create Date: 2026-07-20 00:00:00.000000+00:00

توضیح:
    بازطراحی موتور امتیازدهی V0 به یک ماژول Enterprise:

    ۱. point_policy_rules جایگزین point_group_overrides می‌شود — به‌جای
       دو scope ثابت (role/department) با منطق «کمترین برنده»، حالا
       Priority Engine صریح ۴سطحی (User > Position > Department >
       Organization) با امکان ترکیب هم‌زمان چند شرط. override اختصاصیِ
       خودِ موجودیت (ستون points_override — بدون تغییر) + point_rules
       سراسری با هم سطح ۵ (Default) را تشکیل می‌دهند.

       داده‌های قبلیِ point_group_overrides با target_type=department
       مستقیماً migrate می‌شوند. ردیف‌های target_type=role حذف می‌شوند
       چون اسپک جدید هیچ سطح «نقش» ندارد (فقط Position) — این یک تغییر
       عمدی سیاست است، نه یک باگ.

    ۲. points_ledger کامل می‌شود: transaction_type، transaction_number
       (شماره‌ی تراکنش یکتا)، balance_before/after، points_source
       (ردیابی این‌که امتیاز از کدام سطح Priority Engine آمده)،
       created_by، description. سطرهای موجود transaction_type='earn'
       می‌گیرند و balance_before/after با window function بر اساس
       ترتیب زمانی هر کاربر backfill می‌شود.

    ۳. point_wallets — کیف‌پول امتیاز به‌ازای هر کاربر؛ از روی مجموع
       points_ledger برای کاربرانی که حداقل یک تراکنش دارند backfill
       می‌شود (بقیه هنگام اولین تراکنش توسط wallet_service ساخته می‌شوند).

    ۴. rewards + reward_redemptions — فروشگاه و گردش تبدیل امتیاز.

    ۵. gamification_audit_logs — Audit Trail سراسری ماژول.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e6a2f8c1b9'
down_revision: Union[str, Sequence[str], None] = 'c8f2a5d9e3b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ─── ۰. point_rules.event_label — event_type از این پس یک enum ثابت در
    # کد نیست؛ برچسب فارسی هم در دیتابیس ذخیره می‌شود تا super_admin بتواند
    # از طریق API نوع Event دلخواه (فعلی یا آینده) با برچسب خودش اضافه کند.
    op.add_column('point_rules', sa.Column('event_label', sa.String(length=100), nullable=True))
    op.execute("""
        UPDATE point_rules SET event_label = CASE event_type
            WHEN 'content_item_completed' THEN 'تکمیل آیتم محتوا'
            WHEN 'content_completed' THEN 'تکمیل کامل محتوا'
            WHEN 'quiz_passed' THEN 'قبولی در آزمون'
            WHEN 'onboarding_step_completed' THEN 'تکمیل مرحله‌ی آنبوردینگ'
            WHEN 'onboarding_program_completed' THEN 'تکمیل کامل برنامه‌ی آنبوردینگ'
            ELSE event_type
        END
    """)
    op.alter_column('point_rules', 'event_label', nullable=False)

    # ─── ۱. point_policy_rules (جایگزین point_group_overrides) ────────────
    op.create_table(
        'point_policy_rules',
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('org_id', sa.UUID(), nullable=True),
        sa.Column('dept_id', sa.UUID(), nullable=True),
        sa.Column('position_id', sa.UUID(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dept_id'], ['departments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['position_id'], ['positions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            'org_id IS NOT NULL OR dept_id IS NOT NULL OR position_id IS NOT NULL OR user_id IS NOT NULL',
            name='ck_point_policy_rule_has_scope',
        ),
    )
    op.create_index(op.f('ix_point_policy_rules_event_type'), 'point_policy_rules', ['event_type'], unique=False)

    op.execute("""
        INSERT INTO point_policy_rules (id, event_type, dept_id, points, priority, is_active, created_at, updated_at)
        SELECT gen_random_uuid(), event_type, target_value::uuid, points, 0, is_active, created_at, updated_at
        FROM point_group_overrides
        WHERE target_type = 'department'
    """)

    op.drop_table('point_group_overrides')

    # ─── ۲. points_ledger — تکمیل به یک دفتر کل واقعی ──────────────────────
    op.add_column('points_ledger', sa.Column('transaction_number', sa.String(length=30), nullable=True))
    op.add_column('points_ledger', sa.Column('transaction_type', sa.String(length=30), nullable=False, server_default='earn'))
    op.add_column('points_ledger', sa.Column('balance_before', sa.Integer(), nullable=True))
    op.add_column('points_ledger', sa.Column('balance_after', sa.Integer(), nullable=True))
    op.add_column('points_ledger', sa.Column('points_source', sa.String(length=30), nullable=True))
    op.add_column('points_ledger', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('points_ledger', sa.Column('created_by', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_points_ledger_created_by_users', 'points_ledger', 'users', ['created_by'], ['id'], ondelete='SET NULL',
    )

    op.execute("CREATE SEQUENCE IF NOT EXISTS points_ledger_txn_seq START 1")
    op.execute("""
        WITH ordered AS (
            SELECT id, row_number() OVER (ORDER BY created_at, id) AS rn
            FROM points_ledger
        )
        UPDATE points_ledger pl
        SET transaction_number = 'TXN-' || lpad(o.rn::text, 8, '0')
        FROM ordered o
        WHERE o.id = pl.id
    """)
    op.execute("SELECT setval('points_ledger_txn_seq', GREATEST((SELECT COUNT(*) FROM points_ledger), 1))")

    op.execute("""
        WITH running AS (
            SELECT id,
                   SUM(points) OVER (PARTITION BY user_id ORDER BY created_at, id
                                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
            FROM points_ledger
        )
        UPDATE points_ledger pl
        SET balance_after = r.running_total,
            balance_before = r.running_total - pl.points
        FROM running r
        WHERE r.id = pl.id
    """)

    op.alter_column('points_ledger', 'transaction_number', nullable=False)
    op.alter_column('points_ledger', 'balance_before', nullable=False)
    op.alter_column('points_ledger', 'balance_after', nullable=False)
    op.alter_column('points_ledger', 'transaction_type', server_default=None)
    op.create_unique_constraint('uq_points_ledger_transaction_number', 'points_ledger', ['transaction_number'])
    op.create_index(op.f('ix_points_ledger_transaction_number'), 'points_ledger', ['transaction_number'], unique=False)

    # ─── ۳. point_wallets ───────────────────────────────────────────────────
    op.create_table(
        'point_wallets',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('current_balance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_earned', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_spent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_expired', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pending_points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('redeemed_points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_point_wallets_user_id'),
    )
    op.create_index(op.f('ix_point_wallets_org_id'), 'point_wallets', ['org_id'], unique=False)

    op.execute("""
        INSERT INTO point_wallets (id, user_id, org_id, current_balance, total_earned, total_spent, updated_at)
        SELECT
            gen_random_uuid(),
            pl.user_id,
            u.org_id,
            SUM(pl.points),
            SUM(pl.points) FILTER (WHERE pl.points > 0),
            ABS(SUM(pl.points) FILTER (WHERE pl.points < 0)),
            now()
        FROM points_ledger pl
        JOIN users u ON u.id = pl.user_id
        GROUP BY pl.user_id, u.org_id
    """)

    # ─── ۴. rewards + reward_redemptions ────────────────────────────────────
    op.create_table(
        'rewards',
        sa.Column('org_id', sa.UUID(), nullable=True, comment='null یعنی سراسری — فقط super_admin می‌تواند null بگذارد'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=30), nullable=False, server_default='custom'),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('cost_points', sa.Integer(), nullable=False),
        sa.Column('inventory_total', sa.Integer(), nullable=True),
        sa.Column('inventory_remaining', sa.Integer(), nullable=True),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_rewards_org_id'), 'rewards', ['org_id'], unique=False)

    op.create_table(
        'reward_redemptions',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('reward_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='submitted'),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('cost_points_snapshot', sa.Integer(), nullable=False),
        sa.Column('user_note', sa.Text(), nullable=True),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decided_by', sa.UUID(), nullable=True),
        sa.Column('delivered_by', sa.UUID(), nullable=True),
        sa.Column('ledger_entry_id', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reward_id'], ['rewards.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['decided_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['delivered_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['ledger_entry_id'], ['points_ledger.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reward_redemptions_org_id'), 'reward_redemptions', ['org_id'], unique=False)
    op.create_index(op.f('ix_reward_redemptions_user_id'), 'reward_redemptions', ['user_id'], unique=False)
    op.create_index(op.f('ix_reward_redemptions_reward_id'), 'reward_redemptions', ['reward_id'], unique=False)
    op.create_index(op.f('ix_reward_redemptions_status'), 'reward_redemptions', ['status'], unique=False)

    # ─── ۵. gamification_audit_logs ─────────────────────────────────────────
    op.create_table(
        'gamification_audit_logs',
        sa.Column('org_id', sa.UUID(), nullable=True),
        sa.Column('actor_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.UUID(), nullable=True),
        sa.Column('before', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('after', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_gamification_audit_logs_org_id'), 'gamification_audit_logs', ['org_id'], unique=False)
    op.create_index(op.f('ix_gamification_audit_logs_action'), 'gamification_audit_logs', ['action'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_gamification_audit_logs_action'), table_name='gamification_audit_logs')
    op.drop_index(op.f('ix_gamification_audit_logs_org_id'), table_name='gamification_audit_logs')
    op.drop_table('gamification_audit_logs')

    op.drop_index(op.f('ix_reward_redemptions_status'), table_name='reward_redemptions')
    op.drop_index(op.f('ix_reward_redemptions_reward_id'), table_name='reward_redemptions')
    op.drop_index(op.f('ix_reward_redemptions_user_id'), table_name='reward_redemptions')
    op.drop_index(op.f('ix_reward_redemptions_org_id'), table_name='reward_redemptions')
    op.drop_table('reward_redemptions')

    op.drop_index(op.f('ix_rewards_org_id'), table_name='rewards')
    op.drop_table('rewards')

    op.drop_index(op.f('ix_point_wallets_org_id'), table_name='point_wallets')
    op.drop_table('point_wallets')

    op.drop_index(op.f('ix_points_ledger_transaction_number'), table_name='points_ledger')
    op.drop_constraint('uq_points_ledger_transaction_number', 'points_ledger', type_='unique')
    op.drop_constraint('fk_points_ledger_created_by_users', 'points_ledger', type_='foreignkey')
    op.drop_column('points_ledger', 'created_by')
    op.drop_column('points_ledger', 'description')
    op.drop_column('points_ledger', 'points_source')
    op.drop_column('points_ledger', 'balance_after')
    op.drop_column('points_ledger', 'balance_before')
    op.drop_column('points_ledger', 'transaction_type')
    op.drop_column('points_ledger', 'transaction_number')
    op.execute("DROP SEQUENCE IF EXISTS points_ledger_txn_seq")

    op.drop_index(op.f('ix_point_policy_rules_event_type'), table_name='point_policy_rules')
    op.drop_table('point_policy_rules')

    op.create_table(
        'point_group_overrides',
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('target_type', sa.String(length=20), nullable=False, comment='role | department'),
        sa.Column('target_value', sa.String(length=255), nullable=False, comment='نام نقش برای role — UUID واحد سازمانی برای department'),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_type', 'target_type', 'target_value', name='uq_point_group_override'),
    )

    op.drop_column('point_rules', 'event_label')
