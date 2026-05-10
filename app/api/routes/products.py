from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
import uuid

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above, get_public_tenant_by_slug
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.product import ProductCategory, Product, ProductOrder

router = APIRouter(tags=["Produtos"])


# ---- Schemas ----

class ProductCategoryCreate(BaseModel):
    name: str
    sort_order: int = 0

class ProductCategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    sort_order: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal = Decimal("0")
    image_url: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    track_stock: bool = False
    stock_quantity: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    is_active: bool = True

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    image_url: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    track_stock: Optional[bool] = None
    stock_quantity: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    is_active: Optional[bool] = None

class ProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    price: Decimal
    image_url: Optional[str]
    category_id: Optional[uuid.UUID]
    category: Optional[ProductCategoryResponse]
    track_stock: bool
    stock_quantity: Optional[int]
    low_stock_threshold: Optional[int]
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class StockAdjustment(BaseModel):
    adjustment: int
    reason: Optional[str] = None

class OrderItemIn(BaseModel):
    product_id: uuid.UUID
    quantity: int

class ProductOrderCreate(BaseModel):
    customer_name: str
    customer_phone: Optional[str] = None
    items: List[OrderItemIn]
    notes: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: str

class OrderPaymentUpdate(BaseModel):
    payment_method: str

class ProductOrderResponse(BaseModel):
    id: uuid.UUID
    customer_name: str
    customer_phone: Optional[str]
    items: list
    total: Decimal
    status: str
    payment_status: str
    payment_method: Optional[str]
    notes: Optional[str]
    created_at: object
    model_config = ConfigDict(from_attributes=True)


# ---- Category routes ----

@router.get("/product-categories", response_model=List[ProductCategoryResponse])
def list_categories(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return db.query(ProductCategory).filter(ProductCategory.tenant_id == tenant.id).order_by(ProductCategory.sort_order).all()


@router.post("/product-categories", response_model=ProductCategoryResponse)
def create_category(
    payload: ProductCategoryCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    cat = ProductCategory(tenant_id=tenant.id, **payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/product-categories/{category_id}", response_model=ProductCategoryResponse)
def update_category(
    category_id: uuid.UUID,
    payload: ProductCategoryCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    cat = db.query(ProductCategory).filter(ProductCategory.id == category_id, ProductCategory.tenant_id == tenant.id).first()
    if not cat:
        raise NotFoundError("CATEGORY_NOT_FOUND", "Categoria não encontrada.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/product-categories/{category_id}")
def delete_category(
    category_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    cat = db.query(ProductCategory).filter(ProductCategory.id == category_id, ProductCategory.tenant_id == tenant.id).first()
    if not cat:
        raise NotFoundError("CATEGORY_NOT_FOUND", "Categoria não encontrada.")
    cat.is_active = False
    db.commit()
    return {"message": "Categoria desativada."}


# ---- Product routes ----

@router.get("/products", response_model=List[ProductResponse])
def list_products(
    category_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    q = db.query(Product).filter(Product.tenant_id == tenant.id)
    if category_id:
        q = q.filter(Product.category_id == category_id)
    if is_active is not None:
        q = q.filter(Product.is_active == is_active)
    return q.order_by(Product.name).all()


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    p = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant.id).first()
    if not p:
        raise NotFoundError("PRODUCT_NOT_FOUND", "Produto não encontrado.")
    return p


@router.post("/products", response_model=ProductResponse)
def create_product(
    payload: ProductCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    p = Product(tenant_id=tenant.id, **payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    p = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant.id).first()
    if not p:
        raise NotFoundError("PRODUCT_NOT_FOUND", "Produto não encontrado.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/products/{product_id}")
def delete_product(
    product_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    p = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant.id).first()
    if not p:
        raise NotFoundError("PRODUCT_NOT_FOUND", "Produto não encontrado.")
    p.is_active = False
    db.commit()
    return {"message": "Produto desativado."}


@router.post("/products/{product_id}/adjust-stock", response_model=ProductResponse)
def adjust_stock(
    product_id: uuid.UUID,
    payload: StockAdjustment,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    p = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant.id).first()
    if not p:
        raise NotFoundError("PRODUCT_NOT_FOUND", "Produto não encontrado.")
    p.stock_quantity = (p.stock_quantity or 0) + payload.adjustment
    db.commit()
    db.refresh(p)
    return p


# ---- Orders ----

@router.get("/product-orders", response_model=List[ProductOrderResponse])
def list_orders(
    status: Optional[str] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    q = db.query(ProductOrder).filter(ProductOrder.tenant_id == tenant.id)
    if status:
        q = q.filter(ProductOrder.status == status)
    return q.order_by(ProductOrder.created_at.desc()).all()


@router.post("/product-orders", response_model=ProductOrderResponse)
def create_order(
    payload: ProductOrderCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    items_data = []
    total = Decimal("0")
    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id, Product.tenant_id == tenant.id).first()
        if not product:
            raise NotFoundError("PRODUCT_NOT_FOUND", f"Produto {item.product_id} não encontrado.")
        item_total = product.price * item.quantity
        total += item_total
        items_data.append({
            "product_id": str(item.product_id),
            "product_name": product.name,
            "quantity": item.quantity,
            "unit_price": float(product.price),
        })
        if product.track_stock and product.stock_quantity is not None:
            product.stock_quantity -= item.quantity
    order = ProductOrder(
        tenant_id=tenant.id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        items=items_data,
        total=total,
        notes=payload.notes,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.patch("/product-orders/{order_id}/status", response_model=ProductOrderResponse)
def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    order = db.query(ProductOrder).filter(ProductOrder.id == order_id, ProductOrder.tenant_id == tenant.id).first()
    if not order:
        raise NotFoundError("ORDER_NOT_FOUND", "Pedido não encontrado.")
    order.status = payload.status
    db.commit()
    db.refresh(order)
    return order


@router.patch("/product-orders/{order_id}/payment", response_model=ProductOrderResponse)
def update_order_payment(
    order_id: uuid.UUID,
    payload: OrderPaymentUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    order = db.query(ProductOrder).filter(ProductOrder.id == order_id, ProductOrder.tenant_id == tenant.id).first()
    if not order:
        raise NotFoundError("ORDER_NOT_FOUND", "Pedido não encontrado.")
    order.payment_status = "paid"
    order.payment_method = payload.payment_method
    db.commit()
    db.refresh(order)
    return order


# ---- Public endpoint ----

@router.get("/public/{slug}/products", response_model=List[ProductResponse])
def public_list_products(slug: str, db: Session = Depends(get_db)):
    tenant = get_public_tenant_by_slug(slug, db)
    return db.query(Product).filter(Product.tenant_id == tenant.id, Product.is_active == True).order_by(Product.name).all()
