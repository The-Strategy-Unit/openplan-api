# Dataset discovery manifests

`GET /v1/reference/versions` lists immediate directory prefixes in the configured
dataset container, such as `dev/`, `v5.1/`, and `v4.0/`. It keeps names matching
`dev` or `v<major>.<minor>[.<patch>]` and returns version-name strings without the
trailing slash. It does not read a release-index JSON file or download datasets.
An empty container, or one without valid version directories, returns
`{"versions":[]}`. A directory's presence does not guarantee a complete release.

The availability endpoints separately require a publisher-supplied JSON manifest
for the requested release. They do not scan dataset files or guess measurement units.

| Blob path | Content |
| --- | --- |
| `api/{version}/manifest.json` | Availability and metadata for one release |

The [manifest example](../examples/dataset-manifest.json) contains synthetic data.
Generate production manifests from the same outputs that are published as datasets.

## Format

Manifests use `schema_version: 1`. Release identifiers use the same `dev` or
`v<major>.<minor>[.<patch>]` syntax as the API. Each manifest supplies a
timezone-aware `published_at` timestamp and a nonempty `source` describing its
provenance. A manifest's `version`
must match the version in its blob path.

The version list includes `dev` only when that directory exists; it does not
invent an alias for the latest release. Publish a corresponding
`api/dev/manifest.json` to enable availability queries for `dev`.

A manifest contains `rates` keyed by TPMA code and `demographics` keyed by
provider code. Empty maps are allowed when that release has no corresponding
datasets. Unknown fields are rejected so publisher spelling errors are visible.

For each TPMA, `selections` groups valid providers by financial year. Each
financial year occurs once and each provider occurs once within that year.
For example, the sample's `R01/202425` and `R02/202526` selections do not advertise
`R01/202526` or `R02/202425`.

For each demographic provider, every selection contains a `start_year`, a
`variant`, and the corresponding available `end_years`. The start-year/variant
pairs must be unique; horizon years must be unique and cannot precede the start
year. Advertise only combinations supported by **both population and births**,
because the demographic endpoint returns both. Start years select the baseline
financial-year partition, as described in the main API documentation.

Each dataset may supply a `units` map keyed by measure, such as `denominator` or
`std_rate`. Populate it with the actual measure definitions, scales, and units
from the publishing pipeline. An empty map means units have not been supplied;
the API does not interpret it as unitless data.

## Validate and publish

Validate metadata from the repository root before publishing:

```bash
uv run python -m openplan.api.v1.discovery.validate manifest examples/dataset-manifest.json
```

These checks validate the format without contacting Azure. The publishing
pipeline must also verify that advertised combinations exist in the files and
match the provider and TPMA catalogues for the same release.

Publish dataset files first, then the release manifest. A version directory can
appear in the listing before its publication is complete. Keep released versions
immutable. Update `dev` and its metadata together when publishing development data.
The publisher must own consistency between files and manifests.

The CLI's `index` mode and [index example](../examples/dataset-index.json) remain
available for format validation. Such index files are not read by the API.

## API behaviour

`GET /v1/reference/versions` returns directory names as
`{"versions":["dev","v5.1","v4.0"]}`. It does not supply publication timestamps
or provenance. Ordering follows the storage listing, not release chronology.
The two availability endpoints accept the normal `version` query parameter,
defaulting to `dev`, and return the selected release metadata, resource code,
valid selections, and publisher-supplied units.

Directory listings and manifests bypass the [dataset cache](caching.md); successful responses
use `Cache-Control: no-store`. Provider/TPMA validation still follows the catalogue
cache lifetime.

- Invalid request parameters or inactive catalogue codes: 400.
- Missing container, metadata blob, or manifest entry for the requested resource: 404.
- Malformed metadata, unsupported schema versions, or mismatched release IDs: 500.
- Storage connection failures: 503.

Deploying API code does not create manifests. The data publisher must publish
them before availability queries work for a release. Version listing works
independently of manifests. Existing data-query endpoints continue reading their
established files independently of discovery.
