import json
import os
import unittest
from unittest.mock import patch


from openplan.api.v1 import data
from tests.support import HTTPTestCase


class HealthTests(HTTPTestCase):
    def request(self):
        return self.client.get("/health")

    def test_health_returns_uncached_json(self):
        response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(json.loads(response.content), {"status": "ok"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_health_does_not_depend_on_dataset_storage(self):
        with patch.object(data, "_read_azure_file", side_effect=RuntimeError("Storage is offline")) as read:
            self.assertEqual(self.request().status_code, 200)
        read.assert_not_called()


    def test_health_and_documentation_ignore_invalid_cache_settings(self):
        with patch.dict(os.environ, {
            "OPENPLAN_CACHE_TTL_SECONDS": "invalid",
            "OPENPLAN_CACHE_MAX_BYTES": "invalid",
        }):
            for path in ("/health", "/docs", "/openapi.json"):
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path).status_code, 200)


if __name__ == "__main__":
    unittest.main()
