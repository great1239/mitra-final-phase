# Production Manifests

This directory is the only manifest directory used by production deployment
profiles.

Do not copy files from `contracts/examples` into this directory unless the
target product is real, reachable from the deployed runtime, and approved for
startup attachment.

Production bootstrap manifests must:

- use a real product endpoint;
- avoid `attachment_mode: "simulated"`;
- avoid `dispatch.mode: "loopback"`;
- avoid localhost base URLs;
- include `metadata.production_bootstrap: true`.

Products can also connect at runtime through `POST /api/v1/products/connect`.

## Approved Samruddhi Attachments

This directory currently includes two real BHIV product manifests:

- `product-samruddhi-uniguru.json`
  - repository: `https://github.com/VJY123VJY/uniguru_ai`
  - base URL: `https://uni-guru.in`
  - dispatch: `POST /ask`
  - health: `GET /health`
  - runtime secret required for dispatch:
    `MITRA_PRODUCT_UNIGURU_BEARER_TOKEN`

- `product-samruddhi-trade-bot.json`
  - repository: `https://github.com/harshapawar136/trade-bot-main`
  - base URL: `https://trade-bot-api.onrender.com`
  - dispatch: `POST /tools/predict`, `POST /tools/analyze`
  - health: `GET /tools/health`

Both manifests require JSON health responses through `metadata.health_contract`.
A frontend fallback page, even with HTTP 200, is reported as unhealthy.
