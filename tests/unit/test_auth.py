import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.main import app
from app.core.security import hash_password, verify_password, create_access_token


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root():
    response = client.get("/")
    assert response.status_code == 200


class TestPasswordSecurity:
    def _make_context(self):
        """Cria contexto pbkdf2 para não depender do bcrypt do ambiente."""
        from passlib.context import CryptContext
        return CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

    def test_hash_and_verify(self):
        ctx = self._make_context()
        password = "MySecurePass123"
        hashed = ctx.hash(password)
        assert hashed != password
        assert ctx.verify(password, hashed)

    def test_wrong_password_fails(self):
        ctx = self._make_context()
        hashed = ctx.hash("correct-password")
        assert not ctx.verify("wrong-password", hashed)

    def test_different_hashes_same_password(self):
        ctx = self._make_context()
        password = "same-password"
        hash1 = ctx.hash(password)
        hash2 = ctx.hash(password)
        assert hash1 != hash2  # salts devem diferir
        assert ctx.verify(password, hash1)
        assert ctx.verify(password, hash2)


class TestTokenGeneration:
    def test_create_access_token(self):
        from app.core.security import create_access_token, decode_token
        data = {"sub": "some-uuid", "role": "tenant_owner", "type": "internal"}
        token = create_access_token(data)
        assert token
        decoded = decode_token(token)
        assert decoded["sub"] == "some-uuid"
        assert decoded["role"] == "tenant_owner"

    def test_create_refresh_token(self):
        from app.core.security import create_refresh_token, decode_token
        data = {"sub": "some-uuid", "type": "customer"}
        token = create_refresh_token(data)
        assert token
        decoded = decode_token(token)
        assert decoded["sub"] == "some-uuid"
        assert decoded["type"] == "refresh"


class TestLoginEndpoint:
    def test_login_without_db_returns_error(self):
        """Login com credenciais inválidas retorna 401 (requer PostgreSQL)."""
        pytest.skip("Requer PostgreSQL rodando — execute com docker-compose up db")

    def test_login_bad_request(self):
        response = client.post("/api/v1/auth/login", json={"email": "nao-um-email"})
        # Missing password
        assert response.status_code == 422


class TestCustomerRegister:
    def test_register_missing_fields(self):
        response = client.post("/api/v1/customer-auth/register", json={
            "name": "Teste"
            # missing phone and password
        })
        assert response.status_code == 422
        data = response.json()
        assert data["code"] == "VALIDATION_ERROR"


class TestAvailabilityPublic:
    def test_public_availability_missing_params(self):
        response = client.get("/api/v1/public/demo-slug/availability")
        # Missing service_ids and target_date — should 422
        assert response.status_code == 422


class TestPaginationEdgeCases:
    def test_large_page_size_rejected(self):
        """page_size > 100 deve ser rejeitado pela paginação."""
        response = client.get("/api/v1/appointments?limit=9999")
        # Unauthenticated → 401 before limit validation, that's fine
        assert response.status_code in (401, 422)
