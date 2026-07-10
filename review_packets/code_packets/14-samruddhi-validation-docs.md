# Samruddhi Validation And Docs

## File: `pratham/tests/test_bhiv_product_integration.py`

**Sprint change:** Modified

**Purpose:** Validates real BHIV product attachment behavior through Mitra's
published manifest and transport contracts.

**Why modified:** Added regression coverage for manifest-provided auth
headers, secret-backed Bearer tokens, and strict health contracts that reject
HTML fallback pages.

**Key implementation areas:** Mock HTTP product dispatch; environment-backed
token injection; JSON health enforcement; attachment degradation on health
contract failure.

**Review focus:** Whether tests verify actual request headers and output
states instead of merely checking that manifest files exist.

**Related tests:** This file is the focused suite for the Samruddhi attachment
change.

## File: `contracts/production/README.md`

**Sprint change:** Modified

**Purpose:** Documents which manifests are approved for production bootstrap
and how operators should configure them.

**Why modified:** Added the UniGuru and Samruddhi Trade Bot production
attachments, their repository sources, public endpoints, and the required
UniGuru runtime secret.

**Key implementation areas:** Approved attachment list; endpoint inventory;
credential handling; JSON health contract note.

**Review focus:** Operator clarity, no secret value disclosure, and agreement
with the manifest files.

**Related tests:** `scripts/production_readiness_gate.py`.

## File: `docs/BHIV_PRODUCT_INTEGRATION.md`

**Sprint change:** Modified

**Purpose:** Explains how BHIV products integrate with Mitra through published
contracts.

**Why modified:** Updated UniGuru and Samruddhi Trade Bot rows to include the
new production bootstrap manifests and the actual published API endpoints.

**Key implementation areas:** Product matrix; production manifest references;
UniGuru auth dependency; Trade Bot prediction and analysis routes.

**Review focus:** Contract accuracy and consistency with the production
manifest directory.

**Related tests:** `pratham/tests/test_bhiv_product_integration.py`.
