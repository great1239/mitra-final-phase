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
