# Entra authentication and data roles

Azure Easy Auth authenticates deployed requests before they reach FastAPI. It
checks the configured Entra issuer and audience and injects the authenticated
principal. Functions-key authentication remains anonymous.

Every `/v1/` endpoint additionally requires the Entra app role
`OpenPlan.Data.Read`, including catalogues and discovery metadata. `/health`,
`/docs` and `/openapi.json` require deployed Easy Auth authentication but have no
application role requirement. Health and documentation remain independent of
dataset storage configuration.

## Application authorization

The application decodes `X-MS-CLIENT-PRINCIPAL`, validates its JSON structure
and checks role claims. The current policy accepts only the exact,
case-sensitive value `OpenPlan.Data.Read`. Group identifiers and a top-level
`roles` property do not satisfy the policy.

Role claims may be named `roles` or use the mapped claim type identified by
`role_typ`. A shared FastAPI dependency protects every data router and rejects
unauthorized requests before catalogue or dataset access.
[Microsoft documents the injected headers and claim mapping](https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-user-identities).

Application authorization failures use the established JSON error envelope:

| Condition | Status | Body |
| --- | --- | --- |
| Missing, undecodable or malformed principal | 401 | `{"error":"Unauthorized"}` |
| Principal has no accepted role | 403 | `{"error":"Forbidden"}` |

Easy Auth can reject requests before the application runs. The current deployed
configuration redirects unauthenticated requests to Entra sign-in (302), and
rejected credentials can return 401. Platform responses do not guarantee an
application JSON body. OpenAPI documents both the platform boundary and the
application's 401/403 responses; bearer metadata itself performs no validation.

## Configure access before deploying

This is an access-policy change: authenticated callers without the read role
can no longer use `/v1/`. Configure assignments before deploying the change.

1. On the existing API app registration referenced by the Bicep `entraClientId`
   parameter, define an enabled app role with the exact value `OpenPlan.Data.Read`.
   Choose allowed member types according to whether users/groups, applications
   or both should be eligible. The application policy accepts any authenticated
   principal carrying that role; it does not distinguish human and service callers.
2. Assign the role to the intended users/groups through the Enterprise application,
   or grant client applications the corresponding application permission and
   administrative consent. Obtain a fresh identity/token after assignment.
3. Verify allowed and denied callers against the deployed app, including audience,
   role claims and the expected 401/403 or platform rejection behavior.

The infrastructure consumes an existing app registration; this change does not
create roles, assign permissions or deploy Azure resources. App roles are distinct
from Azure resource RBAC and delegated OAuth scopes. This policy checks app roles;
it does not add a delegated-scope policy.
[Microsoft app-role configuration](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps),
[scope and role verification](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-protected-web-api-verification-scope-app-roles).

## Local development and verification

Trust the principal header only behind the enforced Easy Auth boundary. Direct
local hosting does not authenticate callers or protect the header from forgery.
Sending a bearer token to a local host alone does not create the trusted principal;
do not expose a local host as an authenticated deployment.

Tests use synthetic principal headers, real FastAPI requests and the Azure ASGI
adapter. They cover missing/malformed principals, wrong or absent roles, multiple
roles, claim mapping, denial before storage access and the health/docs exception.
These checks verify application behavior, not the deployed authentication
boundary, role assignments or storage permissions. The server's storage identity
is independent of a caller's read role.

## Evidence required before production approval

1. Obtain independent review of the exact revision: router dependencies,
   principal parsing, mapped roles, JSON errors and the health/docs exception.
   Review the deployed Easy Auth configuration with an Azure/Entra engineer.
2. Run the full suite on supported Linux with Python 3.14 and the locked standard
   Polars runtime, without verification adapters. Verify that the deployed
   dependency versions match the tested build.
3. In an explicitly approved Azure test environment with synthetic data, execute
   the following matrix through the public host. Disable automatic redirects so
   an Entra login page cannot be mistaken for a successful API response.

| Deployed request | Required observation |
| --- | --- |
| No identity, including on health/docs | Rejected or redirected by Easy Auth; no dataset response. The current configuration uses a 302 redirect. |
| Expired/tampered token or wrong audience/issuer | Rejected by the authentication platform; no dataset response. |
| Valid identity without the read role | Every `/v1/` operation denies access; application authorization returns 403 if the request reaches FastAPI. |
| Valid identity with `OpenPlan.Data.Read` | Valid requests succeed with independently expected synthetic results. |
| Forged principal header without a valid identity | Cannot gain access through the Azure host. |
| Valid identity without the role plus a forged principal claiming the role | Cannot gain access; the forged header must not replace the platform principal. |
| Signed-in caller without the role requesting health/docs | Allowed when the approved platform sign-in policy admits that caller. |

Microsoft documents that App Service prevents external requests from setting its
injected identity headers and that allowed audiences constrain accepted tokens.
The deployed checks verify that our request path preserves those assumptions.
[Identity header boundary](https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-user-identities),
[authentication and audience configuration](https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-provider-aad).

Record the revision, artifact/dependency versions, reviewed configuration, caller
permission category and observed results. Do not record tokens or principal
payloads. Cover user/group assignments and application permissions separately if
both are supported, and test every intended external entry point.
