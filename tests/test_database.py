from app.core.database import engine, get_db
from sqlalchemy import text


def test_engine_connection():
    """Verifica que el engine conecta correctamente a PostgreSQL."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("Engine conectado:", result.fetchone())


def test_get_db_session():
    """Verifica que get_db() genera una sesión funcional."""
    db = next(get_db())
    try:
        result = db.execute(text("SELECT current_database(), current_user"))
        row = result.fetchone()
        print(f"get_db() funciona — DB: {row[0]}, User: {row[1]}")
    finally:
        db.close()


if __name__ == "__main__":
    test_engine_connection()
    test_get_db_session()