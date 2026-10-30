import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
STORAGE_ENV = (
    "OPENPLAN_STORAGE_ACCOUNT_NAME",
    "OPENPLAN_STORAGE_CONTAINER_NAME",
    "OPENPLAN_STORAGE_RESOURCE_GROUP",
)


class DeploymentConfigurationTests(unittest.TestCase):
    def run_script(self, missing=None):
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            log = directory / "commands.jsonl"
            command = f"""#!{sys.executable}
import json
import os
from pathlib import Path
import sys

name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['OPENPLAN_TEST_COMMAND_LOG'], 'a') as output:
    output.write(json.dumps([name, *args]) + '\\n')
if name == 'az' and args[:3] == ['ad', 'app', 'list']:
    print('synthetic-client-id')
elif name == 'az' and args[:3] == ['deployment', 'group', 'create']:
    print(json.dumps({{'properties': {{'outputs': {{
        'userAssignedIdentityPrincipalId': {{'value': 'synthetic-principal-id'}},
        'functionAppName': {{'value': 'synthetic-function-app'}},
    }}}}}}))
elif name == 'jq':
    key = args[-1].split('.')[-2]
    print(json.load(sys.stdin)['properties']['outputs'][key]['value'])
"""
            for name in ("az", "jq", "func", "sleep"):
                executable = directory / name
                executable.write_text(command)
                executable.chmod(0o755)
            environment = os.environ.copy()
            for name in STORAGE_ENV:
                environment.pop(name, None)
            environment.update({
                # Only fake commands are on PATH; a test cannot invoke live Azure CLI.
                "PATH": str(directory),
                "OPENPLAN_TEST_COMMAND_LOG": str(log),
                "OPENPLAN_STORAGE_ACCOUNT_NAME": "syntheticstorage",
                "OPENPLAN_STORAGE_CONTAINER_NAME": "synthetic-inputs",
                "OPENPLAN_STORAGE_RESOURCE_GROUP": "synthetic-data-rg",
            })
            if missing:
                del environment[missing]
            result = subprocess.run(
                ["/bin/bash", str(ROOT / "infrastructure/create.sh"), "dev"],
                cwd=ROOT, env=environment, capture_output=True, text=True, timeout=10,
            )
            commands = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            return result, commands

    def test_missing_storage_settings_stop_before_external_commands(self):
        for missing in STORAGE_ENV:
            with self.subTest(missing=missing):
                result, commands = self.run_script(missing)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(missing, result.stderr)
                self.assertEqual(commands, [])

    def test_deployment_and_access_grant_use_the_same_storage_settings(self):
        result, commands = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        deployments = [command for command in commands if command[:4] == ["az", "deployment", "group", "create"]]
        self.assertEqual(len(deployments), 2)
        app = next(command for command in deployments if "infrastructure/main.bicep" in command)
        self.assertIn("dataStorageAccountName=syntheticstorage", app)
        self.assertIn("dataStorageContainerName=synthetic-inputs", app)
        grant = next(command for command in deployments if "infrastructure/grant-data-access.bicep" in command)
        self.assertEqual(grant[grant.index("--resource-group") + 1], "synthetic-data-rg")
        self.assertIn("storageAccountName=syntheticstorage", grant)
        self.assertIn("containerName=synthetic-inputs", grant)
        self.assertIn("principalId=synthetic-principal-id", grant)
        self.assertIn(["func", "azure", "functionapp", "publish", "synthetic-function-app", "--python"], commands)


if __name__ == "__main__":
    unittest.main()
