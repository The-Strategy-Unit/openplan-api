from dataclasses import dataclass
import os

CURRENT_APP_VERSION = "dev"


@dataclass(frozen=True)
class StorageSettings:
    account_name: str
    container_name: str

    @property
    def account_url(self) -> str:
        return f"https://{self.account_name}.blob.core.windows.net"


def get_storage_settings() -> StorageSettings:
    names = ("OPENPLAN_STORAGE_ACCOUNT_NAME", "OPENPLAN_STORAGE_CONTAINER_NAME")
    values = {name: os.environ.get(name, "").strip() for name in names}
    missing = [name for name in names if not values[name]]
    if missing:
        raise RuntimeError("Missing required storage environment variables: " + ", ".join(missing))
    return StorageSettings(
        account_name=values["OPENPLAN_STORAGE_ACCOUNT_NAME"],
        container_name=values["OPENPLAN_STORAGE_CONTAINER_NAME"],
    )


@dataclass(frozen=True)
class CacheSettings:
    ttl_seconds: int = 300
    max_bytes: int = 128 * 1024 * 1024


def get_cache_settings() -> CacheSettings:
    defaults = CacheSettings()
    values = {}
    for name, default in (
        ("OPENPLAN_CACHE_TTL_SECONDS", defaults.ttl_seconds),
        ("OPENPLAN_CACHE_MAX_BYTES", defaults.max_bytes),
    ):
        raw = os.environ.get(name, str(default))
        if not raw.isascii() or not raw.isdecimal():
            raise RuntimeError(f"{name} must be a non-negative integer")
        values[name] = int(raw)
    return CacheSettings(
        ttl_seconds=values["OPENPLAN_CACHE_TTL_SECONDS"],
        max_bytes=values["OPENPLAN_CACHE_MAX_BYTES"],
    )
