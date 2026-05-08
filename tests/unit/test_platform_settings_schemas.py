"""
Schema validation tests for platform_settings.
"""
import pytest
from pydantic import ValidationError

from app.schemas.platform_settings import PlatformSettingsUpdate


class TestPlatformSettingsUpdate:
    def test_accepts_valid_hex_colors(self):
        m = PlatformSettingsUpdate(primary_color="#22D3EE", secondary_color="#0F172A")
        assert m.primary_color == "#22D3EE"
        assert m.secondary_color == "#0F172A"

    def test_accepts_short_hex(self):
        m = PlatformSettingsUpdate(primary_color="#FFF")
        assert m.primary_color == "#FFF"

    def test_rejects_non_hex_color(self):
        with pytest.raises(ValidationError):
            PlatformSettingsUpdate(primary_color="cyan")

    def test_rejects_color_without_hash(self):
        with pytest.raises(ValidationError):
            PlatformSettingsUpdate(primary_color="22D3EE")

    def test_rejects_empty_platform_name(self):
        with pytest.raises(ValidationError):
            PlatformSettingsUpdate(platform_name="   ")

    def test_all_fields_optional(self):
        # Empty payload is valid — partial update may set nothing
        m = PlatformSettingsUpdate()
        assert m.platform_name is None

    def test_accepts_full_payload(self):
        m = PlatformSettingsUpdate(
            platform_name="AUTOMIC",
            platform_tagline="Sistemas inteligentes.",
            platform_legal_name="AUTOMIC.TECH LTDA",
            primary_color="#22D3EE",
            secondary_color="#0F172A",
            accent_color="#06B6D4",
            support_email="support@automic.tech",
            primary_domain="automic.tech",
            owner_notification_emails="leo@automic.tech, ops@automic.tech",
        )
        assert m.platform_name == "AUTOMIC"
        assert m.support_email == "support@automic.tech"
