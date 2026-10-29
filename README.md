# OpenPlan API

[![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This repository contains the API for OpenPlan, implemented as Azure Function Apps and secured with Microsoft Entra ID. The code exposes structured data and reference endpoints for planning and analytical workflows, and includes an OpenAPI definition for interactive documentation.

## Overview

OpenPlan API provides a lightweight HTTP layer built on Azure Functions for access to OpenPlan datasets and reference information. The service currently includes:

- provider and reference lookups
- demographic data endpoints
- TPMA rate queries by provider and financial year
- generated OpenAPI and Swagger documentation

The deployment locations and environment details are intentionally not described in this repository.

## Repository structure

- `function_app.py` — Azure Functions app entry point and route registration
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
3. Start the Azure Functions host locally:
   - `func start`

Once running, the API exposes OpenAPI and Swagger endpoints through the Azure Functions app.

## API endpoints

All data endpoints use `GET`. The `/v1/` prefix identifies the HTTP API contract;
the optional `version` query parameter selects a dataset release such as `v1.0`
and defaults to `dev`.

| Purpose             | Path                                           | Selection parameters                           |
| ------------------- | ---------------------------------------------- | ---------------------------------------------- |
| Application liveness | `/health` | None |
| Dataset releases | `/v1/reference/versions` | None |
| Rate availability | `/v1/tpmas/{tpma}/rates/availability` | `version` |
| Demographic availability | `/v1/providers/{provider}/demographic-factors/availability` | `version` |
| Provider catalogue  | `/v1/reference/providers`                      | `version`                                      |
| TPMA catalogue      | `/v1/tpmas`                                    | `version`                                      |
| Provider peers      | `/v1/reference/peers/{provider}`               | `version`                                      |
| TPMA rates          | `/v1/tpmas/{tpma}/rates`                       | `provider`, `fyear`, `version`                 |
| Demographic factors | `/v1/providers/{provider}/demographic-factors` | `start_year`, `end_year`, `variant`, `version` |

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
Polars transformations. The development dependency group supplies pytest and
Polars' compatibility runtime for machines without AVX support. These dependencies
are installed by `uv sync`; they are not added to the production requirements.
The tests do not require Azure credentials or live storage.

## Security

This repository contains Azure Function Apps secured with Microsoft Entra ID. Authentication and authorization are enforced at the application boundary; access to deployed resources is managed through Microsoft Entra ID-based identity configuration.

## License

This project is licensed under the MIT License. See [LICENSE](./LICENSE) for details.
