# Phase 3 - Intent Router

Phase 3 added manifest-derived intent registration, discovery, capability
lookup, and explicit routing.

## Model

Each attached manifest creates deterministic registrations:

```text
product_id + capability_id + intent_id
```

The registration contains product identity, attachment state, context scopes,
input schema, dispatch target, and metadata.

## Routing Rules

- The router accepts explicit registered IDs only.
- Ambiguous intent IDs require `capability_id`.
- A product-bound session cannot dispatch to another product without transfer.
- Detached products are hidden; degraded products are inspectable but not
  routable.
- Payloads are validated against the selected intent schema before transport.

## APIs

- `GET /api/v1/products/{product_id}/intent-registrations`
- `GET /api/v1/intents`
- `GET /api/v1/capabilities`
- `GET /api/v1/products/{product_id}/capabilities/{capability_id}`
- `POST /api/v1/intents/dispatch`

## Contracts

- `contracts/intent-router-policy.json`
- `contracts/schemas/intent-registration.schema.json`
- `contracts/schemas/capability-view.schema.json`
