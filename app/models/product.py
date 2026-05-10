from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class ProductCategory(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "product_categories"
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    tenant = relationship("Tenant", back_populates="product_categories")
    products = relationship("Product", back_populates="category")
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_product_categories_tenant_name"),)


class Product(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "products"
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("product_categories.id"), nullable=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    image_url = Column(String(500))
    track_stock = Column(Boolean, default=False, nullable=False)
    stock_quantity = Column(Integer, default=0, nullable=False)
    low_stock_threshold = Column(Integer, default=5, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    tenant = relationship("Tenant", back_populates="products")
    category = relationship("ProductCategory", back_populates="products")
    order_items = relationship("ProductOrderItem", back_populates="product")
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_products_price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_non_negative"),
    )


class ProductOrder(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "product_orders"
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id"), nullable=True, index=True)
    customer_name = Column(String(200))
    customer_phone = Column(String(30))
    status = Column(String(20), nullable=False, default="pending")  # pending | ready | completed | cancelled
    payment_status = Column(String(20), nullable=False, default="pending")  # pending | paid | refunded
    payment_method = Column(String(30))
    total = Column(Numeric(10, 2), nullable=False, default=0)
    notes = Column(Text)
    tenant = relationship("Tenant", back_populates="product_orders")
    items = relationship("ProductOrderItem", back_populates="order", cascade="all, delete-orphan")


class ProductOrderItem(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "product_order_items"
    order_id = Column(UUID(as_uuid=True), ForeignKey("product_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    product_name_snapshot = Column(String(200), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    subtotal = Column(Numeric(10, 2), nullable=False)
    order = relationship("ProductOrder", back_populates="items")
    product = relationship("Product", back_populates="order_items")
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),)
