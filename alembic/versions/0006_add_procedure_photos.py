"""add procedure photos

Revision ID: 0006_add_procedure_photos
Revises: 0005_add_terms_and_acceptances
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_add_procedure_photos"
down_revision = "0005_add_terms_and_acceptances"
branch_labels = None
depends_on = None

PHOTO_TYPE_ENUM = postgresql.ENUM(
    "before", "after", "progress",
    name="photo_type_enum",
    create_type=False,
)
PHOTO_VISIBILITY_ENUM = postgresql.ENUM(
    "internal", "customer_visible",
    name="photo_visibility_enum",
    create_type=False,
)


def upgrade() -> None:
    PHOTO_TYPE_ENUM.create(op.get_bind(), checkfirst=True)
    PHOTO_VISIBILITY_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "procedure_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("procedure_history_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("procedure_history.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("customer_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tenant_customer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenant_customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("media_file_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("media_files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("services.id", ondelete="SET NULL"), nullable=True),
        sa.Column("photo_type", PHOTO_TYPE_ENUM, nullable=False),
        sa.Column("visibility", PHOTO_VISIBILITY_ENUM, nullable=False, server_default="internal"),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("ix_procedure_photos_tenant_id", "procedure_photos", ["tenant_id"])
    op.create_index("ix_procedure_photos_procedure_history_id", "procedure_photos", ["procedure_history_id"])
    op.create_index("ix_procedure_photos_customer_account_id", "procedure_photos", ["customer_account_id"])
    op.create_index("ix_procedure_photos_tenant_customer_id", "procedure_photos", ["tenant_customer_id"])
    op.create_index("ix_procedure_photos_media_file_id", "procedure_photos", ["media_file_id"])
    op.create_index("ix_procedure_photos_photo_type", "procedure_photos", ["photo_type"])
    op.create_index("ix_procedure_photos_visibility", "procedure_photos", ["visibility"])
    op.create_index(
        "ix_procedure_photos_tenant_procedure_visibility",
        "procedure_photos",
        ["tenant_id", "procedure_history_id", "visibility"],
    )


def downgrade() -> None:
    op.drop_table("procedure_photos")
    PHOTO_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
    PHOTO_VISIBILITY_ENUM.drop(op.get_bind(), checkfirst=True)
