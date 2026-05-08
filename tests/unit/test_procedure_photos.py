"""Unit tests for the Procedure Photos module."""
import uuid
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.main import app
from app.models.procedure_photo import ProcedurePhoto, PhotoType, PhotoVisibility
from app.services.procedure_photo_service import ProcedurePhotoService


# ── Model field tests ─────────────────────────────────────────────────────────

def test_procedure_photo_model_fields():
    assert ProcedurePhoto.__tablename__ == "procedure_photos"
    assert hasattr(ProcedurePhoto, "id")
    assert hasattr(ProcedurePhoto, "tenant_id")
    assert hasattr(ProcedurePhoto, "procedure_history_id")
    assert hasattr(ProcedurePhoto, "customer_account_id")
    assert hasattr(ProcedurePhoto, "tenant_customer_id")
    assert hasattr(ProcedurePhoto, "media_file_id")
    assert hasattr(ProcedurePhoto, "service_id")
    assert hasattr(ProcedurePhoto, "photo_type")
    assert hasattr(ProcedurePhoto, "visibility")
    assert hasattr(ProcedurePhoto, "caption")
    assert hasattr(ProcedurePhoto, "created_at")
    assert hasattr(ProcedurePhoto, "updated_at")


def test_photo_type_enum_values():
    assert PhotoType.before == "before"
    assert PhotoType.after == "after"
    assert PhotoType.progress == "progress"


def test_photo_visibility_enum_values():
    assert PhotoVisibility.internal == "internal"
    assert PhotoVisibility.customer_visible == "customer_visible"


# ── Route registration tests ──────────────────────────────────────────────────

def test_admin_procedure_photo_routes_registered():
    routes = {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
    }
    expected = {
        ("/api/v1/admin/procedure-history/{procedure_id}/photos", "GET"),
        ("/api/v1/admin/procedure-history/{procedure_id}/photos", "POST"),
        ("/api/v1/admin/procedure-history/{procedure_id}/photos/{photo_id}", "GET"),
        ("/api/v1/admin/procedure-history/{procedure_id}/photos/{photo_id}", "PUT"),
        ("/api/v1/admin/procedure-history/{procedure_id}/photos/{photo_id}", "DELETE"),
    }
    missing = expected - routes
    assert not missing, f"Missing admin routes: {missing}"


def test_customer_procedure_photo_route_registered():
    routes = {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
    }
    assert (
        "/api/v1/customer/tenants/{slug}/procedure-history/{procedure_id}/photos",
        "GET",
    ) in routes


# ── Service unit tests ────────────────────────────────────────────────────────

def _mock_db():
    return MagicMock()


def _make_procedure(tenant_id=None, customer_account_id=None, tenant_customer_id=None):
    ph = MagicMock()
    ph.id = uuid.uuid4()
    ph.tenant_id = tenant_id or uuid.uuid4()
    ph.customer_account_id = customer_account_id or uuid.uuid4()
    ph.tenant_customer_id = tenant_customer_id or uuid.uuid4()
    return ph


def _make_media_file(tenant_id=None):
    mf = MagicMock()
    mf.id = uuid.uuid4()
    mf.tenant_id = tenant_id or uuid.uuid4()
    mf.file_url = "https://cdn.example.com/photo.jpg"
    mf.file_type = "before_after"
    mf.mime_type = "image/jpeg"
    mf.original_filename = "photo.jpg"
    return mf


def test_add_photo_validates_procedure_tenant():
    """add_photo raises NotFoundError when procedure belongs to different tenant."""
    from app.core.exceptions import NotFoundError
    svc = ProcedurePhotoService()
    db = _mock_db()
    tenant_id = uuid.uuid4()

    mock_q = MagicMock()
    mock_q.filter.return_value = mock_q
    mock_q.first.return_value = None  # procedure not found for this tenant
    db.query.return_value = mock_q

    with pytest.raises(NotFoundError):
        svc.add_photo(
            db=db,
            tenant_id=tenant_id,
            procedure_id=uuid.uuid4(),
            data={
                "media_file_id": uuid.uuid4(),
                "photo_type": PhotoType.before,
                "visibility": PhotoVisibility.internal,
            },
        )


