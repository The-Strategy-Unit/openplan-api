# OpenPlan API

[![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This repository contains the API for OpenPlan, implemented with FastAPI, hosted on Azure Functions, and secured with Microsoft Entra ID. The code exposes structured data and reference endpoints for planning and analytical workflows, with generated OpenAPI and interactive documentation.

## Overview

OpenPlan API uses FastAPI for routing, parameter validation, response validation, and OpenAPI generation. Azure Functions provides hosting through its ASGI adapter. The service currently includes:

- provider and reference lookups
- demographic data endpoints
- TPMA rate queries by provider and financial year
- generated OpenAPI and Swagger documentation

The deployment locations and environment details are intentionally not described in this repository.

## Repository structure

- `function_app.py` — Azure Functions ASGI entry point
- `openplan/api/app.py` — FastAPI application and router registration
- `openplan/` — application modules and API route handlers
- `infrastructure/` — infrastructure-as-code for Azure resources
- `host.json` and `local.settings.json` — Azure Functions runtime configuration
- `requirements.txt` / `pyproject.toml` — Python project dependencies and packaging metadata

## Local development

This project targets Python 3.14.

1. Create and activate a virtual environment:
   - `python -m venv .venv`
   - `source .venv/bin/activate`
2. Install dependencies:
   - `pip install -r requirements.txt`
   - or `uv sync`
3. Set `OPENPLAN_STORAGE_ACCOUNT_NAME` and `OPENPLAN_STORAGE_CONTAINER_NAME` in
   the `Values` section of your `local.settings.json`. Use
   [local.settings.example.json](local.settings.example.json) as a template and
   replace the example names with your dataset storage account and container.
4. Start the Azure Functions host locally:
   - `func start`

Once running, `/openapi.json` and `/docs` expose FastAPI's generated OpenAPI and
Swagger UI through the Azure Functions app. Route signatures and Pydantic models
define parameters and response schemas; a small shared customization documents
the Entra authentication boundary and the established 400 validation status.

## Dataset storage configuration

Dataset storage is configured through environment variables:

| Variable                          | Meaning                                                    |
| --------------------------------- | ---------------------------------------------------------- |
| `OPENPLAN_STORAGE_ACCOUNT_NAME`   | Existing Azure storage account name, without a URL or path |
| `OPENPLAN_STORAGE_CONTAINER_NAME` | Existing blob container containing OpenPlan datasets       |

Both are required for data reads; there is no default storage account or
container. The account name determines the public Azure Blob endpoint
`https://<account>.blob.core.windows.net`. Authentication continues to use
`DefaultAzureCredential`, including the configured managed identity in Azure.
Blob names such as `api/peers.json` are relative to the selected container.

Azure Functions loads local values from `local.settings.json`. When running
Python directly, export the two variables in your shell. Restart the host after
changing storage settings to clear its dataset caches. Health and OpenAPI do not
require dataset storage configuration, and unit tests use synthetic storage.

For deployment, `infrastructure/create.sh` reads these same two variables and
also requires `OPENPLAN_STORAGE_RESOURCE_GROUP`, the resource group containing
the dataset account. The script passes the account and container into Bicep app
settings and uses those same values to grant the managed identity read access.
The Function host/deployment storage remains a separate infrastructure resource.

Existing deployments need the two new application settings before publishing
this code. The deployment script supplies them; manual deployments must set
them explicitly. The tracked `local.settings.json` is not changed automatically.

## API endpoints

All data endpoints use `GET`. The `/v1/` prefix identifies the HTTP API contract;
the optional `version` query parameter selects a dataset release such as `v1.0`
and defaults to `dev`.

| Purpose                  | Path                                                        | Selection parameters                           |
| ------------------------ | ----------------------------------------------------------- | ---------------------------------------------- |
| Application liveness     | `/health`                                                   | None                                           |
| Dataset releases         | `/v1/reference/versions`                                    | None                                           |
| Rate availability        | `/v1/tpmas/{tpma}/rates/availability`                       | `version`                                      |
| Demographic availability | `/v1/providers/{provider}/demographic-factors/availability` | `version`                                      |
| Provider catalogue       | `/v1/reference/providers`                                   | `version`                                      |
| TPMA catalogue           | `/v1/tpmas`                                                 | `version`                                      |
| Provider peers           | `/v1/reference/peers/{provider}`                            | `version`                                      |
| TPMA rates               | `/v1/tpmas/{tpma}/rates`                                    | `provider`, `fyear`, `version`                 |
| Demographic factors      | `/v1/providers/{provider}/demographic-factors`              | `start_year`, `end_year`, `variant`, `version` |

Provider and TPMA identifiers are validated against the selected dataset version.
Use the catalogues with the same `version` to discover valid codes, including
historical identifiers. Validity includes the introduction release and excludes
the retirement release. The TPMA catalogue maps codes to metadata objects with
`active_from`, optional `active_to`, and any additional catalogue metadata.

Rates require `provider`, `fyear`, or both. When both are supplied, both filters
apply. Each response row contains `provider`, `fyear`, `denominator`, and
`std_rate`, regardless of the filters. A valid query with no matching rows
returns an empty list. Financial years use six digits spanning consecutive
years, for example `202425`. Century rollovers such as `199900` are valid;
values such as `202499` are rejected.

Demographic factors require `start_year`, `end_year`, and `variant` as query
parameters. `end_year` must be greater than or equal to `start_year`. The start
year selects the baseline financial-year dataset; the response contains
population and birth factors for the baseline and horizon years, grouped by sex
and age. Variant identifiers must not contain path separators.

Invalid parameters or codes outside the selected dataset version return 400.
Peer queries return 404 when no peer set exists for that provider and version;
an explicitly empty peer set remains a successful 200 response.

`GET /health` returns `{"status":"ok"}` when the application is running. It does
not contact storage or confirm dataset availability. Its response is not cached,
and the deployed endpoint remains protected by the existing Entra authentication.

Discovery endpoints expose publisher-supplied release metadata and valid query
combinations. Rate selections group providers by financial year; demographic
selections give start-year/variant pairs and their available horizon years.
They also include publication time, provenance, and any supplied measure units.
The data publisher must supply the [discovery manifests](docs/dataset-manifests.md)
before these endpoints can serve a release. Synthetic examples and an offline
validation command are included in that guide.

Example requests (replace provider and TPMA codes with values from the catalogues):

```text
/v1/tpmas/IP-AA-001/rates?provider=RXX
/v1/tpmas/IP-AA-001/rates?fyear=202425
/v1/tpmas/IP-AA-001/rates?provider=RXX&fyear=202425&version=v1.0
/v1/providers/RXX/demographic-factors?start_year=2024&end_year=2030&variant=principal
```

The earlier `/v1/tpmas/rates/provider/provider={provider}/{tpma}` and
`/v1/tpmas/rates/provider/fyear={fyear}/{tpma}` routes are replaced by the single
rate endpoint above. Rate responses now always include both provider and
financial year. The earlier
`/v1/demographics/provider/{provider}/{start_year}/{end_year}/{variant}` route is
replaced by the demographic-factors endpoint above. These are breaking changes;
the earlier routes have no compatibility aliases.

## Tests

Run the endpoint regression tests from the repository root:

```bash
uv run pytest -vv
```

Pytest runs the `unittest`-based regression tests with synthetic datasets and real
Polars transformations. HTTP tests use FastAPI's TestClient; adapter tests also
invoke the registered Azure Function to verify request parsing, response bodies,
and errors through the hosting boundary. Install the development dependencies,
including pytest and TestClient's `httpx2`, with `uv sync --locked`. Tests block
unexpected Azure storage access and do not require credentials or live datasets.

## Security

The Azure Functions app is secured with Microsoft Entra ID through Easy Auth.
Functions-key authentication remains anonymous; deployed requests pass through
Easy Auth before reaching FastAPI.

OpenAPI declares an `EntraBearer` JWT bearer scheme for the deployed API. In
Swagger UI, use **Authorize** to supply an Entra access token for the API's
configured audience. The deployed authentication settings currently redirect
unauthenticated requests to Entra sign-in (302); rejected credentials can return 401. Those platform responses have no application JSON error-body guarantee.
Local Functions hosting does not reproduce Easy Auth.

## Response and error contracts

FastAPI validates responses against the same models used by OpenAPI to describe
rate rows, provider/TPMA catalogues, demographic factors,
health, and discovery responses. Demographic responses contain `population` and
`births`, each with `baseline` and `horizon` maps keyed by sex and age. JSON map
keys are strings; factor values may be numeric or null when missing in the input.
Peer sets remain publisher-defined JSON until their narrower structure is
confirmed; the API preserves that payload.

Application-handled errors share these JSON shapes:

```json
{ "error": "Dataset not found" }
```

Parameter validation errors additionally identify affected fields:

```json
{
  "error": "Invalid request parameters",
  "details": [{ "field": "version", "message": "Invalid value" }]
}
```

The documented application statuses are 400 for request validation, 404 for
missing resources, 500 for data-processing or unexpected server failures, and
503 for storage connection failures. Internal exception details are logged on
the server and are not included in server-error responses.

## License

This project is licensed under the MIT License. See [LICENSE](./LICENSE) for details.
