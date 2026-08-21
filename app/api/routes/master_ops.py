"""
Master operations routes — trial expiration job and tenant health dashboard.

These complement /master/tenants by providing operational views and actions
that the AUTOMIC owner uses day-to-day.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_super_admin
from app.models.user import User
from app.models.tenant import Tenant
from app.models.product import Product
from app.models.supply import Supply
from app.models.task_run import TaskRunSource
from app.services.tenant_ops_service import tenant_ops_service
from app.services.task_run_service import task_run_service
from app.services.reminder_service import reminder_service

router = APIRouter(prefix="/master", tags=["Operações - Master"])


@router.get("/health/tenants")
def tenants_health(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Snapshot de saúde de todos os tenants (com churn risk)."""
    return tenant_ops_service.compute_tenant_health(db)


@router.post("/jobs/run-trial-expiration")
def run_trial_expiration(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Roda o job de expiração de trials manualmente.
    Idempotente — pode ser chamado várias vezes seguidas sem duplicar efeito.
    Cada execução é registrada em TaskRun.
    """
    with task_run_service.record(db, "expire_trials", TaskRunSource.manual) as ctx:
        result = tenant_ops_service.expire_trials(db)
        ctx.set_summary(result)
        return result


@router.post("/jobs/send-24h-reminders")
def run_24h_reminders(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Envia lembretes de agendamento 24h antes (idempotente).
    Designed to run hourly. Skips appointments that already have a sent log.
    """
    with task_run_service.record(db, "send_24h_reminders", TaskRunSource.manual) as ctx:
        result = reminder_service.send_24h_reminders(db)
        ctx.set_summary(result)
        return result


@router.post("/jobs/check-low-stock")
def check_low_stock(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Verifica produtos e insumos com estoque abaixo do limite configurado em todos os tenants ativos.
    Retorna um resumo com os itens em baixo estoque por tenant.
    """
    active_tenants = (
        db.query(Tenant)
        .filter(Tenant.status == "active", Tenant.deleted_at.is_(None))
        .all()
    )

    low_stock_products: List[Dict[str, Any]] = []
    low_stock_supplies: List[Dict[str, Any]] = []

    for tenant in active_tenants:
        products = (
            db.query(Product)
            .filter(
                Product.tenant_id == tenant.id,
                Product.track_stock.is_(True),
                Product.stock_quantity <= Product.low_stock_threshold,
                Product.is_active.is_(True),
                Product.deleted_at.is_(None),
            )
            .all()
        )
        for p in products:
            low_stock_products.append({
                "tenant_name": tenant.name,
                "product_name": p.name,
                "stock_quantity": p.stock_quantity,
                "low_stock_threshold": p.low_stock_threshold,
            })

        supplies = (
            db.query(Supply)
            .filter(
                Supply.tenant_id == tenant.id,
                Supply.track_stock.is_(True),
                Supply.stock_quantity <= Supply.low_stock_threshold,
                Supply.is_active.is_(True),
                Supply.deleted_at.is_(None),
            )
            .all()
        )
        for s in supplies:
            low_stock_supplies.append({
                "tenant_name": tenant.name,
                "supply_name": s.name,
                "stock_quantity": float(s.stock_quantity),
                "low_stock_threshold": float(s.low_stock_threshold),
            })

    return {
        "tenants_checked": len(active_tenants),
        "low_stock_products": low_stock_products,
        "low_stock_supplies": low_stock_supplies,
    }


@router.get("/ops/schema-state")
def schema_state(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Which migrations the database believes it has applied, and what it actually has.

    The migration history forked at 0021 into two chains that both create the
    products/supplies tables, so `alembic upgrade head` refuses to run. Repairing
    that safely depends on which chain this database actually followed, and the
    alembic_version table plus the presence of the disputed tables is the only
    way to tell from outside.
    """
    from sqlalchemy import text, inspect

    inspector = inspect(db.get_bind())
    tables = set(inspector.get_table_names())

    try:
        applied = sorted(r[0] for r in db.execute(text("SELECT version_num FROM alembic_version")))
    except Exception as exc:
        applied = f"não foi possível ler alembic_version: {type(exc).__name__}"

    def columns(table: str) -> list:
        return sorted(c["name"] for c in inspector.get_columns(table)) if table in tables else []

    return {
        "alembic_version": applied,
        # Only the ecommerce chain creates these two; their presence says which
        # chain ran. The plural spelling belongs to the duplicate chain.
        "chain_markers": {
            "appointment_supply_usage (correto, model)": "appointment_supply_usage" in tables,
            "appointment_supply_usages (duplicata)": "appointment_supply_usages" in tables,
            "product_order_items (só na cadeia correta)": "product_order_items" in tables,
        },
        "shared_tables_present": {
            t: t in tables for t in ("products", "product_categories", "product_orders", "supplies")
        },
        "branch_b_changes_applied": {
            "tenant_settings.page_sections": "page_sections" in columns("tenant_settings"),
            "payments.registered_by_user_id": "registered_by_user_id" in columns("payments"),
        },
        "plans.allow_page_customization": "allow_page_customization" in columns("plans"),
    }
