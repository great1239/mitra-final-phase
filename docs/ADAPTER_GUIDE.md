# Adapter Guide

## Transport adapter

Implement the published `TransportAdapter` port:

```python
class QueueTransportAdapter:
    mode = "queue"

    def validate_target(self, manifest, target):
        if not target.endpoint.startswith("queue://"):
            raise ValueError("queue:// endpoint required")

    async def dispatch(self, *, route, envelope, manifest):
        # Publish only the versioned envelope through the queue client.
        return {"accepted": True, "message_id": "..."}
```

Register it at composition time:

```python
transport = CapabilityTransport(
    default_timeout_seconds=10,
    adapters=[QueueTransportAdapter()],
)
runtime = CompanionRuntime(settings, transport=transport)
```

The manifest may then declare `"mode": "queue"`. No runtime branch or product
case is added.

## Manifest-source adapter

Implement:

```python
class RegistryManifestSource:
    def load(self):
        return [ProductAttachmentManifest.model_validate(item) for item in rows]
```

Pass it to the API composition root:

```python
app = create_app(manifest_sources=[RegistryManifestSource()])
```

The bundled `DirectoryManifestSourceAdapter` discovers `*.json` files in a
configured directory. In development it can load examples and loopback
fixtures; in production the API composition root configures it to skip
example, simulated, loopback, and localhost-bound manifests unless the
operator explicitly opts in. Production startup manifests must include
`metadata.production_bootstrap: true`.

When multiple manifests are returned, the composition root calls `attach_many`.
Attachment is sequential and validates each manifest through the same public
contract path used by the API.

## Adapter constraints

- consume published contracts only;
- do not import a product implementation package;
- do not infer authority from manifest metadata;
- do not read hidden product storage;
- do not add product-specific branches to shared runtime modules;
- fail closed when the adapter mode or target is invalid.

## Persistence and module ports

Session, context, lifecycle, attachment, and routing modules type against narrow
ports from `mitra_companion.ports`; they do not import the SQLite store or one
another's concrete implementation classes. The composition root wires the
default implementations together.
