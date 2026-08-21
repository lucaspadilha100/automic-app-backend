import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.core.config import settings

# The production defaults are sized for serverless, where many short-lived
# instances each hold their own pool and a big one would exhaust the database's
# connection limit. On an always-on host the opposite is true: one long-lived
# process serves every request, so a larger pool means requests reuse warm
# connections instead of queueing. Override with DB_POOL_SIZE / DB_MAX_OVERFLOW.
_pool_size = settings.DB_POOL_SIZE or (2 if settings.is_production else 10)
_max_overflow = settings.DB_MAX_OVERFLOW or (3 if settings.is_production else 20)

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    pool_recycle=300,
    echo=settings.DEBUG,
    connect_args={"connect_timeout": 5},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def scrub_credentials(value: object, limit: int = 300) -> str:
    """Render an error (or any text) with connection-string passwords removed.

    Driver errors frequently echo the URL they failed to connect to, so anything
    derived from them has to be laundered before it reaches a response body.
    """
    return re.sub(r"://[^@/\s]+@", "://***@", str(value))[:limit]


def describe_target() -> dict:
    """Where the app is pointed, with credentials stripped.

    DATABASE_URL is normally write-only in a hosting dashboard, which leaves no
    way to confirm which database a deployment is actually talking to. This
    exposes the harmless half of the URL — never the user or the password — and
    pulls out the Supabase project ref, which is encoded either in the direct
    host (``db.<ref>.supabase.co``) or in the pooler username (``postgres.<ref>``).
    """
    url = engine.url
    host = url.host or ""
    info: dict = {"host": host, "port": url.port, "database": url.database}

    ref = None
    if host.startswith("db.") and host.endswith(".supabase.co"):
        ref = host.split(".")[1]
    elif "pooler.supabase.com" in host and url.username and "." in url.username:
        ref = url.username.split(".", 1)[1]
    if ref:
        info["supabase_project_ref"] = ref
        info["supabase_dashboard"] = f"https://supabase.com/dashboard/project/{ref}"

    region = re.search(r"aws-\d+-([a-z]{2}-[a-z]+-\d)", host)
    if region:
        info["region"] = region.group(1)

    info["pooled"] = url.port == 6543 or "pooler." in host
    return info


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
