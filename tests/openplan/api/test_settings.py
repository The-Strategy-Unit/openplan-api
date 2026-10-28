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
