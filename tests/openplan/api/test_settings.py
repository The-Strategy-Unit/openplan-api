import importlib

from openplan.api.v1 import settings


def test_current_app_version_with_envvar_set(monkeypatch):
    monkeypatch.setenv("CURRENT_APP_VERSION", "test")

    importlib.reload(settings)
    assert settings.CURRENT_APP_VERSION == "test"


def test_current_app_version_without_envvar_set(monkeypatch):
    monkeypatch.delenv("CURRENT_APP_VERSION", raising=False)

    importlib.reload(settings)
    assert settings.CURRENT_APP_VERSION == "dev"


def test_min_baseline_year_with_envvar_set(monkeypatch):
    monkeypatch.setenv("MIN_BASELINE_YEAR", "2022")

    importlib.reload(settings)
    assert settings.MIN_BASELINE_YEAR == 2022


def test_min_baseline_year_without_envvar_set(monkeypatch):
    monkeypatch.delenv("MIN_BASELINE_YEAR", raising=False)

    importlib.reload(settings)
    assert settings.MIN_BASELINE_YEAR == 2023


def test_max_baseline_year_with_envvar_set(monkeypatch):
    monkeypatch.setenv("MAX_BASELINE_YEAR", "2025")

    importlib.reload(settings)
    assert settings.MAX_BASELINE_YEAR == 2025


def test_max_baseline_year_without_envvar_set(monkeypatch):
    monkeypatch.delenv("MAX_BASELINE_YEAR", raising=False)

    importlib.reload(settings)
    assert settings.MAX_BASELINE_YEAR == 2024


def test_max_horizon_year_with_envvar_set(monkeypatch):
    monkeypatch.setenv("MAX_HORIZON_YEAR", "2050")

    importlib.reload(settings)
    assert settings.MAX_HORIZON_YEAR == 2050


def test_max_horizon_year_without_envvar_set(monkeypatch):
    monkeypatch.delenv("MAX_HORIZON_YEAR", raising=False)

    importlib.reload(settings)
    assert settings.MAX_HORIZON_YEAR == 2047


def test_blob_storage_account_with_envvar_set(monkeypatch):
    monkeypatch.setenv("BLOB_STORAGE_ACCOUNT", "test_account")

    importlib.reload(settings)
    assert settings.BLOB_STORAGE_ACCOUNT == "test_account"


def test_blob_storage_container_with_envvar_set(monkeypatch):
    monkeypatch.setenv("BLOB_STORAGE_CONTAINER", "test_container")

    importlib.reload(settings)
    assert settings.BLOB_STORAGE_CONTAINER == "test_container"