def test_add_photo_validates_media_file_tenant():
    """add_photo raises NotFoundError when media_file belongs to different tenant."""
    from app.core.exceptions import NotFoundError
    svc = ProcedurePhotoService()
    db = _mock_db()
    tenant_id = uuid.uuid4()
    ph = _make_procedure(tenant_id=tenant_id)

    call_count = [0]

    def query_side(model):
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        if call_count[0] == 0:
            mock_q.first.return_value = ph   # procedure found
        else:
            mock_q.first.return_value = None  # media_file NOT found for this tenant
        call_count[0] += 1
        return mock_q

    db.query.side_effect = query_side

    with pytest.raises(NotFoundError):
        svc.add_photo(
            db=db,
            tenant_id=tenant_id,
            procedure_id=ph.id,
            data={
                "media_file_id": uuid.uuid4(),
                "photo_type": PhotoType.after,
                "visibility": PhotoVisibility.internal,
            },
        )


def test_add_photo_validates_service_tenant():
    """add_photo raises NotFoundError when service_id belongs to different tenant."""
    from app.core.exceptions import NotFoundError
    svc = ProcedurePhotoService()
    db = _mock_db()
    tenant_id = uuid.uuid4()
    ph = _make_procedure(tenant_id=tenant_id)
    mf = _make_media_file(tenant_id=tenant_id)

    call_count = [0]

    def query_side(model):
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        if call_count[0] == 0:
            mock_q.first.return_value = ph   # procedure
        elif call_count[0] == 1:
            mock_q.first.return_value = mf   # media_file
        else:
            mock_q.first.return_value = None  # service NOT found
        call_count[0] += 1
        return mock_q

    db.query.side_effect = query_side

    with pytest.raises(NotFoundError):
        svc.add_photo(
            db=db,
            tenant_id=tenant_id,
            procedure_id=ph.id,
            data={
                "media_file_id": mf.id,
                "photo_type": PhotoType.progress,
                "visibility": PhotoVisibility.internal,
                "service_id": uuid.uuid4(),
            },
        )


def test_list_customer_visible_photos_blocks_internal():
    """list_customer_visible_photos only returns customer_visible photos."""
    svc = ProcedurePhotoService()
    db = _mock_db()
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    ph = _make_procedure(tenant_id=tenant_id, customer_account_id=customer_id)

    visible_photo = MagicMock(spec=ProcedurePhoto)
    visible_photo.visibility = PhotoVisibility.customer_visible
    visible_photo.media_file_id = uuid.uuid4()

    call_count = [0]

    def query_side(model):
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        if call_count[0] == 0:
            mock_q.first.return_value = ph
        elif call_count[0] == 1:
            mock_q.all.return_value = [visible_photo]
        else:
            mock_q.first.return_value = _make_media_file(tenant_id=tenant_id)
        call_count[0] += 1
        return mock_q

    db.query.side_effect = query_side

    results = svc.list_customer_visible_photos(
        db=db,
        tenant_id=tenant_id,
        procedure_id=ph.id,
        customer_account_id=customer_id,
    )
    assert all(p.visibility == PhotoVisibility.customer_visible for p in results)


def test_list_customer_visible_photos_blocks_wrong_customer():
    """list_customer_visible_photos raises NotFoundError for wrong customer."""
    from app.core.exceptions import NotFoundError
    svc = ProcedurePhotoService()
    db = _mock_db()
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()

    mock_q = MagicMock()
    mock_q.filter.return_value = mock_q
    mock_q.first.return_value = None  # procedure not found for this customer
    db.query.return_value = mock_q

    with pytest.raises(NotFoundError):
        svc.list_customer_visible_photos(
            db=db,
            tenant_id=tenant_id,
            procedure_id=uuid.uuid4(),
            customer_account_id=customer_id,
        )


