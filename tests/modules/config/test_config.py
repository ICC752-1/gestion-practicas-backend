from app.core.config import Config


def test_cors_allowed_origins_parses_comma_separated_values() -> None:
    config = Config(
        CORS_ORIGINS=(
            "http://localhost:5173, "
            "http://127.0.0.1:5173,, "
            "https://frontend.example"
        ),
        _env_file=None,
    )

    assert config.CORS_ALLOWED_ORIGINS == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://frontend.example",
    ]


def test_cors_allowed_origins_has_local_vite_defaults() -> None:
    config = Config(_env_file=None)

    assert config.CORS_ALLOWED_ORIGINS == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_google_allowed_domains_parses_comma_separated_values() -> None:
    config = Config(
        GOOGLE_ALLOWED_DOMAINS="ufromail.cl, ufrontera.cl,,",
        _env_file=None,
    )

    assert config.GOOGLE_ALLOWED_DOMAIN_LIST == [
        "ufromail.cl",
        "ufrontera.cl",
    ]


def test_google_oauth_has_local_non_sensitive_defaults() -> None:
    config = Config(
        GOOGLE_CLIENT_ID="client-id",
        GOOGLE_CLIENT_SECRET="client-secret",
        _env_file=None,
    )

    assert config.GOOGLE_REDIRECT_URI == (
        "http://localhost:8000/auth/google/callback"
    )
    assert config.GOOGLE_ALLOWED_DOMAINS == "ufromail.cl,ufrontera.cl"
    assert config.GOOGLE_ALLOWED_DOMAIN_LIST == [
        "ufromail.cl",
        "ufrontera.cl",
    ]
    assert config.GOOGLE_FRONTEND_SUCCESS_URL == (
        "http://localhost:5173/auth/callback"
    )
    assert config.GOOGLE_FRONTEND_ERROR_URL == (
        "http://localhost:5173/auth/callback"
    )
    assert config.GOOGLE_COOKIE_SECURE is False


def test_google_canonical_settings_are_read_directly() -> None:
    config = Config(
        GOOGLE_CLIENT_ID="client-id",
        GOOGLE_CLIENT_SECRET="client-secret",
        GOOGLE_AUTH_URI="https://accounts.example/auth",
        GOOGLE_TOKEN_URI="https://accounts.example/token",
        GOOGLE_REDIRECT_URI="http://localhost:8000/auth/google/callback",
        GOOGLE_FRONTEND_SUCCESS_URL="http://localhost:5173/auth/callback",
        GOOGLE_FRONTEND_ERROR_URL="http://localhost:5173/auth/callback",
        GOOGLE_ALLOWED_DOMAINS="ufromail.cl",
        _env_file=None,
    )

    assert config.GOOGLE_CLIENT_ID == "client-id"
    assert config.GOOGLE_CLIENT_SECRET == "client-secret"
    assert config.GOOGLE_AUTH_URI == "https://accounts.example/auth"
    assert config.GOOGLE_TOKEN_URI == "https://accounts.example/token"
    assert config.GOOGLE_REDIRECT_URI == "http://localhost:8000/auth/google/callback"
    assert config.GOOGLE_FRONTEND_SUCCESS_URL == "http://localhost:5173/auth/callback"
    assert config.GOOGLE_FRONTEND_ERROR_URL == "http://localhost:5173/auth/callback"
