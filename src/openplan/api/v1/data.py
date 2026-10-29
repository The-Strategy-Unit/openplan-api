import json
from functools import cache
from io import BytesIO

import polars as pl
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from openplan.api.v1 import settings

__CREDENTIAL: DefaultAzureCredential | None = None


def _read_azure_file(file: str) -> BytesIO:
    global __CREDENTIAL
    if __CREDENTIAL is None:
        __CREDENTIAL = DefaultAzureCredential()

    blob_service_client = BlobServiceClient(
        account_url=f"https://{settings.BLOB_STORAGE_ACCOUNT}.blob.core.windows.net",
        credential=__CREDENTIAL,
    )

    container_client = blob_service_client.get_container_client(
        settings.BLOB_STORAGE_CONTAINER
    )
    blob_client = container_client.get_blob_client(file)
    download_stream = blob_client.download_blob()

    return BytesIO(download_stream.readall())


@cache
def read_azure_parquet_file(file: str) -> pl.LazyFrame:
    with _read_azure_file(file) as f:
        return pl.scan_parquet(f)


@cache
def read_azure_csv_file(file: str) -> pl.LazyFrame:
    with _read_azure_file(file) as f:
        return pl.scan_csv(f)


@cache
def read_azure_json_file(file: str) -> dict:
    with _read_azure_file(file) as f:
        return json.load(f)
