import json
from io import BytesIO

import polars as pl
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from openplan.api.v1.cache import BlobCache
from openplan.api.v1.settings import StorageSettings, get_cache_settings, get_storage_settings

credential = DefaultAzureCredential()
_blob_cache = BlobCache()


def clear_dataset_cache() -> None:
    _blob_cache.clear()


def _read_azure_file(file: str, *, settings: StorageSettings | None = None) -> BytesIO:
    settings = settings or get_storage_settings()
    blob_service_client = BlobServiceClient(
        account_url=settings.account_url,
        credential=credential,
    )

    container_client = blob_service_client.get_container_client(settings.container_name)
    blob_client = container_client.get_blob_client(file)
    download_stream = blob_client.download_blob()

    return BytesIO(download_stream.readall())


def _read_cached_azure_file(file: str) -> BytesIO:
    storage = get_storage_settings()
    policy = get_cache_settings()
    key = (storage.account_name, storage.container_name, file)

    def download() -> bytes:
        with _read_azure_file(file, settings=storage) as stream:
            return stream.read()

    return BytesIO(_blob_cache.get(key, download, policy))


def read_azure_parquet_file(file: str) -> pl.LazyFrame:
    with _read_cached_azure_file(file) as f:
        return pl.scan_parquet(f)


def read_azure_csv_file(file: str) -> pl.LazyFrame:
    with _read_cached_azure_file(file) as f:
        return pl.scan_csv(f)


def read_azure_json_file(file: str) -> dict:
    with _read_cached_azure_file(file) as f:
        return json.load(f)


def read_azure_json_file_uncached(file: str) -> dict:
    with _read_azure_file(file) as f:
        return json.load(f)
