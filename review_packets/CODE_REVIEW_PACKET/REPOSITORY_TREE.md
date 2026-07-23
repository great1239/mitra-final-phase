# Owned Repository Tree

Only Mitra-owned implementation and its direct contracts are shown.

```text
api/
  index.py                         public serverless process entry
pratham/
  companion-runtime/
    mitra_companion/
      api.py                       HTTP and operator surface
      runtime.py                   composition and capability selection
      ecosystem.py                 strict owner-contract chain and replay
      store.py                     durable executions, stages, attempts
      config.py                    deployment and owner configuration
      contracts.py                 versioned request models
      depository.py                immutable artifacts and lineage
      telemetry.py                 runtime events and metrics
      frontend_connector.py        existing website compatibility adapter
  session-runtime/                 session identity and continuity
  context-runtime/                 isolated context scopes and transfer
  intent-router/                   manifest-derived capability routing
  attachment-runtime/              manifest validation and state
contracts/
  api/companion-runtime.openapi.yaml
  schemas/ecosystem-execution.schema.json
  schemas/ecosystem-replay-validation.schema.json
  production/                      approved UniGuru and Samruddhi manifests
deploy/
  production.env.example
docs/
  TANTRA_ECOSYSTEM_CONVERGENCE.md
review_packets/
  REVIEW_PACKET.md
  CODE_REVIEW_PACKET/
  SCREENSHOTS/
```

Raj, KESHAV, Ashmit, Bucket, Karma, PRANA, InsightFlow, attached product logic,
and Central Depository acceptance remain externally owned.
