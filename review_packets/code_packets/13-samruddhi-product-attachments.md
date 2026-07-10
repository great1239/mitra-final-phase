# Samruddhi Product Attachments

## File: `pratham/companion-runtime/mitra_companion/transport.py`

**Sprint change:** Modified

**Purpose:** Provides Mitra's product-neutral HTTP transport and attachment
health checking.

**Why modified:** Added generic manifest-configured headers, secret-backed
Bearer token injection, and strict health-contract validation so real product
APIs can be attached without embedding credentials or accepting frontend HTML
fallbacks as healthy APIs.

**Key implementation areas:** `dispatch.options.headers`;
`dispatch.options.secret_headers`; `dispatch.options.bearer_token_env`;
`*_FILE` secret loading; JSON health-contract enforcement.

**Review focus:** Header precedence, absence of hardcoded product branches,
secret redaction, behavior when secret files are missing, and whether
non-JSON health responses become unhealthy when required by manifest metadata.

**Related tests:** `pratham/tests/test_bhiv_product_integration.py`.

## File: `contracts/production/product-samruddhi-uniguru.json`

**Sprint change:** Added

**Purpose:** Production bootstrap manifest for the UniGuru product repository
under the Samruddhi attached-product group.

**Why modified:** Moves UniGuru from example-only documentation into the real
production manifest directory using the product's published API contract and
repository provenance.

**Key implementation areas:** Published base URL; `POST /ask` dispatch;
`GET /health` JSON health contract; source repository and HEAD commit;
operator-supplied UniGuru bearer token reference.

**Review focus:** Contract accuracy against `VJY123VJY/uniguru_ai`, no
embedded token value, correct request schema, and honest behavior when the
deployed domain serves a frontend page instead of JSON health.

**Related tests:** `pratham/tests/test_bhiv_product_integration.py`.

## File: `contracts/production/product-samruddhi-trade-bot.json`

**Sprint change:** Added

**Purpose:** Production bootstrap manifest for the Samruddhi Trade Bot
repository.

**Why modified:** Moves Trade Bot from example-only documentation into the
real production manifest directory using the product's published MCP API
surface and repository provenance.

**Key implementation areas:** Published base URL; `POST /tools/predict`;
`POST /tools/analyze`; `GET /tools/health`; response schemas; source
repository and HEAD commit.

**Review focus:** Contract accuracy against `harshapawar136/trade-bot-main`,
external endpoint availability, schema strictness, and absence of simulated or
localhost routing.

**Related tests:** `pratham/tests/test_bhiv_product_integration.py`.
