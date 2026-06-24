class CompanionRuntimeError(RuntimeError):
    status_code = 400
    code = "COMPANION_RUNTIME_ERROR"


class ContractCompatibilityError(CompanionRuntimeError):
    status_code = 422
    code = "CONTRACT_INCOMPATIBLE"


class ResourceNotFoundError(CompanionRuntimeError):
    status_code = 404
    code = "RESOURCE_NOT_FOUND"


class ResourceConflictError(CompanionRuntimeError):
    status_code = 409
    code = "RESOURCE_CONFLICT"


class ContextRevisionConflict(ResourceConflictError):
    code = "CONTEXT_REVISION_CONFLICT"


class IntentRoutingError(CompanionRuntimeError):
    status_code = 422
    code = "INTENT_ROUTING_FAILED"


class AmbiguousIntentError(IntentRoutingError):
    status_code = 409
    code = "INTENT_AMBIGUOUS"


class AttachmentValidationError(CompanionRuntimeError):
    status_code = 422
    code = "ATTACHMENT_INVALID"


class TransportError(CompanionRuntimeError):
    status_code = 502
    code = "CAPABILITY_TRANSPORT_FAILED"

