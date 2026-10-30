import unittest

from fastapi.testclient import TestClient

from openplan.api.app import app


class HTTPTestCase(unittest.TestCase):
    def setUp(self):
        # Exercise the HTTP error envelope instead of re-raising server exceptions.
        self.client = self.enterContext(TestClient(app, raise_server_exceptions=False))

    def request(self, path, params=None, route_params=None):
        return self.client.get(path.format(**(route_params or {})), params=params or {})
