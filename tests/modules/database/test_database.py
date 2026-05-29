from app.core.database.database import engine, get_db
from app.core.config import config
import pytest
from sqlalchemy import text


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


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_engine_connection())
    asyncio.run(test_get_db_session())
