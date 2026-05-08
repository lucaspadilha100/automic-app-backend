"""
Unit tests for platform_settings_service.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.platform_settings_service import platform_settings_service


class TestPlatformSettingsService:
    def test_get_or_create_returns_existing_row(self):
        existing = MagicMock(id=uuid4(), platform_name="AUTOMIC")
        db = MagicMock()
        db.query.return_value.first.return_value = existing

        result = platform_settings_service.get_or_create(db)

        assert result is existing
        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_get_or_create_creates_when_missing(self):
        db = MagicMock()
        db.query.return_value.first.return_value = None

        # Make refresh do nothing — the model already has defaults via __init__
        def _refresh_noop(obj):
            pass
        db.refresh.side_effect = _refresh_noop

        result = platform_settings_service.get_or_create(db)

        # Should have created a row, added/committed/refreshed
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()
        assert result is not None
        # is_singleton must be True
        added_obj = db.add.call_args[0][0]
        assert added_obj.is_singleton is True

    def test_update_applies_partial_changes(self):
        existing = MagicMock(
            id=uuid4(),
            platform_name="AUTOMIC",
            support_email=None,
        )
        db = MagicMock()
        db.query.return_value.first.return_value = existing

        with patch("app.services.platform_settings_service.audit_service") as audit_mock:
            result = platform_settings_service.update(
                db=db,
                data={"support_email": "support@automic.tech"},
                user_id=uuid4(),
                ip_address="127.0.0.1",
                user_agent="pytest",
            )

        # The update should have been applied
        assert result.support_email == "support@automic.tech"
        # platform_name should remain untouched (not in data)
        assert result.platform_name == "AUTOMIC"
        # Audit should be invoked
        audit_mock.log.assert_called_once()
        kwargs = audit_mock.log.call_args.kwargs
        assert kwargs["action"] == "platform_settings.update"
        assert kwargs["entity_type"] == "platform_settings"
        assert kwargs["tenant_id"] is None  # platform-level

    def test_update_swallows_audit_failures(self):
        existing = MagicMock(id=uuid4(), platform_name="AUTOMIC")
        db = MagicMock()
        db.query.return_value.first.return_value = existing

        with patch("app.services.platform_settings_service.audit_service") as audit_mock:
            audit_mock.log.side_effect = RuntimeError("audit DB down")

            # Must not raise
            result = platform_settings_service.update(
                db=db,
                data={"platform_name": "AUTOMIC.TECH"},
                user_id=None,
                ip_address=None,
                user_agent=None,
            )
        assert result.platform_name == "AUTOMIC.TECH"
