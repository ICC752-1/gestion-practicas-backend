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
