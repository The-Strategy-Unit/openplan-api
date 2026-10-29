from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError, ServiceRequestError
from pydantic import ValidationError

from openplan.api.v1 import data, discovery, tpmas
from openplan.api.v1.discovery.models import DatasetIndex, DatasetManifest
from openplan.api.v1.reference import providers

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.index = json.loads((EXAMPLES / "dataset-index.json").read_text())
        self.manifest = json.loads((EXAMPLES / "dataset-manifest.json").read_text())
        self.patch_attribute(providers, "_get_providers", return_value={
            "R01": {"name": "Provider one", "valid_from": "v1.0"},
            "R02": {"name": "Provider two", "valid_from": "v1.0"},
            "OLD": {"name": "Retired provider", "valid_from": "v1.0", "valid_to": "v2.0"},
        })
        self.patch_attribute(tpmas, "_get_TPMAs", return_value={
            "IP-AA-001": {"name": "Example", "active_from": "v1.0"},
            "IP-AA-002": {"name": "Retired", "active_from": "v1.0", "active_to": "v2.0"},
        })
        self.read_metadata = self.patch_attribute(
            discovery, "read_azure_json_file_uncached", side_effect=self.metadata,
        )
        self.patch_attribute(data, "_read_azure_file", side_effect=AssertionError("No live storage in tests"))

    def patch_attribute(self, target, attribute, **kwargs):
        patcher = patch.object(target, attribute, **kwargs)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def metadata(self, filename):
        if filename == "api/versions.json":
            return self.index
        if filename == f"api/{self.manifest['version']}/manifest.json":
            return self.manifest
        raise ResourceNotFoundError("Synthetic missing metadata")

    def request(self, handler, params=None, route_params=None):
        return handler(func.HttpRequest(
            method="GET", url="http://localhost/", body=b"",
            params=params or {}, route_params=route_params or {},
        ))

    def rate_request(self, version="v1.0", tpma="IP-AA-001"):
        return self.request(discovery.route_rate_availability, {"version": version}, {"tpma": tpma})

    def demographic_request(self, version="v1.0", provider="R01"):
        return self.request(discovery.route_demographic_availability, {"version": version}, {"provider": provider})

    def test_versions_return_published_release_metadata(self):
        response = self.request(discovery.route_versions)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_body()), {"versions": self.index["versions"]})
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.read_metadata.assert_called_once_with("api/versions.json")

    def test_rate_availability_preserves_valid_combinations(self):
        response = self.rate_request()
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.get_body())
        self.assertEqual(payload["selections"], self.manifest["rates"]["IP-AA-001"]["selections"])
        self.assertEqual(payload["tpma"], "IP-AA-001")
        self.assertEqual(payload["version"], "v1.0")
        self.assertEqual(payload["source"], "Synthetic example data")
        self.assertEqual(payload["units"], {})
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_demographic_availability_preserves_start_variant_horizon_combinations(self):
        response = self.demographic_request()
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.get_body())
        self.assertEqual(payload["selections"], self.manifest["demographics"]["R01"]["selections"])
        self.assertEqual(payload["provider"], "R01")
        self.assertEqual(payload["version"], "v1.0")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_publisher_units_are_returned_without_interpretation(self):
        units = {"denominator": "Synthetic denominator unit", "std_rate": "Synthetic rate scale"}
        self.manifest["rates"]["IP-AA-001"]["units"] = units
        self.assertEqual(json.loads(self.rate_request().get_body())["units"], units)

    def test_default_version_uses_the_dev_manifest(self):
        self.manifest["version"] = "dev"
        response = self.request(discovery.route_rate_availability, route_params={"tpma": "IP-AA-001"})
        self.assertEqual(response.status_code, 200)
        self.read_metadata.assert_called_once_with("api/dev/manifest.json")

    def test_historical_resource_codes_use_the_requested_release(self):
        self.manifest["rates"]["IP-AA-002"] = deepcopy(self.manifest["rates"]["IP-AA-001"])
        self.manifest["demographics"]["OLD"] = deepcopy(self.manifest["demographics"]["R01"])
        self.assertEqual(self.rate_request(tpma="IP-AA-002").status_code, 200)
        self.assertEqual(self.demographic_request(provider="OLD").status_code, 200)
        self.assertEqual(self.rate_request(version="v2.0", tpma="IP-AA-002").status_code, 400)
        self.assertEqual(self.demographic_request(version="v2.0", provider="OLD").status_code, 400)

    def test_invalid_requests_do_not_read_metadata(self):
        for response in (
            self.rate_request(version="invalid"), self.rate_request(tpma="IP-AA-999"),
            self.demographic_request(version="invalid"), self.demographic_request(provider="ZZZ"),
        ):
            self.assertEqual(response.status_code, 400)
        self.read_metadata.assert_not_called()

    def test_absent_resource_entries_return_not_found(self):
        self.manifest["rates"] = {}
        self.manifest["demographics"] = {}
        self.assertEqual(self.rate_request().status_code, 404)
        self.assertEqual(self.demographic_request().status_code, 404)

    def test_missing_metadata_blobs_return_not_found(self):
        self.read_metadata.side_effect = ResourceNotFoundError("Synthetic missing blob")
        self.assertEqual(self.request(discovery.route_versions).status_code, 404)
        self.assertEqual(self.rate_request().status_code, 404)
        self.assertEqual(self.demographic_request().status_code, 404)

    def test_storage_connection_failures_are_unavailable(self):
        self.read_metadata.side_effect = ServiceRequestError("Synthetic offline storage")
        with self.assertLogs("openplan.api.v1.discovery", level="ERROR"):
            self.assertEqual(self.rate_request().status_code, 503)

    def test_invalid_published_metadata_is_a_server_error(self):
        self.manifest["schema_version"] = 99
        with self.assertLogs("openplan.api.v1.discovery", level="ERROR"):
            response = self.rate_request()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.get_body()), {"error": "Internal server error"})

    def test_manifest_version_must_match_its_requested_path(self):
        self.read_metadata.side_effect = None
        self.read_metadata.return_value = self.manifest | {"version": "v2.0"}
        with self.assertLogs("openplan.api.v1.discovery", level="ERROR"):
            self.assertEqual(self.rate_request().status_code, 500)

    def test_new_releases_are_visible_without_worker_restart(self):
        updated = deepcopy(self.index)
        updated["versions"].append(updated["versions"][0] | {"version": "v2.0"})
        self.read_metadata.side_effect = [self.index, updated]
        self.assertEqual(len(json.loads(self.request(discovery.route_versions).get_body())["versions"]), 1)
        self.assertEqual(len(json.loads(self.request(discovery.route_versions).get_body())["versions"]), 2)

    def test_example_metadata_validates_without_catalogue_access(self):
        with patch.object(providers, "_get_providers", side_effect=AssertionError("No catalogue reads")), \
             patch.object(tpmas, "_get_TPMAs", side_effect=AssertionError("No catalogue reads")):
            DatasetIndex.model_validate(self.index)
            DatasetManifest.model_validate(self.manifest)

    def test_metadata_rejects_invalid_or_duplicate_selections(self):
        invalid = []
        duplicate_versions = deepcopy(self.index)
        duplicate_versions["versions"] *= 2
        with self.assertRaises(ValidationError):
            DatasetIndex.model_validate(duplicate_versions)
        for change in ("duplicate-year", "duplicate-provider", "invalid-year", "bad-horizon", "duplicate-horizon", "duplicate-variant", "path-variant"):
            manifest = deepcopy(self.manifest)
            rates = manifest["rates"]["IP-AA-001"]["selections"]
            demographics = manifest["demographics"]["R01"]["selections"]
            if change == "duplicate-year":
                rates.append(deepcopy(rates[0]))
            elif change == "duplicate-provider":
                rates[0]["providers"] *= 2
            elif change == "invalid-year":
                rates[0]["fyear"] = "202499"
            elif change == "bad-horizon":
                demographics[0]["end_years"] = [2023]
            elif change == "duplicate-horizon":
                demographics[0]["end_years"] *= 2
            elif change == "duplicate-variant":
                demographics.append(deepcopy(demographics[0]))
            else:
                demographics[0]["variant"] = "../principal"
            invalid.append((change, manifest))
        for change, manifest in invalid:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                DatasetManifest.model_validate(manifest)

    def test_uncached_json_reader_observes_replaced_metadata(self):
        with patch.object(data, "_read_azure_file", side_effect=[BytesIO(b'{"revision": 1}'), BytesIO(b'{"revision": 2}')]):
            self.assertEqual(data.read_azure_json_file_uncached("api/versions.json"), {"revision": 1})
            self.assertEqual(data.read_azure_json_file_uncached("api/versions.json"), {"revision": 2})


if __name__ == "__main__":
    unittest.main()
