"""add platform documents

Revision ID: 0016_add_platform_documents
Revises: 0015_add_owner_notifications
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016_add_platform_documents"
down_revision = "0015_add_owner_notifications"
branch_labels = None
depends_on = None


PLATFORM_DOCUMENT_TYPE_ENUM = postgresql.ENUM(
    "terms_of_service", "privacy_policy",
    "data_processing_agreement", "acceptable_use_policy",
    name="platform_document_type",
    create_type=False,
)


def upgrade() -> None:
    PLATFORM_DOCUMENT_TYPE_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "platform_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("document_type", PLATFORM_DOCUMENT_TYPE_ENUM, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("revision_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("document_type", name="uq_platform_documents_type"),
    )
    op.create_index("ix_platform_documents_document_type", "platform_documents", ["document_type"])


def downgrade() -> None:
    op.drop_table("platform_documents")
    PLATFORM_DOCUMENT_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
