# OpenPlan API

[![Project Status: WIP](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

FastAPI on Azure Functions, secured by Microsoft Entra ID. Provides peer, TPMA rate,
provider and demographic datasets for OpenPlan.

## Local development

Requires Python 3.14, uv, and Azure Functions Core Tools.

```bash
uv sync --locked
source .venv/bin/activate
```

Configure `local.settings.json` using [the example](local.settings.example.json),
then run `func start`. Set these values in its `Values` section:

| Setting                           | Value                        |
| --------------------------------- | ---------------------------- |
| `OPENPLAN_STORAGE_ACCOUNT_NAME`   | Dataset storage account name |
| `OPENPLAN_STORAGE_CONTAINER_NAME` | Dataset blob container name  |

Data reads use `DefaultAzureCredential` and require container read access.
Datasets cache for five minutes by default; see
[cache settings and limits](docs/caching.md).
Health and documentation work without dataset storage configuration.

Swagger UI is at `/docs`; the generated schema is at `/openapi.json`.
Deployed requests use Entra Easy Auth; local hosting does not enforce it.

## API

All endpoints use `GET`. The optional `version` query parameter selects the
dataset release and defaults to `dev`; `/v1/` identifies the API contract.

| Path                                                        | Query parameters                               |
| ----------------------------------------------------------- | ---------------------------------------------- |
| `/health`                                                   | —                                              |
| `/v1/reference/versions`                                    | —                                              |
| `/v1/reference/providers`                                   | `version`                                      |
| `/v1/reference/peers/{provider}`                            | `version`                                      |
| `/v1/tpmas`                                                 | `version`                                      |
| `/v1/tpmas/{tpma}/rates`                                    | `provider`, `fyear`, `version`                 |
| `/v1/tpmas/{tpma}/rates/availability`                       | `version`                                      |
| `/v1/providers/{provider}/demographic-factors`              | `start_year`, `end_year`, `variant`, `version` |
| `/v1/providers/{provider}/demographic-factors/availability` | `version`                                      |

Rates require `provider`, `fyear`, or both; financial years look like `202425`.
Demographics require all three selection parameters, with `end_year >= start_year`.
Discover valid codes through the catalogues using the same dataset version.

See [API contracts and route changes](docs/api.md) for response and error details.
Discovery requires publisher-supplied [dataset manifests](docs/dataset-manifests.md).

## Tests

```bash
uv run pytest -vv
```

Tests use synthetic data and block live storage access. [CI](.github/workflows/tests.yml)
runs tests and Python/shell syntax checks with Python 3.14 and locked dependencies.

## Deployment

[Infrastructure](infrastructure/) defines hosting, managed identity, and Entra
authentication. `infrastructure/create.sh` uses both storage variables above,
exported in the shell, plus `OPENPLAN_STORAGE_RESOURCE_GROUP` for the dataset
account's resource group. It configures access and publishes the app. Existing
deployments must also supply both storage application settings.

MIT licensed; see [LICENSE](LICENSE).
