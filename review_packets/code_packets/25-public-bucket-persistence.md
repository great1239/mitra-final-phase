# Public Bucket Persistence

Bucket implementation source:
[`great1239/bhiv-bucket@contract-api`](https://github.com/great1239/bhiv-bucket/tree/contract-api)
at commit `67522b41a7593ed0aff9baa7bf32b664e86f2035`. Its three
changed implementation files are bounded in that repository; this packet lists
only files present in the Mitra review tree.

## File: `.env.example`

**Sprint change:** Replaced the inaccessible owner Bucket origin with the
personal public Bucket for both runtime storage and Bucket-backed handover.

**Purpose:** Provides the rebuildable public endpoint configuration without
containing credentials.

**Why modified:** The previous deployment could not be configured with the
required Redis and durable artifact storage.

**Key implementation areas:** `MITRA_BHIV_BUCKET_BASE_URL` and
`MITRA_CENTRAL_DEPOSITORY_BASE_URL`.

**Review focus:** Local Compose remains on `http://bucket:8000`; only the
published origin changed.

**Related tests:** Eight focused configuration tests, JSON validation,
Compose configuration validation, and the complete 161-test regression passed.

## File: `.vercelignore`

**Sprint change:** Explicitly excluded `.env` and `.env.*` while retaining
`.env.example`.

**Purpose:** Prevents local runtime secrets from entering Vercel source
uploads.

**Why modified:** The project already had a Vercel-specific ignore file, so
implicit CLI exclusions were not a sufficient packaging guarantee.

**Key implementation areas:** Secret-file exclusion and public example
retention.

**Review focus:** The production upload must contain configuration names, not
local credential values.

**Related tests:** The production deployment completed after the exclusion was
added; the runtime secret summary exposes names only and redacts values.

## File: `review_packets/testing/bucket-public-storage-live-evidence.json`

**Sprint change:** Replaced the obsolete owner-endpoint record with the exact
personal Bucket append, read, hash, replay, restart, post-restart, and hosted
Mitra preflight observations.

**Purpose:** Retains independently inspectable runtime output without a proof
generator.

**Why modified:** The prior record neither used the active endpoint nor proved
durability across restart.

**Key implementation areas:** Canonical SHA-256 match, Atlas-backed restart
persistence, Redis health, Vercel-to-Render Bucket health, and latest-hash
calls.

**Review focus:** `simulation=false`; the hosted execution failed closed only
for modules without public URLs, while Bucket and Bucket-backed Central
Depository returned HTTP 200 with `accepted` transport status.

**Related tests:** Four focused Mongo storage tests passed; live append,
read-back, replay, restart, and hosted preflight checks passed.
