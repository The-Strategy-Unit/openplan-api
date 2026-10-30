from unittest.mock import Mock

import pytest

from openplan.api.v1 import data


@pytest.fixture(autouse=True)
def isolate_dataset_caches():
    readers = (
        data.read_azure_csv_file, data.read_azure_parquet_file,
        data.read_azure_json_file,
    )
    for reader in readers:
        reader.cache_clear()
    yield
    for reader in readers:
        reader.cache_clear()


@pytest.fixture(autouse=True)
def prohibit_live_blob_storage(monkeypatch):
    client = Mock(side_effect=AssertionError("Unit tests must mock BlobServiceClient"))
    monkeypatch.setattr(data, "BlobServiceClient", client)
    yield
    # Detect attempted access even if a route converted the assertion to a 500.
    client.assert_not_called()
