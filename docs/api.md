# API contracts and route changes

See the [endpoint list](../README.md#api) and generated `/docs` or `/openapi.json`
for paths, query parameters, and schemas.

## Dataset selection

`/v1/` identifies the HTTP contract. The `version` query parameter selects a
dataset release such as `v1.0`, defaulting to `dev`. Provider and TPMA codes must
exist in that release; use the catalogues with the same version. Validity includes
the introduction release and excludes the retirement release.

The TPMA catalogue maps codes to metadata objects containing `active_from`,
optional `active_to`, and publisher-supplied fields.

Catalogue responses and identifier validation follow the
[dataset cache lifetime](caching.md#freshness). Release indexes and manifests
are read without caching.

## Responses

- **Rates:** require `provider`, `fyear`, or both; both filters apply when supplied.
  Rows always contain `provider`, `fyear`, `denominator`, and `std_rate`. No matching
  rows returns `[]`. Financial years span consecutive years: `202425` and `199900`
  are valid; `202499` is not.
- **Demographics:** require `start_year`, `end_year`, and `variant`, with the end
  year at least the start year. The start year selects the baseline financial-year
  file. Responses contain `population` and `births`, each with `baseline` and
  `horizon` maps keyed by sex and age. JSON keys are strings; factors may be numeric
  or null. Variants cannot contain path separators.
- **Peers:** preserve the publisher-defined JSON payload. Missing provider/version
  peer sets return 404; an explicitly empty set returns 200.
- **Health:** returns `{"status":"ok"}` without contacting storage. This checks
  application liveness, not dataset availability, and uses `Cache-Control: no-store`.
- **Discovery:** returns published releases and valid query combinations, with
  provenance, publication time, and supplied units. See [dataset manifests](dataset-manifests.md).

FastAPI validates responses against the models used to generate OpenAPI.

## Errors and authentication

Application errors return `{"error":"message"}`. Invalid parameters additionally
identify affected fields:

```json
{"error":"Invalid request parameters","details":[{"field":"version","message":"Invalid value"}]}
```

Status codes are 400 for invalid requests or inactive codes, 404 for missing
resources, 500 for processing or server failures, and 503 for storage connection
failures. Server exception details are logged and excluded from error responses.

Azure Easy Auth protects deployed endpoints, including health and documentation.
Functions-key authentication is anonymous. Swagger's **Authorize** accepts an Entra
access token for the API's configured audience using the `EntraBearer` scheme.
Unauthenticated requests are redirected to sign-in (302); rejected credentials
can return 401. Platform responses do not guarantee an application JSON body.
Local hosting does not reproduce Easy Auth.

## Breaking route changes

The following routes have been replaced without compatibility aliases:

| Earlier route | Replacement |
| --- | --- |
| `/v1/tpmas/rates/provider/provider={provider}/{tpma}` | `/v1/tpmas/{tpma}/rates?provider={provider}` |
| `/v1/tpmas/rates/provider/fyear={fyear}/{tpma}` | `/v1/tpmas/{tpma}/rates?fyear={fyear}` |
| `/v1/demographics/provider/{provider}/{start_year}/{end_year}/{variant}` | `/v1/providers/{provider}/demographic-factors?start_year={start_year}&end_year={end_year}&variant={variant}` |

Rate responses now always include both provider and financial year.
