from app.core.database.database import engine, get_db
from app.core.config import config
import pytest
from sqlalchemy import text


# El AsyncEngine mantiene un pool asociado al event loop. Si cada test corre en un loop
# distinto (config por defecto de pytest-asyncio), puede aparecer:
# "Future attached to a different loop". Forzamos el mismo loop para este modulo.
pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_engine_connection() -> None:
    """Verifica que el engine conecta correctamente a PostgreSQL."""

    if not (config.POSTGRES_HOST and config.POSTGRES_DB and config.POSTGRES_USER):
        pytest.skip("POSTGRES_* env vars not configured for database tests")

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


async def test_get_db_session() -> None:
    """Verifica que get_db() genera una sesión funcional."""

    if not (config.POSTGRES_HOST and config.POSTGRES_DB and config.POSTGRES_USER):
        pytest.skip("POSTGRES_* env vars not configured for database tests")

    async for db in get_db():
        result = await db.execute(text("SELECT current_database(), current_user"))
        row = result.one()
        assert row[0]
        assert row[1]
        break
