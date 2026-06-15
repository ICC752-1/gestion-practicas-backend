import pytest

from scripts.seed_demo import _ensure_not_production, _get_demo_password


def test_seed_demo_requires_password(monkeypatch) -> None:
    monkeypatch.delenv("DEMO_SEED_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="DEMO_SEED_PASSWORD is required"):
        _get_demo_password()


def test_seed_demo_rejects_short_password(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_SEED_PASSWORD", "short")

    with pytest.raises(RuntimeError, match="at least 8"):
        _get_demo_password()


def test_seed_demo_rejects_production_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeError, match="disabled in production"):
        _ensure_not_production()


def test_seed_demo_allows_local_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")

    _ensure_not_production()
