import base64
import json
import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

from openplan.api.app import create_app
from openplan.api.auth import DATA_READ_ROLE, require_role
from openplan.api.v1 import data
from openplan.api.v1.error_handling import register_error_handlers
from openplan.api.v1.reference import providers
from tests.support import principal_headers


def encoded_principal(value) -> dict[str, str]:
    return {"X-MS-CLIENT-PRINCIPAL": base64.b64encode(json.dumps(value).encode()).decode()}


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.enterContext(TestClient(self.app, raise_server_exceptions=False))

    def test_every_data_endpoint_rejects_missing_and_wrong_roles_before_storage(self):
        operations = [
            (route.path_format, method)
            for route in iter_route_contexts(self.app.routes)
            if route.path and route.path.startswith("/v1/")
            for method in route.methods or ()
        ]
        self.assertTrue(operations)
        with patch.object(data, "_read_azure_file") as read:
            for path, method in operations:
                path = path.format(provider="R01", tpma="IP-AA-001")
                for headers, status, message in (
                    ({}, 401, "Unauthorized"),
                    (principal_headers(), 403, "Forbidden"),
                    (principal_headers("Unrelated.Read"), 403, "Forbidden"),
                ):
                    with self.subTest(path=path, method=method, status=status, headers=headers):
                        response = self.client.request(method, path, headers=headers)
                        self.assertEqual(response.status_code, status)
                        self.assertEqual(response.json(), {"error": message})
            read.assert_not_called()

    def test_malformed_principals_return_401_json(self):
        payloads = (
            None, [], "not an object", {"claims": None}, {"claims": {}},
            {"claims": [None]}, {"claims": [{}]},
            {"claims": [{"typ": "roles", "val": [DATA_READ_ROLE]}]},
            {"claims": [{"typ": "roles", "val": 123}]},
            {"claims": [], "role_typ": None},
        )
        headers = [encoded_principal(payload) for payload in payloads]
        headers.extend({"X-MS-CLIENT-PRINCIPAL": value} for value in (
            "", "not-base64!", base64.b64encode(b"\xff").decode(),
            base64.b64encode(b"not-json").decode(),
        ))
        with patch.object(providers, "get_providers") as read:
            for value in headers:
                with self.subTest(headers=value):
                    response = self.client.get("/v1/reference/providers", headers=value)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.json(), {"error": "Unauthorized"})
            read.assert_not_called()

    def test_bearer_token_alone_does_not_replace_the_easy_auth_principal(self):
        response = self.client.get(
            "/v1/reference/providers", headers={"Authorization": "Bearer unvalidated-token"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "Unauthorized"})

    def test_roles_must_be_role_claims_with_the_exact_required_value(self):
        payloads = (
            {}, {"roles": [DATA_READ_ROLE]},
            {"claims": [{"typ": "groups", "val": DATA_READ_ROLE}]},
            {"claims": [{"typ": "roles", "val": DATA_READ_ROLE.lower()}]},
            {"claims": [{"typ": "roles", "val": DATA_READ_ROLE + ".Extra"}]},
            {"claims": [{"typ": "roles", "val": "Prefix." + DATA_READ_ROLE}]},
            {"claims": [{"typ": "roles", "val": DATA_READ_ROLE + " Other.Read"}]},
            {"claims": [{"typ": "roles", "val": "Other.Read," + DATA_READ_ROLE}]},
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.get(
                    "/v1/reference/providers", headers=encoded_principal(payload),
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json(), {"error": "Forbidden"})

    def test_required_role_succeeds_among_other_roles_and_with_claim_mapping(self):
        mapped_type = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"
        headers = (
            principal_headers(DATA_READ_ROLE),
            principal_headers("Unrelated.Read", DATA_READ_ROLE),
            encoded_principal({
                "role_typ": mapped_type,
                "claims": [{"typ": mapped_type, "val": DATA_READ_ROLE}],
            }),
            encoded_principal({
                "role_typ": mapped_type,
                "claims": [{"typ": "roles", "val": DATA_READ_ROLE}],
            }),
        )
        with patch.object(providers, "get_providers", return_value={"R01": "Synthetic provider"}) as read:
            for value in headers:
                with self.subTest(headers=value):
                    response = self.client.get("/v1/reference/providers", headers=value)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), {"R01": "Synthetic provider"})
            self.assertEqual(read.call_count, len(headers))

    def test_any_accepted_role_is_sufficient_as_in_the_reference(self):
        app = FastAPI()
        register_error_handlers(app)

        @app.get("/restricted", dependencies=[Depends(require_role("Read", "Admin"))])
        def route():
            return {"status": "ok"}

        with TestClient(app) as client:
            for role in ("Read", "Admin"):
                with self.subTest(role=role):
                    response = client.get("/restricted", headers=principal_headers(role))
                    self.assertEqual(response.status_code, 200)

    def test_health_and_documentation_have_no_application_role_requirement(self):
        with patch.object(data, "_read_azure_file") as read:
            for path in ("/health", "/docs", "/openapi.json"):
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path).status_code, 200)
            read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
