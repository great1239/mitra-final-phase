# Mitra Sprint Code Packets

This directory is the mandatory bounded code-review surface for the final
runtime convergence sprint.

- Baseline branch: `main`
- Baseline commit: `1baaadf313f4d8a91018321db1317c5c6b385ccc`
- Packet prepared: `2026-07-23`
- Selection rule: only files added or modified after the baseline are listed.
- Review limit: no implementation area contains more than three critical
  files.

The packet is intentionally selective rather than a repository-wide change
inventory. Supporting manifests, screenshots, generated runtime outputs, and
historical reports remain available in their normal locations but are not
critical code entry points.

## Implementation Areas

1. [Core runtime orchestration](01-core-runtime.md)
2. [Deterministic replay and depository](02-replay-depository.md)
3. [BHIV runtime convergence](03-bhiv-convergence.md)
4. [Capability planning and companion continuity](04-capability-companion.md)
5. [Published API and contract surface](05-api-contracts.md)
6. [Independent production hosting](06-production-hosting.md)
7. [Production operations and observability](07-production-operations.md)
8. [Documentation and handover](08-handover.md)
9. [Testing and performance](09-testing-performance.md)
10. [Production manifest policy](10-production-manifest-policy.md)
11. [Docker deployment repair](11-docker-deployment-repair.md)
12. [Frontend compatibility connector](12-frontend-connector.md)
13. [Samruddhi product attachments](13-samruddhi-product-attachments.md)
14. [Samruddhi validation and docs](14-samruddhi-validation-docs.md)
15. [Validation report consolidation](15-validation-report-consolidation.md)
16. [TANTRA handover port](16-tantra-handover.md)
17. [Runtime coordination and continuity](17-runtime-coordination.md)
18. [Ashmit owner integration](18-ashmit-owner-integration.md)
19. [Real ecosystem topology](19-real-ecosystem-topology.md)
20. [Published contract services](20-published-contract-services.md)
21. [InsightFlow owner runtime](21-insightflow-owner-runtime.md)
22. [Live configuration validation](22-live-configuration-validation.md)
23. [Operational acceptance](23-operational-acceptance.md)
24. [Clean rebuild efficiency](24-clean-rebuild-efficiency.md)
25. [Public Bucket persistence](25-public-bucket-persistence.md)
26. [Deployment parity gate](26-deployment-parity-gate.md)
27. [Portable deployment validation](27-portable-deployment-validation.md)

## Reviewer Path

Start with core runtime orchestration, then follow the dispatch into replay and
BHIV convergence. Review contracts before hosting and operations. Finish with
handover to verify that an incoming engineer can rebuild and operate what the
code implements.
