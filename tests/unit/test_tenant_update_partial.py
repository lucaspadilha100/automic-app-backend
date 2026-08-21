"""Partial-update semantics for the master tenant endpoints.

The handlers dump with exclude_unset, so an omitted field is left untouched and an
explicit null clears an optional one. That distinction only holds if a blank can
never reach name, slug or timezone, which are NOT NULL in the model — and which a
blank string would satisfy at the database level while still breaking the tenant.
"""
import pytest
from pydantic import ValidationError

from app.schemas.tenant import TenantUpdate


def test_omitted_fields_stay_unset():
    """A partial payload must not carry defaults that would overwrite columns."""
    payload = TenantUpdate(name="Salão Novo")
    assert payload.model_dump(exclude_unset=True) == {"name": "Salão Novo"}


def test_explicit_null_clears_an_optional_field():
    """null is how the caller says "empty this" — it must survive the dump."""
    dumped = TenantUpdate(phone=None).model_dump(exclude_unset=True)
    assert dumped == {"phone": None}


@pytest.mark.parametrize("field", ["name", "slug", "timezone"])
@pytest.mark.parametrize("blank", [None, "", "   "])
def test_required_fields_reject_blanks(field, blank):
    with pytest.raises(ValidationError):
        TenantUpdate(**{field: blank})


@pytest.mark.parametrize("field", ["phone", "email", "address", "website"])
def test_optional_fields_accept_blanks(field):
    assert TenantUpdate(**{field: None}).model_dump(exclude_unset=True) == {field: None}


def test_required_fields_accept_real_values():
    payload = TenantUpdate(name="Salão X", slug="salao-x", timezone="America/Bahia")
    assert payload.model_dump(exclude_unset=True) == {
        "name": "Salão X", "slug": "salao-x", "timezone": "America/Bahia",
    }
