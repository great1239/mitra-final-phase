# Failure Matrix

| Scenario | Expected behavior | Automated proof |
|---|---|---|
| Invalid runtime contract version | reject with `422` | `test_invalid_contract_returns_stable_error` |
| Duplicate product, same manifest | idempotent success | `test_duplicate_attachment_is_idempotent_but_manifest_change_conflicts` |
| Duplicate product, changed manifest | reject with conflict | same test |
| Incompatible attachment contract | reject before registration | `test_incompatible_attachment_contract_is_rejected` |
| Unknown intent | fail closed before dispatch | `test_unknown_intent_fails_closed` |
| Unknown capability | fail exact lookup with not found | `test_intent_discovery_filters_and_capability_lookup` |
| Intent registered in multiple capabilities | require explicit `capability_id` | `test_ambiguous_intent_requires_explicit_capability` |
| Degraded product route | remain discoverable but reject dispatch | `test_unavailable_product_is_discoverable_but_not_routable` |
| Payload violates registered intent schema | reject before creating dispatch receipt | `test_dispatch_validates_registered_input_schema` |
| Cross-product dispatch without transfer | reject with conflict | `test_cross_product_dispatch_requires_transfer` |
| Stale context revision | preserve current context and reject update | `test_context_loading_updates_and_revision_control` |
| Unknown context scope | reject instead of reading an undeclared partition | `test_unknown_context_scope_is_rejected` |
| Same workspace ID used by another actor | return an empty, independently owned workspace partition | `test_workspace_continuity_is_actor_scoped` |
| Ambiguous Phase 1 workspace owner | do not expose the legacy row to either actor | `test_phase1_workspace_migration_preserves_only_unambiguous_owners` |
| Product context transfer attempt | source product data excluded | `test_cross_product_transfer_does_not_copy_product_context` |
| Remote endpoint non-2xx | persist failed receipt, degrade product/runtime | `test_http_transport_failure_degrades_attachment` |
| Adapter raises unexpected exception | normalize error, persist failed receipt, degrade product/runtime | `test_unexpected_adapter_exception_is_persisted_as_failed_dispatch` |
| Process recreation | session and context resume from durable state | `test_session_and_context_continuity_survive_runtime_recreation` |