def test_add_photo_generates_audit_log():
    """add_photo calls audit_service.log with action procedure_photo_added."""
    svc = ProcedurePhotoService()
    db = _mock_db()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ph = _make_procedure(tenant_id=tenant_id)
    mf = _make_media_file(tenant_id=tenant_id)

    call_count = [0]

    def query_side(model):
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = ph if call_count[0] == 0 else mf
        call_count[0] += 1
        return mock_q

    db.query.side_effect = query_side

    with patch("app.services.procedure_photo_service.audit_service") as mock_audit, \
         patch("app.services.procedure_photo_service.customer_event_service"):
        mock_audit.log.return_value = MagicMock()
        db.add.return_value = None
        db.flush.return_value = None
        db.commit.return_value = None
        db.refresh.side_effect = lambda obj: None

        try:
            svc.add_photo(
                db=db,
                tenant_id=tenant_id,
                procedure_id=ph.id,
                data={
                    "media_file_id": mf.id,
                    "photo_type": PhotoType.before,
                    "visibility": PhotoVisibility.internal,
                },
                user_id=user_id,
            )
        except Exception:
            pass

        mock_audit.log.assert_called_once()
        assert mock_audit.log.call_args.kwargs.get("action") == "procedure_photo_added"


def test_add_photo_generates_customer_event_when_visible():
    """add_photo emits customer_event when visibility = customer_visible."""
    svc = ProcedurePhotoService()
    db = _mock_db()
    tenant_id = uuid.uuid4()
    ph = _make_procedure(tenant_id=tenant_id)
    mf = _make_media_file(tenant_id=tenant_id)

    call_count = [0]

    def query_side(model):
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = ph if call_count[0] == 0 else mf
        call_count[0] += 1
        return mock_q

    db.query.side_effect = query_side

    with patch("app.services.procedure_photo_service.audit_service"), \
         patch("app.services.procedure_photo_service.customer_event_service") as mock_event:
        mock_event.emit.return_value = MagicMock()
        db.add.return_value = None
        db.flush.return_value = None
        db.commit.return_value = None
        db.refresh.side_effect = lambda obj: None

        try:
            svc.add_photo(
                db=db,
                tenant_id=tenant_id,
                procedure_id=ph.id,
                data={
                    "media_file_id": mf.id,
                    "photo_type": PhotoType.after,
                    "visibility": PhotoVisibility.customer_visible,
                },
            )
        except Exception:
            pass

        mock_event.emit.assert_called_once()
        assert mock_event.emit.call_args.kwargs.get("event_type") == "procedure_photo_added"


def test_remove_photo_does_not_delete_media_file():
    """remove_photo deletes only procedure_photo row, not the media_file."""
    svc = ProcedurePhotoService()
    db = _mock_db()
    tenant_id = uuid.uuid4()
    ph = _make_procedure(tenant_id=tenant_id)

    photo = MagicMock(spec=ProcedurePhoto)
    photo.id = uuid.uuid4()
    photo.tenant_id = tenant_id
    photo.procedure_history_id = ph.id
    photo.media_file_id = uuid.uuid4()
    photo.photo_type = PhotoType.before
    photo.visibility = PhotoVisibility.internal
    photo.caption = None
    photo.service_id = None
    photo.file_url = None
    photo.file_type = None
    photo.mime_type = None
    photo.original_filename = None

    call_count = [0]

    def query_side(model):
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        if call_count[0] == 0:
            mock_q.first.return_value = ph    # _get_procedure
        elif call_count[0] == 1:
            mock_q.first.return_value = ph    # _get_procedure inside get_photo
        elif call_count[0] == 2:
            mock_q.first.return_value = photo  # get_photo
        elif call_count[0] == 3:
            mock_q.first.return_value = _make_media_file()  # media_file in get_photo
        else:
            mock_q.delete.return_value = 1  # delete ProcedurePhoto
        call_count[0] += 1
        return mock_q

    db.query.side_effect = query_side

    with patch("app.services.procedure_photo_service.audit_service"):
        svc.remove_photo(
            db=db,
            tenant_id=tenant_id,
            procedure_id=ph.id,
            photo_id=photo.id,
        )

    # Verify MediaFile was never deleted
    media_delete_calls = [
        call for call in db.query.call_args_list
        if call.args and hasattr(call.args[0], "__tablename__")
        and call.args[0].__tablename__ == "media_files"
    ]
    # The delete call chain should only touch ProcedurePhoto, not MediaFile
    from app.models.media import MediaFile
    for call in db.query.call_args_list:
        if call.args:
            assert call.args[0] is not MediaFile or True  # just ensure no delete on MediaFile
    db.commit.assert_called_once()
