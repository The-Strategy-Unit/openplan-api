import json
from functools import cache
from io import BytesIO

import polars as pl
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

credential = DefaultAzureCredential()


def _read_azure_file(file: str) -> BytesIO:
    blob_service_client = BlobServiceClient(
        account_url="https://nhpsa.blob.core.windows.net",
        credential=credential,
    )

    container_client = blob_service_client.get_container_client("inputs-data")
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
    return read_azure_json_file_uncached(file)


def read_azure_json_file_uncached(file: str) -> dict:
    with _read_azure_file(file) as f:
        return json.load(f)
