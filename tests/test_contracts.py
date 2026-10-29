import unittest
from unittest.mock import patch

from azure.core.exceptions import AzureError, ResourceNotFoundError, ServiceRequestError
from fastapi import FastAPI
from fastapi.testclient import TestClient
import polars as pl
from pydantic import JsonValue, TypeAdapter, ValidationError

from openplan.api.app import app
from openplan.api.v1 import demographics
from openplan.api.v1.demographics.models import DemographicFactorsResponse
from openplan.api.v1.error_handling import ErrorResponse, ValidationErrorResponse, register_error_handlers
from openplan.api.v1.models import VersionQuery
from openplan.api.v1.reference import peers, providers
from tests.support import HTTPTestCase


class ContractTests(HTTPTestCase):
    @classmethod
    def setUpClass(cls):
        with TestClient(app) as client:
            cls.document = client.get("/openapi.json").json()

    def resolve(self, schema):
        if "$ref" not in schema:
            return schema
        target = self.document
        for part in schema["$ref"][2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        return target

    def test_document_declares_platform_bearer_authentication(self):
        self.assertEqual(self.document["security"], [{"EntraBearer": []}])
        scheme = self.document["components"]["securitySchemes"]["EntraBearer"]
        self.assertEqual(scheme["type"], "http")
        self.assertEqual(scheme["scheme"], "bearer")
        for path_item in self.document["paths"].values():
            responses = path_item["get"]["responses"]
            self.assertIn("302", responses)
            self.assertIn("401", responses)
            self.assertNotIn("content", responses["302"])
            self.assertNotIn("content", responses["401"])

    def test_data_operations_document_their_error_envelopes(self):
        for path, path_item in self.document["paths"].items():
            if path == "/health":
                continue
            expected = {"404", "500", "503"}
            if path != "/v1/reference/versions":
                expected.add("400")
            for status in expected:
                with self.subTest(path=path, status=status):
                    schema = path_item["get"]["responses"][status]["content"]["application/json"]["schema"]
                    schema = self.resolve(schema)
                    self.assertEqual(schema["properties"]["error"]["type"], "string")
                    self.assertIn("error", schema["required"])
                    if status == "400":
                        self.assertIn("details", schema["required"])

    def test_generated_schema_references_all_resolve(self):
        def walk(value):
            if isinstance(value, dict):
                if "$ref" in value:
                    self.assertTrue(value["$ref"].startswith("#/"))
                    self.resolve(value)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(self.document)

    def test_runtime_errors_match_the_documented_models(self):
        try:
            VersionQuery(version="invalid")
        except ValidationError as exc:
            invalid_parameters = exc
        cases = (
            # Invalid server-side models are server failures, not client errors.
            (invalid_parameters, 500),
            (ResourceNotFoundError("fixture-secret"), 404),
            (ServiceRequestError("fixture-secret"), 503),
            (AzureError("fixture-secret"), 500),
            (pl.exceptions.ComputeError("fixture-secret"), 500),
            (RuntimeError("fixture-secret"), 500),
        )
        for error, status in cases:
            with self.subTest(error=type(error).__name__):
                error_app = FastAPI()
                register_error_handlers(error_app)

                @error_app.get("/failure")
                def route():
                    raise error

                with TestClient(error_app, raise_server_exceptions=False) as client, self.assertLogs(__name__, level="INFO"):
                    response = client.get("/failure")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.headers["content-type"], "application/json")
                ErrorResponse.model_validate_json(response.content)
                self.assertNotIn("fixture-secret", response.text)

    def test_invalid_http_parameters_use_the_validation_error_envelope(self):
        response = self.client.get("/v1/reference/providers", params={"version": "invalid"})
        self.assertEqual(response.status_code, 400)
        model = ValidationErrorResponse.model_validate_json(response.content)
        self.assertEqual(model.error, "Invalid request parameters")
        self.assertEqual([detail.field for detail in model.details], ["version"])

    def test_demographic_schema_describes_both_factors_and_time_points(self):
        schema = self.document["paths"][
            "/v1/providers/{provider}/demographic-factors"
        ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        schema = self.resolve(schema)
        self.assertEqual(set(schema["required"]), {"population", "births"})
        for field in ("population", "births"):
            factors = self.resolve(schema["properties"][field])
            self.assertEqual(set(factors["required"]), {"baseline", "horizon"})

    def test_demographic_json_matches_the_response_model(self):
        factors = {
            "baseline": {1: {0: 1.0, 1: None}},
            "horizon": {1: {0: 1.1, 1: 1.2}},
        }
        with patch.object(providers, "_get_providers", return_value={
            "R01": {"name": "Synthetic provider", "valid_from": "v1.0"},
        }), patch.object(demographics, "get_demographic_factors", return_value=factors):
            response = self.client.get(
                "/v1/providers/R01/demographic-factors",
                params={"start_year": "2024", "end_year": "2030", "variant": "principal"},
            )
        self.assertEqual(response.status_code, 200)
        model = DemographicFactorsResponse.model_validate_json(response.content)
        self.assertEqual(model.population.baseline["1"]["0"], 1.0)
        self.assertIsNone(model.births.baseline["1"]["1"])

    def test_publisher_peer_payloads_remain_unchanged(self):
        for payload in (["R02"], {"group": ["R02"], "description": "Synthetic peer group"}):
            with self.subTest(payload=payload), patch.object(providers, "_get_providers", return_value={
                "R01": {"name": "Synthetic provider", "valid_from": "v1.0"},
            }), patch.object(peers, "read_azure_json_file", return_value={"R01": {"v1.0": payload}}):
                response = self.client.get("/v1/reference/peers/R01", params={"version": "v1.0"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(TypeAdapter(JsonValue).validate_json(response.content), payload)


if __name__ == "__main__":
    unittest.main()
