"""
conftest.py — configura variáveis de ambiente mínimas para que os testes
possam importar app.main sem um PostgreSQL real disponível.
Usado exclusivamente no ambiente de CI/sandbox sem banco de dados.
"""
import os

# Deve ser setado ANTES de qualquer import que carregue settings
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-only")
os.environ.setdefault("ENVIRONMENT", "test")
