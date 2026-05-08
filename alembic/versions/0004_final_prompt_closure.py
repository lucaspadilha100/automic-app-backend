"""final prompt closure fixes

Revision ID: 0004_final_prompt_closure
Revises: 0003_prompt_alignment_fixes
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_final_prompt_closure"
down_revision = "0003_prompt_alignment_fixes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    # Backfill prompt-compatible aliases and tenant_id fields.
    op.execute("""
        UPDATE customer_tag_links ctl
        SET tenant_id = tc.tenant_id
        FROM tenant_customers tc
        WHERE ctl.tenant_customer_id = tc.id
          AND ctl.tenant_id IS NULL
    """)
    op.alter_column("customer_tag_links", "tenant_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)

    op.execute("UPDATE customer_notes SET note = content WHERE note IS NULL")
    op.execute("""
        UPDATE customer_notes
        SET visibility = CASE WHEN COALESCE(is_internal, true) THEN 'internal' ELSE 'customer_visible' END
        WHERE visibility IS NULL
    """)
    op.alter_column("customer_notes", "note", existing_type=sa.Text(), nullable=False)
    op.alter_column("customer_notes", "visibility", existing_type=sa.String(length=30), nullable=False)

    op.execute("UPDATE package_sessions SET status = CASE WHEN action='consumed' THEN 'used' WHEN action='returned' THEN 'cancelled' ELSE action END WHERE status IS NULL")
    op.execute("UPDATE customer_packages SET purchase_price = price_paid WHERE purchase_price IS NULL")

    # Ensure existing tenants have default payment settings and a main unit.
    op.execute("""
        INSERT INTO tenant_payment_settings (
            id, tenant_id, require_deposit_by_default, default_deposit_type, default_deposit_value,
            require_deposit_for_first_appointment, require_deposit_after_no_show,
            manual_payment_instructions, pix_key, created_at, updated_at
        )
        SELECT gen_random_uuid(), t.id, false, 'none', 0, false, false, NULL, NULL, now(), now()
        FROM tenants t
        WHERE NOT EXISTS (
            SELECT 1 FROM tenant_payment_settings ps WHERE ps.tenant_id = t.id
        )
    """)
    op.execute("""
        INSERT INTO units (
            id, tenant_id, name, address, phone, whatsapp, email, timezone,
            is_main, is_active, deleted_at, created_at, updated_at
        )
        SELECT gen_random_uuid(), t.id, COALESCE(t.public_name, t.name), t.address, t.phone, t.whatsapp,
               t.email, t.timezone, true, true, NULL, now(), now()
        FROM tenants t
        WHERE NOT EXISTS (
            SELECT 1 FROM units u WHERE u.tenant_id = t.id AND u.is_main = true AND u.deleted_at IS NULL
        )
    """)


def downgrade() -> None:
    op.alter_column("customer_notes", "visibility", existing_type=sa.String(length=30), nullable=True)
    op.alter_column("customer_notes", "note", existing_type=sa.Text(), nullable=True)
    op.alter_column("customer_tag_links", "tenant_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
