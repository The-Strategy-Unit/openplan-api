import json
import os
import unittest
from unittest.mock import Mock, call, patch

from azure.core.exceptions import ServiceRequestError
from azure.core.paging import ItemPaged
from azure.storage.blob import BlobPrefix, BlobProperties
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openplan.api.v1 import data
from openplan.api.v1.error_handling import register_error_handlers


class StorageConfigurationTests(unittest.TestCase):
    def test_blob_reads_use_the_configured_account_and_container(self):
        with patch.dict(os.environ, {
            "OPENPLAN_STORAGE_ACCOUNT_NAME": "syntheticstorage",
            "OPENPLAN_STORAGE_CONTAINER_NAME": "synthetic-inputs",
        }, clear=True), patch.object(data, "BlobServiceClient") as client:
            blob = client.return_value.get_container_client.return_value.get_blob_client.return_value
            blob.download_blob.return_value.readall.return_value = b'{"example": true}'
            with data._read_azure_file("api/peers.json") as stream:
                self.assertEqual(json.load(stream), {"example": True})
        client.assert_called_once_with(
            account_url="https://syntheticstorage.blob.core.windows.net",
            credential=data.credential,
        )
        client.return_value.get_container_client.assert_called_once_with("synthetic-inputs")
        client.return_value.get_container_client.return_value.get_blob_client.assert_called_once_with("api/peers.json")

    def test_missing_or_blank_settings_fail_before_any_storage_access(self):
        for missing in ("OPENPLAN_STORAGE_ACCOUNT_NAME", "OPENPLAN_STORAGE_CONTAINER_NAME"):
            for value in (None, "", "   "):
                with self.subTest(setting=missing, value=value):
                    environment = {
                        "OPENPLAN_STORAGE_ACCOUNT_NAME": "syntheticstorage",
                        "OPENPLAN_STORAGE_CONTAINER_NAME": "synthetic-inputs",
                    }
                    if value is None:
                        del environment[missing]
                    else:
                        environment[missing] = value
                    with patch.dict(os.environ, environment, clear=True), patch.object(data, "BlobServiceClient") as client:
                        with self.assertRaisesRegex(RuntimeError, missing):
                            data._read_azure_file("api/peers.json")
                    client.assert_not_called()

    def test_storage_settings_are_resolved_when_reading_not_when_importing(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(data, "BlobServiceClient") as client:
            with self.assertRaises(RuntimeError):
                data._read_azure_file("api/peers.json")
            os.environ.update({
                "OPENPLAN_STORAGE_ACCOUNT_NAME": "anotherstorage",
                "OPENPLAN_STORAGE_CONTAINER_NAME": "another-container",
            })
            client.return_value.get_container_client.return_value.get_blob_client.return_value.download_blob.return_value.readall.return_value = b"{}"
            with data._read_azure_file("api/peers.json") as stream:
                self.assertEqual(stream.read(), b"{}")
        self.assertEqual(client.call_args.kwargs["account_url"], "https://anotherstorage.blob.core.windows.net")

    def test_storage_configuration_errors_are_server_errors(self):
        app = FastAPI()
        register_error_handlers(app)

        @app.get("/storage")
        def route():
            data._read_azure_file("api/peers.json")
            return {"status": "ok"}

        with patch.dict(os.environ, {}, clear=True), patch.object(data, "BlobServiceClient") as storage, TestClient(app, raise_server_exceptions=False) as client, self.assertLogs(__name__, level="ERROR"):
            response = client.get("/storage")
        storage.assert_not_called()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"error": "Internal server error"})


class DirectoryListingTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {
            "OPENPLAN_STORAGE_ACCOUNT_NAME": "syntheticstorage",
            "OPENPLAN_STORAGE_CONTAINER_NAME": "synthetic-inputs",
        }, clear=True))
        self.client = self.enterContext(patch.object(data, "BlobServiceClient"))
        self.service = self.client.return_value.__enter__.return_value
        self.container = self.service.get_container_client.return_value

    def test_lists_only_immediate_directories_across_all_pages(self):
        next_page = Mock(side_effect=[
            ("second-page", [BlobPrefix(prefix="dev/"), BlobProperties(name="v9.0")]),
            (None, [BlobPrefix(prefix="v4.0/"), BlobPrefix(prefix="api/")]),
        ])
        self.container.walk_blobs.return_value = ItemPaged(
            get_next=next_page, extract_data=lambda page: page,
        )

        self.assertEqual(data.list_azure_directories(), ["dev", "v4.0", "api"])

        self.client.assert_called_once_with(
            account_url="https://syntheticstorage.blob.core.windows.net", credential=data.credential,
        )
        self.service.get_container_client.assert_called_once_with("synthetic-inputs")
        self.container.walk_blobs.assert_called_once_with(delimiter="/")
        self.assertEqual(next_page.call_args_list, [call(None), call("second-page")])
        self.client.return_value.__exit__.assert_called_once_with(None, None, None)

    def test_empty_listing_and_new_directories_are_not_cached(self):
        self.container.walk_blobs.side_effect = [iter([]), iter([BlobPrefix(prefix="dev/")])]
        with patch.dict(os.environ, {"OPENPLAN_CACHE_TTL_SECONDS": "invalid"}):
            self.assertEqual(data.list_azure_directories(), [])
            self.assertEqual(data.list_azure_directories(), ["dev"])
        self.assertEqual(self.container.walk_blobs.call_count, 2)
        self.assertEqual(self.client.return_value.__exit__.call_count, 2)

    def test_later_page_failures_propagate_and_close_the_client(self):
        next_page = Mock(side_effect=[
            ("second-page", [BlobPrefix(prefix="dev/")]),
            ServiceRequestError("Synthetic listing failure"),
        ])
        self.container.walk_blobs.return_value = ItemPaged(
            get_next=next_page, extract_data=lambda page: page,
        )
        with self.assertRaises(ServiceRequestError):
            data.list_azure_directories()
        self.client.return_value.__exit__.assert_called_once()

    def test_missing_settings_fail_before_client_construction(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                data.list_azure_directories()
        self.client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
