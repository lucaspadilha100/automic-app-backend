from sqlalchemy import Column, String, Boolean, Integer, Text, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class ProductCategory(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "product_categories"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    products = relationship("Product", back_populates="category")


class Product(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "products"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("product_categories.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    image_url = Column(String(500), nullable=True)
    track_stock = Column(Boolean, default=False, nullable=False)
    stock_quantity = Column(Integer, nullable=True)
    low_stock_threshold = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    category = relationship("ProductCategory", back_populates="products")


class ProductOrder(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "product_orders"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_name = Column(String(200), nullable=False)
    customer_phone = Column(String(30), nullable=True)
    items = Column(JSONB, nullable=False, default=list)
    total = Column(Numeric(10, 2), nullable=False, default=0)
    status = Column(String(20), default="pending", nullable=False)
    payment_status = Column(String(20), default="unpaid", nullable=False)
    payment_method = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
