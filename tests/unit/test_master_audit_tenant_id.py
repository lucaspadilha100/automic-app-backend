"""Guards the tenant_id on audit writes from the master console.

audit_service.log takes (db, action, entity_type, entity_id, tenant_id=None, ...),
so passing the tenant as the fourth positional argument fills entity_id and leaves
tenant_id NULL. The per-tenant audit view filters strictly on tenant_id, so such a
row is written but can never be read back — the tenant's audit page just looks
empty. Nothing at runtime complains, which is why this is checked structurally.
"""
import ast
import pathlib

ROUTES = pathlib.Path(__file__).resolve().parents[2] / "app" / "api" / "routes"


def _audit_log_calls(path: pathlib.Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "log":
            if isinstance(func.value, ast.Name) and func.value.id == "audit_service":
                yield node


def test_master_audit_calls_set_tenant_id():
    offenders = []
    for path in sorted(ROUTES.glob("master_*.py")):
        for call in _audit_log_calls(path):
            keywords = {kw.arg for kw in call.keywords}
            if "tenant_id" not in keywords:
                offenders.append(f"{path.name}:{call.lineno}")
    assert not offenders, (
        "audit_service.log sem tenant_id= (o log não aparece na auditoria do tenant): "
        + ", ".join(offenders)
    )


def test_limit_overrides_preserve_explicit_nulls():
    """Clearing a limit must reach the database.

    Every field of LimitOverrideUpdate is Optional, so null is the only way to say
    "drop this override and fall back to the plan". exclude_none would discard
    exactly that, leaving a cleared field unsavable. Scoped to this one handler:
    other endpoints in the file use exclude_none deliberately for partial updates.
    """
    tree = ast.parse((ROUTES / "master_tenants.py").read_text())
    handlers = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and "limit_override" in n.name
    ]
    assert handlers, "handler de limit overrides não encontrado"
    dumps = [
        kw.value.value
        for handler in handlers
        for node in ast.walk(handler)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "model_dump"
        for kw in node.keywords
        if kw.arg in ("exclude_none", "exclude_unset") and isinstance(kw.value, ast.Constant)
        and kw.arg == "exclude_none" and kw.value.value is True
    ]
    assert not dumps, (
        "exclude_none descarta nulls explícitos; use exclude_unset para permitir limpar um limite"
    )
