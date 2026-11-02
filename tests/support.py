import base64
import json
import unittest

from fastapi.testclient import TestClient

from openplan.api.app import app
from openplan.api.auth import DATA_READ_ROLE


def principal_headers(*roles: str) -> dict[str, str]:
    principal = {
        "auth_typ": "aad",
        "claims": [{"typ": "roles", "val": role} for role in roles],
        "role_typ": "roles",
    }
    value = base64.b64encode(json.dumps(principal).encode()).decode()
    return {"X-MS-CLIENT-PRINCIPAL": value}


class HTTPTestCase(unittest.TestCase):
    def setUp(self):
        # Exercise the HTTP error envelope instead of re-raising server exceptions.
        self.client = self.enterContext(TestClient(
            app, raise_server_exceptions=False, headers=principal_headers(DATA_READ_ROLE),
        ))

    def request(self, path, params=None, route_params=None):
        return self.client.get(path.format(**(route_params or {})), params=params or {})
