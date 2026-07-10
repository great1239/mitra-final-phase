# Samruddhi Product Attachments

## File: `pratham/companion-runtime/mitra_companion/transport.py`

**Sprint change:** Modified

**Purpose:** Provides Mitra's product-neutral HTTP transport and attachment
health checking.

**Why modified:** Added generic manifest-configured headers, secret-backed
Bearer token injection, strict health-contract validation, declared health
translation, and manifest-driven response fallback dispatch so real product
APIs can be attached without embedding credentials or accepting frontend HTML
fallbacks as healthy APIs.

**Key implementation areas:** `dispatch.options.headers`;
`dispatch.options.secret_headers`; `dispatch.options.bearer_token_env`;
`dispatch.options.response_fallbacks`; `*_FILE` secret loading; JSON
health-contract enforcement; `metadata.health_contract.translator`.

**Review focus:** Header precedence, absence of hardcoded product branches,
secret redaction, behavior when secret files are missing, and whether declared
non-linear health/dispatch responses are normalized without falsely marking
downstream failures healthy.

**Related tests:** `pratham/tests/test_bhiv_product_integration.py`.

## File: `contracts/production/product-samruddhi-uniguru.json`

**Sprint change:** Added

**Purpose:** Production bootstrap manifest for the UniGuru product repository
under the Samruddhi attached-product group.

**Why modified:** Moves UniGuru from example-only documentation into the real
production manifest directory using the product's published API contract,
repository provenance, declared health redirect handling, and a published
`/new_rag` fallback when `/ask` returns UniGuru's current safe-fallback
invalid-response signature.

**Key implementation areas:** Published base URL; `POST /ask` dispatch;
`POST /new_rag` response fallback; `GET /health` JSON health contract; source
repository and HEAD commit; operator-supplied UniGuru bearer token references;
declared redirect translator.

**Review focus:** Contract accuracy against `VJY123VJY/uniguru_ai`, no
embedded token value, correct request schema, fallback trigger specificity,
redirect handling, and honest behavior when the deployed domain serves a
frontend page instead of JSON health.

**Related tests:** `pratham/tests/test_bhiv_product_integration.py`.

## File: `contracts/production/product-samruddhi-trade-bot.json`

**Sprint change:** Added

**Purpose:** Production bootstrap manifest for the Samruddhi Trade Bot
repository.

**Why modified:** Moves Trade Bot from example-only documentation into the
real production manifest directory using the product's published MCP API
surface, repository provenance, and declared suspended-service health
normalization.

**Key implementation areas:** Published base URL; `POST /tools/predict`;
`POST /tools/analyze`; `GET /tools/health`; response schemas; source
repository and HEAD commit; declared service-suspended translator;
`predictions[].error` semantic rejection.

**Review focus:** Contract accuracy against `harshapawar136/trade-bot-main`,
external endpoint availability, schema strictness, absence of simulated or
localhost routing, never treating a suspended Render service as healthy, and
never counting HTTP 200 product execution errors as successful dispatches.

**Related tests:** `pratham/tests/test_bhiv_product_integration.py`.
