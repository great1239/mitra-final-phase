# Mitra Sprint Code Packets

This directory is the mandatory bounded code-review surface for the final
runtime convergence sprint.

- Baseline branch: `main`
- Baseline commit: `1baaadf313f4d8a91018321db1317c5c6b385ccc`
- Packet prepared: `2026-07-10`
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

## Reviewer Path

Start with core runtime orchestration, then follow the dispatch into replay and
BHIV convergence. Review contracts before hosting and operations. Finish with
handover to verify that an incoming engineer can rebuild and operate what the
code implements.
