import json
import os
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
