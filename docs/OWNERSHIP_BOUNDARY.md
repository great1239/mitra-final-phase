# Pratham Ownership Boundary

This document is the implementation allowlist for Mitra Phase V.
The same boundary is published machine-readably at
`contracts/ownership-boundary.json`.

## Owned runtime capabilities

| Owned capability | Implementation |
|---|---|
| Companion Runtime | `mitra_companion.runtime.CompanionRuntime` |
| Session Runtime | `mitra_session.runtime.SessionRuntime` |
| Context Runtime | `mitra_context.runtime.ContextRuntime` |
| Intent Router | `mitra_intent.runtime.IntentRouter` |
| Capability Attachment Runtime | capability registrations inside `mitra_attachment.runtime.AttachmentRuntime` |
| Runtime Lifecycle | `mitra_companion.lifecycle.RuntimeLifecycle` |
| Runtime State | `mitra_companion.constants.RuntimeState` and the lifecycle journal |
| Context Transfer Runtime | `SessionRuntime.transfer`, `ContextRuntime.initialize_transfer`, and the versioned transfer contract |
| Product Attachment Runtime | product manifests and lifecycle inside `AttachmentRuntime` |

Only these capabilities may contain executable behavior owned by Pratham.

## Explicitly external capabilities

Pratham does not implement or own:

- Conversation Design;
- Governance;
- Safety;
- Knowledge;
- Project Intelligence;
- Domain Intelligence;
- Evidence;
- Replay;
- Certification.

If another component supplies an explicit registered intent or receives a
dispatch, the Companion Runtime treats it as an external contract participant.
It does not infer, reproduce, approve, score, certify, govern, enrich, retrieve,
replay, or redesign that participant's behavior.

## Enforcement

The automated ownership tests verify that:

1. implementation folders are limited to the five assigned runtime folders;
2. all nine owned capabilities have concrete implementation symbols;
3. forbidden subsystem names do not appear in implementation module, class, or
   function names;
4. forbidden subsystem packages are not imported;
5. forbidden subsystem API routes are not exposed;
6. the intent router accepts only explicit registered intent IDs and contains
   no conversation or domain inference;
7. external integration occurs through published ports and adapters.

## Clarification: assignment evidence

The repository's `evidence/` directory contains screenshots, a demo transcript,
and a demo video required for assignment review. It is static submission
material. It is not an Evidence subsystem, evidence authority, evidence
producer, lineage engine, or runtime dependency.
