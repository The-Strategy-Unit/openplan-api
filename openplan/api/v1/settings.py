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
