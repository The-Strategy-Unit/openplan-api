# OpenPlan API

[![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![codecov](https://codecov.io/gh/The-Strategy-Unit/openplan-api/graph/badge.svg?token=d1I5EnPiPJ)](https://codecov.io/gh/The-Strategy-Unit/openplan-api)

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

## Security

This repository contains Azure Function Apps secured with Microsoft Entra ID. Authentication and authorization are enforced at the application boundary; access to deployed resources is managed through Microsoft Entra ID-based identity configuration.

## License

This project is licensed under the MIT License. See [LICENSE](./LICENSE) for details.
