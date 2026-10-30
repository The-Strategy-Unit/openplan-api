import asyncio
import json
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import azure.functions as func

from function_app import app as hosted_app
from openplan.api.app import create_app
from openplan.api.v1 import tpmas
from openplan.api.v1.reference import providers
from openplan.api.v1.tpmas import rates


class AzureHostingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.host = func.AsgiFunctionApp(
            app=create_app(), http_auth_level=func.AuthLevel.ANONYMOUS,
        )
        self.handler = self.host.get_functions()[0].get_user_function()

    async def asyncTearDown(self):
        if self.host.startup_task_done:
            await self.host.middleware.notify_shutdown()
            # Shutdown already ran on this loop; prevent SDK destructor repetition.
            self.host.startup_task_done = False

    async def request(self, path, params=None):
        query_string = f"?{urlencode(params)}" if params else ""
        request = func.HttpRequest(
            method="GET", url=f"http://localhost{path}{query_string}", body=b"", params=params,
        )
        return await asyncio.wait_for(self.handler(request, None), timeout=10)

    def test_entry_point_registers_one_anonymous_catch_all_function(self):
        functions = hosted_app.get_functions()
        self.assertEqual(len(functions), 1)
        trigger = functions[0].get_bindings_dict()["bindings"][0]
        self.assertEqual(trigger["type"], "httpTrigger")
        self.assertEqual(trigger["route"], "/{*route}")
        self.assertEqual(trigger["authLevel"], func.AuthLevel.ANONYMOUS)
        self.assertIn(func.HttpMethod.GET, trigger["methods"])

    async def test_health_and_documentation_work_through_the_functions_adapter(self):
        response = await self.request("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_body()), {"status": "ok"})
        self.assertEqual(response.headers["cache-control"], "no-store")
        response = await self.request("/openapi.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("/v1/tpmas/{tpma}/rates", json.loads(response.get_body())["paths"])
        response = await self.request("/docs")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/openapi.json", response.get_body())

    async def test_invalid_requests_keep_the_400_json_contract_through_the_adapter(self):
        response = await self.request("/v1/reference/providers", {"version": "invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.get_body())["details"][0]["field"], "version")

    async def test_dataset_selection_and_json_survive_the_adapter(self):
        rows = [{"provider": "R01", "fyear": 202425, "denominator": 100.0, "std_rate": 1.2}]
        with patch.object(providers, "_get_providers", return_value={
            "R01": {"name": "Synthetic provider", "valid_from": "v1.0"},
        }), patch.object(tpmas, "_get_TPMAs", return_value={
            "IP-AA-001": {"active_from": "v1.0"},
        }), patch.object(rates, "get_tpma_rates", return_value=rows) as read:
            response = await self.request("/v1/tpmas/IP-AA-001/rates", {
                "provider": "R01", "fyear": "202425", "version": "v1.0",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_body()), rows)
        read.assert_called_once_with("v1.0", "IP-AA-001", provider="R01", fyear=202425)

    async def test_unexpected_errors_keep_the_500_json_contract_through_the_adapter(self):
        with patch.object(providers, "get_providers", side_effect=RuntimeError("fixture-secret")), self.assertLogs(
            "openplan.api.v1.reference.providers", level="ERROR",
        ):
            response = await self.request("/v1/reference/providers")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.get_body()), {"error": "Internal server error"})


if __name__ == "__main__":
    unittest.main()
