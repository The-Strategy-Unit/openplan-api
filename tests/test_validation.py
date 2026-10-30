import json
import unittest
from unittest.mock import patch

import azure.functions as func
import polars as pl
from pydantic import TypeAdapter

import function_app
from openplan.api.v1 import data, demographics, tpmas
from openplan.api.v1.reference import peers, providers
from openplan.api.v1.tpmas import rates


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.providers = {
            "OLD": {"name": "Retired provider", "valid_from": "v1.0", "valid_to": "v2.0"},
            "CUR": {"name": "Continuing provider", "valid_from": "v1.0"},
            "NEW": {"name": "New provider", "valid_from": "v2.0"},
        }
        self.tpmas = {
            "IP-AA-001": {"name": "Retired TPMA", "active_from": "v1.0", "active_to": "v2.0"},
            "IP-AA-002": {"name": "Continuing TPMA", "active_from": "v1.0"},
            "IP-AA-003": {"name": "New TPMA", "active_from": "v2.0", "active_to": None},
        }
        self.peers = {
            "OLD": {"v1.0": ["CUR"]},
            "CUR": {"v1.0": ["OLD"], "v2.0": ["NEW"]},
        }
        self.patch_attribute(providers, "_get_providers", return_value=self.providers)
        self.patch_attribute(tpmas, "_get_TPMAs", return_value=self.tpmas)
        self.read_peers = self.patch_attribute(peers, "read_azure_json_file", return_value=self.peers)
        rate_frame = pl.DataFrame({
            "provider": ["OLD", "CUR", "NEW"],
            "fyear": [202425, 202425, 202425],
            "denominator": [10.0, 20.0, 30.0],
            "std_rate": [1.0, 2.0, 3.0],
        }).lazy()
        self.read_rates = self.patch_attribute(rates, "read_azure_parquet_file", return_value=rate_frame)
        self.demographic_factors = self.patch_attribute(
            demographics, "get_demographic_factors", return_value={"baseline": {}, "horizon": {}}
        )
        self.patch_attribute(
            data, "_read_azure_file",
            side_effect=AssertionError("Tests must not access Azure Storage"),
        )

    def patch_attribute(self, target, attribute, **kwargs):
        patcher = patch.object(target, attribute, **kwargs)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def request(self, handler, params=None, route_params=None):
        return handler(func.HttpRequest(
            method="GET", url="http://localhost/", body=b"",
            params=params or {}, route_params=route_params or {},
        ))

    def request_rates(self, provider=None, tpma="IP-AA-002", version="dev", fyear="202425"):
        params = {"version": version, "fyear": fyear}
        if provider is not None:
            params["provider"] = provider
        return self.request(rates.route_tpma_rates, params, {"tpma": tpma})

    def test_every_listed_provider_can_be_used_for_that_dataset_version(self):
        for version in ("v1.0", "v1.9", "v2.0", "dev"):
            catalogue = json.loads(self.request(
                providers.route_providers, {"version": version}
            ).get_body())
            for provider in catalogue:
                with self.subTest(version=version, provider=provider):
                    response = self.request_rates(provider=provider, version=version)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(json.loads(response.get_body())[0]["provider"], provider)

    def test_providers_outside_the_requested_version_are_rejected(self):
        for version, provider in (("v1.0", "NEW"), ("v1.9", "NEW"), ("v2.0", "OLD"), ("dev", "OLD")):
            with self.subTest(version=version, provider=provider):
                self.assertEqual(self.request_rates(provider=provider, version=version).status_code, 400)
        self.read_rates.assert_not_called()

    def test_every_listed_tpma_can_be_used_for_that_dataset_version(self):
        for version in ("v1.0", "v1.9", "v2.0", "dev"):
            catalogue = json.loads(self.request(tpmas.route_tpmas, {"version": version}).get_body())
            for tpma in catalogue:
                with self.subTest(version=version, tpma=tpma):
                    response = self.request_rates(tpma=tpma, version=version)
                    self.assertEqual(response.status_code, 200)

    def test_tpmas_outside_the_requested_version_are_rejected(self):
        for version, tpma in (
            ("v1.0", "IP-AA-003"), ("v1.9", "IP-AA-003"),
            ("v2.0", "IP-AA-001"), ("dev", "IP-AA-001"),
        ):
            with self.subTest(version=version, tpma=tpma):
                self.assertEqual(self.request_rates(tpma=tpma, version=version).status_code, 400)
        self.read_rates.assert_not_called()

    def test_demographics_validate_the_provider_against_the_requested_version(self):
        for version, provider, expected_status in (
            ("v1.0", "OLD", 200), ("v1.0", "NEW", 400),
            ("v2.0", "OLD", 400), ("v2.0", "NEW", 200),
        ):
            with self.subTest(version=version, provider=provider):
                response = self.request(demographics.route_demographic_factors, {
                    "version": version, "start_year": "2024",
                    "end_year": "2030", "variant": "principal",
                }, {"provider": provider})
                self.assertEqual(response.status_code, expected_status)
                if expected_status == 200:
                    self.demographic_factors.assert_any_call(
                        version, "population", 202425, provider, "principal", 2024, 2030
                    )

    def test_peers_validate_the_provider_against_the_requested_version(self):
        response = self.request(peers.route_peers, {"version": "v1.0"}, {"provider": "OLD"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_body()), ["CUR"])
        response = self.request(peers.route_peers, {"version": "v1.0"}, {"provider": "NEW"})
        self.assertEqual(response.status_code, 400)

    def test_default_dataset_version_rejects_retired_identifiers(self):
        requests = (
            (rates.route_tpma_rates, {"provider": "OLD"}, {"tpma": "IP-AA-002"}),
            (rates.route_tpma_rates, {"fyear": "202425"}, {"tpma": "IP-AA-001"}),
            (peers.route_peers, {}, {"provider": "OLD"}),
            (demographics.route_demographic_factors, {
                "start_year": "2024", "end_year": "2030", "variant": "principal",
            }, {"provider": "OLD"}),
        )
        for handler, params, route_params in requests:
            # Decorated Azure handlers are FunctionBuilders, without __name__.
            with self.subTest(params=params, route_params=route_params):
                self.assertEqual(self.request(handler, params, route_params).status_code, 400)
        self.read_rates.assert_not_called()
        self.demographic_factors.assert_not_called()

    def test_missing_peer_entries_return_not_found(self):
        del self.peers["CUR"]
        response = self.request(peers.route_peers, route_params={"provider": "CUR"})
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", json.loads(response.get_body()))

    def test_no_peer_version_at_or_before_the_requested_version_returns_not_found(self):
        self.peers["CUR"] = {"v2.0": ["NEW"]}
        response = self.request(peers.route_peers, {"version": "v1.0"}, {"provider": "CUR"})
        self.assertEqual(response.status_code, 404)

    def test_empty_peer_history_returns_not_found(self):
        self.peers["CUR"] = {}
        response = self.request(peers.route_peers, route_params={"provider": "CUR"})
        self.assertEqual(response.status_code, 404)

    def test_explicitly_empty_peer_sets_are_successful(self):
        self.peers["CUR"] = {"v1.0": []}
        response = self.request(peers.route_peers, route_params={"provider": "CUR"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_body()), [])

    def test_peer_selection_uses_the_latest_applicable_release(self):
        for version, expected in (("v1.0", ["OLD"]), ("v1.9", ["OLD"]), ("v2.0", ["NEW"]), ("dev", ["NEW"])):
            with self.subTest(version=version):
                response = self.request(peers.route_peers, {"version": version}, {"provider": "CUR"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(json.loads(response.get_body()), expected)

    def test_invalid_financial_years_are_rejected_without_reading_rates(self):
        for fyear in ("202499", "202424", "202427", "199901", "000001", "２０２４２５", "202425\n"):
            with self.subTest(fyear=fyear):
                response = self.request_rates(fyear=fyear)
                self.assertEqual(response.status_code, 400)
                details = json.loads(response.get_body())["details"]
                self.assertIn("fyear", [detail["field"] for detail in details])
        self.read_rates.assert_not_called()

    def test_consecutive_financial_years_include_century_rollovers(self):
        for fyear in ("202425", "202526", "199900", "209900"):
            with self.subTest(fyear=fyear):
                self.assertEqual(self.request_rates(fyear=fyear).status_code, 200)

    def test_tpma_response_model_preserves_the_actual_metadata_objects(self):
        response = self.request(tpmas.route_tpmas, {"version": "v1.0"})
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.get_body())
        adapter = TypeAdapter(dict[str, tpmas.TPMAResponseModel])
        models = adapter.validate_python(payload)
        self.assertEqual(adapter.dump_python(models, exclude_unset=True), payload)

    def test_tpma_openapi_schema_describes_metadata_objects(self):
        spec = json.loads(self.request(function_app.openapi_json).get_body())
        schema = spec["paths"]["/v1/tpmas"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        values = schema["additionalProperties"]
        if "$ref" in values:
            values = spec["components"]["schemas"][values["$ref"].split("/")[-1]]
        self.assertEqual(values["type"], "object")
        self.assertIn("active_from", values["required"])
        self.assertIn("active_to", values["properties"])
        self.assertTrue(values["additionalProperties"])
        self.assertIn("404", spec["paths"]["/v1/reference/peers/{provider}"]["get"]["responses"])


if __name__ == "__main__":
    unittest.main()
