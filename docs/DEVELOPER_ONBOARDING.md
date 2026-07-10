# Developer Onboarding

Use `docs/HANDOVER.md` for the complete clean-room rebuild, deployment,
operations, and transfer procedure. This document covers day-to-day extension
rules after the runtime is running.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m pytest
python scripts/production_readiness_gate.py
```

Run the demo:

```powershell
python scripts/run_demo.py
$env:MITRA_COMPANION_MANIFEST_DIRECTORY="contracts\examples"
$env:MITRA_COMPANION_ENVIRONMENT="development"
$env:MITRA_COMPANION_ALLOW_EXAMPLE_MANIFESTS="true"
$env:MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS="true"
$env:MITRA_COMPANION_ALLOW_LOOPBACK_MANIFESTS="true"
$env:MITRA_COMPANION_ALLOW_LOCALHOST_MANIFESTS="true"
$env:MITRA_COMPANION_REQUIRE_PRODUCTION_BOOTSTRAP_MANIFESTS="false"
mitra-companion serve --port 8090
```

`contracts/examples` is never the production bootstrap source. Production
uses `contracts/production` and rejects example, simulated, loopback, and
localhost-bound manifests unless an operator explicitly opts into them.

## Folder rule

Pratham implementation changes stay under `pratham/`. Integration changes
shared with other developers stay under `contracts/`. Do not add implementation
code to another developer's folder.

## Extension rule

To add a product:

1. publish a contract-compatible manifest;
2. implement an endpoint supported by a registered transport adapter;
3. attach the manifest through the API;
4. create a session bound to that product;
5. discover and dispatch its intent IDs.

No modification to `CompanionRuntime`, `IntentRouter`, or `ContextRuntime` is
required.

For self-attachment, use `contracts/examples/product-self-attach.http` as the
minimal API flow. For automated bootstrap, supply a `ManifestSourceAdapter` to
the composition root and call `attach_many` over the manifests it returns.

For a new protocol, implement and register `TransportAdapter`. For a new
manifest registry, implement `ManifestSourceAdapter`. See
`docs/ADAPTER_GUIDE.md`.

## Review checklist

Before handing off a change:

1. run `pytest`;
2. validate any new manifest against
   `contracts/schemas/product-attachment.schema.json`;
3. update `contracts/integration-contracts.json` when a public contract or
   example is added;
4. update the OpenAPI/catalog and the relevant maintained guide;
5. run the full test suite and readiness gate.

## Design guardrails

- Do not add natural-language intent classification here.
- Do not copy SHAKTI, governance, certification, external replay-authority, or
  external evidence-authority logic.
- Do not put product-specific branches in the router.
- Do not point production at `contracts/examples`.
- Do not use simulated or loopback manifests as production integrations.
- Do not expose another product's context partition.
- Do not store raw resume tokens.
- Do not accept breaking contract versions silently.
- Keep transports generic and responses JSON-object based.
