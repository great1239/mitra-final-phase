# Security and IP Boundaries

## Non-negotiable boundary

The Companion Runtime is a bounded capability. It has no privileged knowledge
of the wider BHIV architecture and does not need it.

It depends only on:

- the published product attachment manifest;
- versioned session, context, transfer, and dispatch contracts;
- registered adapter ports;
- JSON Schema declared by the capability owner.

It does not depend on:

- private product source code;
- hidden services, tables, events, or routes;
- product names or repository layouts;
- governance, safety, knowledge, evidence, replay, or certification internals;
- assumptions about systems that are not present in a published contract.

## Enforced implementation rules

1. No product ID is selected by an implementation branch.
2. No product manifest filename is known by runtime code.
3. No transport protocol is selected by product identity.
4. Unknown transport modes fail closed during attachment.
5. Products cannot invoke one another through the runtime without explicit
   session/context transfer.
6. Product-private context is not copied during transfer.
7. Capability payloads are validated against the capability owner's published
   JSON Schema before dispatch.
8. Adapters receive only the versioned dispatch envelope and manifest metadata
   required by their port.

## Adapter seams

| Port | Purpose | Default adapters |
|---|---|---|
| `ManifestSourceAdapter` | discover published manifests | directory adapter |
| `TransportAdapter` | invoke a declared product endpoint | HTTP, loopback |
| `FileReader` | isolate filesystem reads in manifest discovery | local file reader |
| Store/registry ports | isolate session, context, attachment, and lifecycle logic from persistence implementations | SQLite runtime store |

New adapters are registered at composition time. They do not require changes to
the intent router, session runtime, context runtime, or attachment registry.
Concrete implementations meet only in the Companion Runtime composition root.

## IP posture

The runtime stores product-provided interface metadata and opaque context
values. It does not ingest or reproduce proprietary product algorithms. The
example manifests are synthetic fixtures and are not treated as ecosystem
architecture.
