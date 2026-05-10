from typing import List, Optional
from decimal import Decimal
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import (
    get_current_user, require_active_tenant, require_manager_or_above,
    require_receptionist_or_above, require_feature, get_public_tenant_by_slug,
)
from app.core.exceptions import NotFoundError, ConflictError, ValidationError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.product import Product, ProductCategory, ProductOrder, ProductOrderItem
from app.services.audit_service import audit_service


# ---- Schemas ----

class ProductCategoryCreate(BaseModel):
    name: str
    sort_order: int = 0
    is_active: bool = True


class ProductCategoryResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal = Decimal("0")
    category_id: Optional[uuid.UUID] = None
    image_url: Optional[str] = None
    track_stock: bool = False
    stock_quantity: int = 0
    low_stock_threshold: int = 5
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    category_id: Optional[uuid.UUID] = None
    image_url: Optional[str] = None
    track_stock: Optional[bool] = None
    stock_quantity: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    category_id: Optional[uuid.UUID]
    name: str
    description: Optional[str]
    price: Decimal
    image_url: Optional[str]
    track_stock: bool
    stock_quantity: int
    low_stock_threshold: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StockAdjustPayload(BaseModel):
    adjustment: int
    reason: str


class OrderItemIn(BaseModel):
    product_id: uuid.UUID
    quantity: int = 1


class ProductOrderCreate(BaseModel):
    items: List[OrderItemIn]
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_account_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name_snapshot: str
    unit_price: Decimal
    quantity: int
    subtotal: Decimal

    class Config:
        from_attributes = True


class ProductOrderResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    customer_account_id: Optional[uuid.UUID]
    customer_name: Optional[str]
    customer_phone: Optional[str]
    status: str
    payment_status: str
    payment_method: Optional[str]
    total: Decimal
    notes: Optional[str]
    items: List[OrderItemResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    status: str


class OrderPaymentUpdate(BaseModel):
    payment_method: str


# ---- Routers ----

router = APIRouter(
    prefix="/products",
    tags=["Ecommerce"],
    dependencies=[Depends(require_feature("ecommerce"))],
)

public_router = APIRouter(prefix="/public", tags=["Public"])

categories_router = APIRouter(
    prefix="/product-categories",
    tags=["Ecommerce"],
    dependencies=[Depends(require_feature("ecommerce"))],
)

orders_router = APIRouter(
    prefix="/product-orders",
    tags=["Ecommerce"],
    dependencies=[Depends(require_feature("ecommerce"))],
)


# ---- Categories ----

@categories_router.get("", response_model=List[ProductCategoryResponse])
def list_categories(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(ProductCategory)
        .filter(ProductCategory.tenant_id == tenant.id, ProductCategory.is_active == True)
        .order_by(ProductCategory.sort_order)
        .all()
    )


@categories_router.post("", response_model=ProductCategoryResponse, status_code=201)
def create_category(
    payload: ProductCategoryCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    exists = db.query(ProductCategory).filter(
        ProductCategory.tenant_id == tenant.id,
        ProductCategory.name == payload.name,
    ).first()
    if exists:
        raise ConflictError("CATEGORY_NAME_TAKEN", "Já existe uma categoria com este nome.")
    cat = ProductCategory(tenant_id=tenant.id, **payload.model_dump())
    db.add(cat)
    db.flush()
    audit_service.log(db, "product_category_created", "product_category", cat.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(cat)
    return cat


@categories_router.put("/{category_id}", response_model=ProductCategoryResponse)
def update_category(
    category_id: uuid.UUID,
    payload: ProductCategoryCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    cat = db.query(ProductCategory).filter(
        ProductCategory.id == category_id, ProductCategory.tenant_id == tenant.id
    ).first()
    if not cat:
        raise NotFoundError("CATEGORY_NOT_FOUND", "Categoria não encontrada.")
    for k, v in payload.model_dump().items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


@categories_router.delete("/{category_id}")
def delete_category(
    category_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    cat = db.query(ProductCategory).filter(
        ProductCategory.id == category_id, ProductCategory.tenant_id == tenant.id
    ).first()
    if not cat:
        raise NotFoundError("CATEGORY_NOT_FOUND", "Categoria não encontrada.")
    cat.is_active = False
    db.commit()
    return {"message": "Categoria desativada."}


# ---- Products ----

@router.get("", response_model=List[ProductResponse])
def list_products(
    category_id: Optional[uuid.UUID] = None,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Product).filter(Product.tenant_id == tenant.id, Product.deleted_at.is_(None))
    if active_only:
        q = q.filter(Product.is_active == True)
    if category_id:
        q = q.filter(Product.category_id == category_id)
    return q.offset(skip).limit(limit).all()


@router.post("", response_model=ProductResponse, status_code=201)
def create_product(
    payload: ProductCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    if payload.category_id:
        cat = db.query(ProductCategory).filter(
            ProductCategory.id == payload.category_id, ProductCategory.tenant_id == tenant.id
        ).first()
        if not cat:
            raise NotFoundError("CATEGORY_NOT_FOUND", "Categoria não encontrada.")
    product = Product(tenant_id=tenant.id, **payload.model_dump())
    db.add(product)
    db.flush()
    audit_service.log(db, "product_created", "product", product.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(
        Product.id == product_id, Product.tenant_id == tenant.id, Product.deleted_at.is_(None)
    ).first()
    if not product:
        raise NotFoundError("PRODUCT_NOT_FOUND", "Produto não encontrado.")
    return product


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(
        Product.id == product_id, Product.tenant_id == tenant.id, Product.deleted_at.is_(None)
    ).first()
    if not product:
        raise NotFoundError("PRODUCT_NOT_FOUND", "Produto não encontrado.")
    if payload.category_id is not None:
        cat = db.query(ProductCategory).filter(
            ProductCategory.id == payload.category_id, ProductCategory.tenant_id == tenant.id
        ).first()
        if not cat:
            raise NotFoundError("CATEGORY_NOT_FOUND", "Categoria não encontrada.")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(product, k, v)
    audit_service.log(db, "product_updated", "product", product.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}")
def delete_product(
    product_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(
        Product.id == product_id, Product.tenant_id == tenant.id, Product.deleted_at.is_(None)
    ).first()
    if not product:
        raise NotFoundError("PRODUCT_NOT_FOUND", "Produto não encontrado.")
    product.deleted_at = datetime.now(timezone.utc)
    product.is_active = False
    audit_service.log(db, "product_deleted", "product", product.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Produto removido."}


@router.post("/{product_id}/adjust-stock", response_model=ProductResponse)
def adjust_stock(
    product_id: uuid.UUID,
    payload: StockAdjustPayload,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(
        Product.id == product_id, Product.tenant_id == tenant.id, Product.deleted_at.is_(None)
    ).first()
    if not product:
        raise NotFoundError("PRODUCT_NOT_FOUND", "Produto não encontrado.")
    new_qty = product.stock_quantity + payload.adjustment
    if new_qty < 0:
        raise ValidationError("Estoque insuficiente para este ajuste.")
    product.stock_quantity = new_qty
    audit_service.log(db, "product_stock_adjusted", "product", product.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(product)
    return product


# ---- Orders ----

@orders_router.get("", response_model=List[ProductOrderResponse])
def list_orders(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(ProductOrder).filter(ProductOrder.tenant_id == tenant.id)
    if status:
        q = q.filter(ProductOrder.status == status)
    return q.order_by(ProductOrder.created_at.desc()).offset(skip).limit(limit).all()


@orders_router.post("", response_model=ProductOrderResponse, status_code=201)
def create_order(
    payload: ProductOrderCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    if not payload.items:
        raise ValidationError("O pedido deve conter ao menos um item.")

    order_items = []
    total = Decimal("0")

    for item_in in payload.items:
        product = db.query(Product).filter(
            Product.id == item_in.product_id,
            Product.tenant_id == tenant.id,
            Product.deleted_at.is_(None),
            Product.is_active == True,
        ).first()
        if not product:
            raise NotFoundError("PRODUCT_NOT_FOUND", f"Produto {item_in.product_id} não encontrado.")
        if product.track_stock and product.stock_quantity < item_in.quantity:
            raise ValidationError(f"Estoque insuficiente para o produto '{product.name}'.")
        subtotal = Decimal(str(product.price)) * item_in.quantity
        total += subtotal
        order_items.append((product, item_in.quantity, subtotal))

    order = ProductOrder(
        tenant_id=tenant.id,
        customer_account_id=payload.customer_account_id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        notes=payload.notes,
        total=total,
    )
    db.add(order)
    db.flush()

    for product, quantity, subtotal in order_items:
        item = ProductOrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name_snapshot=product.name,
            unit_price=product.price,
            quantity=quantity,
            subtotal=subtotal,
        )
        db.add(item)
        if product.track_stock:
            product.stock_quantity -= quantity

    audit_service.log(db, "product_order_created", "product_order", order.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(order)
    return order


@orders_router.patch("/{order_id}/status", response_model=ProductOrderResponse)
def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    order = db.query(ProductOrder).filter(
        ProductOrder.id == order_id, ProductOrder.tenant_id == tenant.id
    ).first()
    if not order:
        raise NotFoundError("ORDER_NOT_FOUND", "Pedido não encontrado.")
    valid_statuses = {"pending", "ready", "completed", "cancelled"}
    if payload.status not in valid_statuses:
        raise ValidationError(f"Status inválido. Valores permitidos: {', '.join(valid_statuses)}.")
    order.status = payload.status
    audit_service.log(db, "product_order_status_updated", "product_order", order.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(order)
    return order


@orders_router.patch("/{order_id}/payment", response_model=ProductOrderResponse)
def update_order_payment(
    order_id: uuid.UUID,
    payload: OrderPaymentUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    order = db.query(ProductOrder).filter(
        ProductOrder.id == order_id, ProductOrder.tenant_id == tenant.id
    ).first()
    if not order:
        raise NotFoundError("ORDER_NOT_FOUND", "Pedido não encontrado.")
    order.payment_status = "paid"
    order.payment_method = payload.payment_method
    audit_service.log(db, "product_order_paid", "product_order", order.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(order)
    return order


# ---- Public storefront ----

@public_router.get("/{slug}/products", response_model=List[ProductResponse])
def public_list_products(
    slug: str,
    category_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
):
    tenant = get_public_tenant_by_slug(slug, db)
    q = db.query(Product).filter(
        Product.tenant_id == tenant.id,
        Product.deleted_at.is_(None),
        Product.is_active == True,
    )
    if category_id:
        q = q.filter(Product.category_id == category_id)
    return q.all()
