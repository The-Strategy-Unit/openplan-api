import json
import unittest
from unittest.mock import patch

import azure.functions as func
import polars as pl

import function_app
from openplan.api.v1 import data, demographics, tpmas
from openplan.api.v1.reference import providers
from openplan.api.v1.tpmas import rates


class EndpointContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routes = {}
        for function in function_app.app.get_functions():
            for binding in function.get_bindings():
                if binding.type == "httpTrigger":
                    cls.routes[binding.route] = function.get_user_function()

    def setUp(self):
        provider_catalogue = {
            "R01": {"name": "Provider one", "valid_from": "v1.0"},
            "R02": {"name": "Provider two", "valid_from": "v1.0"},
        }
        tpma_catalogue = {
            "IP-AA-001": {"name": "Example TPMA", "active_from": "v1.0"},
        }
        self.rate_rows = [
            {"provider": "R01", "fyear": 202425, "denominator": 100.0, "std_rate": 1.2},
            {"provider": "R01", "fyear": 202526, "denominator": 120.0, "std_rate": 1.5},
            {"provider": "R02", "fyear": 202425, "denominator": 80.0, "std_rate": 0.8},
        ]
        rate_data = pl.DataFrame(self.rate_rows).with_columns(
            pl.lit("not part of the response").alias("internal")
        )
        demographic_data = pl.DataFrame({
            "sex": ["F", "F", "M"],
            "age": [0, 1, 0],
            "2024": [10.0, 20.0, 15.0],
            "2030": [12.0, 22.0, 16.0],
        })
        self.patch_attribute(providers, "_get_providers", return_value=provider_catalogue)
        self.patch_attribute(tpmas, "_get_TPMAs", return_value=tpma_catalogue)
        self.read_rates = self.patch_attribute(
            rates, "read_azure_parquet_file", return_value=rate_data.lazy()
        )
        self.read_demographics = self.patch_attribute(
            demographics, "read_azure_csv_file", return_value=demographic_data.lazy()
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

    def request_rates(self, params, tpma="IP-AA-001"):
        request = func.HttpRequest(
            method="GET",
            url=f"http://localhost/v1/tpmas/{tpma}/rates",
            body=b"",
            route_params={"tpma": tpma},
            params=params,
        )
        return self.routes["v1/tpmas/{tpma}/rates"](request)

    def request_demographics(self, params, provider="R01"):
        request = func.HttpRequest(
            method="GET",
            url=f"http://localhost/v1/providers/{provider}/demographic-factors",
            body=b"",
            route_params={"provider": provider},
            params=params,
        )
        return self.routes["v1/providers/{provider}/demographic-factors"](request)

    def test_registered_routes_match_the_approved_contract(self):
        self.assertEqual(set(self.routes), {
            "openapi.json",
            "docs",
            "v1/reference/providers",
            "v1/reference/peers/{provider}",
            "v1/tpmas",
            "v1/tpmas/{tpma}/rates",
            "v1/providers/{provider}/demographic-factors",
        })

    def test_rates_filter_by_provider_with_complete_rows(self):
        response = self.request_rates({"provider": "R01"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_body()), self.rate_rows[:2])
        self.read_rates.assert_called_once_with("api/dev/provider/rates/IP-AA-001.parquet")

    def test_rates_filter_by_financial_year_with_complete_rows(self):
        response = self.request_rates({"fyear": "202425"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_body()), [self.rate_rows[0], self.rate_rows[2]])

    def test_rates_apply_both_filters(self):
        response = self.request_rates({"provider": "R01", "fyear": "202425"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_body()), [self.rate_rows[0]])

    def test_rates_return_an_empty_list_for_no_matching_rows(self):
        response = self.request_rates({"provider": "R02", "fyear": "202526"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_body()), [])

    def test_rates_use_the_requested_dataset_version(self):
        response = self.request_rates({"provider": "R01", "version": "v1.0"})
        self.assertEqual(response.status_code, 200)
        self.read_rates.assert_called_once_with("api/v1.0/provider/rates/IP-AA-001.parquet")

    def test_rates_require_at_least_one_filter(self):
        for params in ({}, {"version": "v1.0"}):
            with self.subTest(params=params):
                response = self.request_rates(params)
                self.assertEqual(response.status_code, 400)
                self.assertIn("provider or fyear", response.get_body().decode())
        self.read_rates.assert_not_called()

    def test_rates_reject_invalid_filters_before_reading_rate_data(self):
        for params in (
            {"provider": ""}, {"provider": "ZZZ"},
            {"fyear": "2024"}, {"fyear": "2024ab"}, {"fyear": ""},
            {"provider": "R01", "version": "invalid"},
        ):
            with self.subTest(params=params):
                response = self.request_rates(params)
                self.assertEqual(response.status_code, 400)
        self.read_rates.assert_not_called()

    def test_rates_reject_invalid_tpmas_before_reading_rate_data(self):
        for tpma in ("invalid", "IP-AA-999"):
            with self.subTest(tpma=tpma):
                self.assertEqual(self.request_rates({"fyear": "202425"}, tpma).status_code, 400)
        self.read_rates.assert_not_called()

    def test_demographics_read_selection_from_query_parameters(self):
        response = self.request_demographics({
            "start_year": "2024", "end_year": "2030", "variant": "principal",
            "version": "v1.0",
        })
        self.assertEqual(response.status_code, 200)
        expected = {
            "baseline": {"F": {"0": 10.0, "1": 20.0}, "M": {"0": 15.0}},
            "horizon": {"F": {"0": 12.0, "1": 22.0}, "M": {"0": 16.0}},
        }
        self.assertEqual(json.loads(response.get_body()), {
            "population": expected, "births": expected,
        })
        self.assertEqual(self.read_demographics.call_count, 2)
        for demographic_type in ("population", "births"):
            self.read_demographics.assert_any_call(
                f"api/v1.0/provider/demographics/{demographic_type}/"
                "fyear=202425/provider=R01/variant=principal/part-0.csv"
            )

    def test_demographics_require_all_selection_parameters(self):
        valid = {"start_year": "2024", "end_year": "2030", "variant": "principal"}
        for missing in valid:
            with self.subTest(missing=missing):
                params = {key: value for key, value in valid.items() if key != missing}
                response = self.request_demographics(params)
                self.assertEqual(response.status_code, 400)
                details = json.loads(response.get_body())["details"]
                self.assertIn(missing, [detail["field"] for detail in details])
        self.read_demographics.assert_not_called()

    def test_demographics_reject_invalid_selection_parameters(self):
        for invalid in (
            {"start_year": "not-a-year"}, {"start_year": "1899"},
            {"end_year": "2023"}, {"variant": ""},
        ):
            with self.subTest(invalid=invalid):
                params = {"start_year": "2024", "end_year": "2030", "variant": "principal"}
                self.assertEqual(self.request_demographics(params | invalid).status_code, 400)
        self.read_demographics.assert_not_called()

    def test_demographics_allow_equal_baseline_and_horizon_years(self):
        response = self.request_demographics({
            "start_year": "2024", "end_year": "2024", "variant": "principal",
        })
        self.assertEqual(response.status_code, 200)
        for factors in json.loads(response.get_body()).values():
            self.assertEqual(factors["baseline"], factors["horizon"])

    def test_demographic_variant_cannot_change_the_dataset_path(self):
        for variant in ("../principal", "principal/other", r"..\principal"):
            with self.subTest(variant=variant):
                response = self.request_demographics({
                    "start_year": "2024", "end_year": "2030", "variant": variant,
                })
                self.assertEqual(response.status_code, 400)
        self.read_demographics.assert_not_called()

    def test_openapi_matches_parameter_locations_and_rate_response(self):
        request = func.HttpRequest(method="GET", url="http://localhost/openapi.json", body=b"")
        response = self.routes["openapi.json"](request)
        self.assertEqual(response.status_code, 200)
        spec = json.loads(response.get_body())

        def resolve_schema(schema):
            if "$ref" in schema:
                return spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
            return schema

        def query_schema(operation):
            parameter = next(
                parameter for parameter in operation["parameters"]
                if parameter["in"] == "querystring"
            )
            return resolve_schema(parameter["content"][
                "application/x-www-form-urlencoded"
            ]["schema"])

        self.assertEqual(set(spec["paths"]), {f"/{route}" for route in self.routes} - {
            "/openapi.json", "/docs",
        })
        rate_operation = spec["paths"]["/v1/tpmas/{tpma}/rates"]["get"]
        rate_parameters = {
            (parameter["in"], parameter["name"]): parameter
            for parameter in rate_operation["parameters"]
        }
        self.assertEqual(set(rate_parameters), {
            ("path", "tpma"), ("querystring", "querystring"),
        })
        rate_query_schema = query_schema(rate_operation)
        self.assertEqual(set(rate_query_schema["properties"]), {"provider", "fyear", "version"})
        self.assertEqual(rate_query_schema.get("required", []), [])
        items = rate_operation["responses"]["200"]["content"]["application/json"]["schema"]["items"]
        items = resolve_schema(items)
        self.assertEqual(set(items["required"]), {"provider", "fyear", "denominator", "std_rate"})
        demographic_operation = spec["paths"][
            "/v1/providers/{provider}/demographic-factors"
        ]["get"]
        demographic_parameters = {
            (parameter["in"], parameter["name"]): parameter
            for parameter in demographic_operation["parameters"]
        }
        self.assertEqual(set(demographic_parameters), {
            ("path", "provider"), ("querystring", "querystring"),
        })
        demographic_query_schema = query_schema(demographic_operation)
        self.assertEqual(set(demographic_query_schema["properties"]), {
            "start_year", "end_year", "variant", "version",
        })
        self.assertEqual(set(demographic_query_schema["required"]), {
            "start_year", "end_year", "variant",
        })


if __name__ == "__main__":
    unittest.main()
