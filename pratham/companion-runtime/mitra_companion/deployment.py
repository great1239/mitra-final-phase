from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from .utils import utc_now

if TYPE_CHECKING:
    from .config import RuntimeSettings


_OWNER_REQUIREMENTS = {
    "raj": (
        ("raj_workflow_base_url", "MITRA_RAJ_WORKFLOW_BASE_URL"),
    ),
    "ashmit": (
        ("bhiv_ashmit_base_url", "MITRA_BHIV_ASHMIT_BASE_URL"),
        ("bhiv_ashmit_api_key", "MITRA_BHIV_ASHMIT_API_KEY"),
    ),
    "bucket": (
        ("bhiv_bucket_base_url", "MITRA_BHIV_BUCKET_BASE_URL"),
    ),
    "keshav": (
        ("bhiv_keshav_base_url", "MITRA_BHIV_KESHAV_BASE_URL"),
    ),
    "karma": (
        ("bhiv_karma_base_url", "MITRA_BHIV_KARMA_BASE_URL"),
    ),
    "prana": (
        ("bhiv_prana_base_url", "MITRA_BHIV_PRANA_BASE_URL"),
    ),
    "insightflow": (
        (
            "bhiv_insightflow_ingest_url",
            "MITRA_BHIV_INSIGHTFLOW_INGEST_URL",
        ),
    ),
    "central_depository": (
        (
            "central_depository_base_url",
            "MITRA_CENTRAL_DEPOSITORY_BASE_URL",
        ),
    ),
}

_OWNER_ENDPOINTS = {
    "raj": "raj_workflow_base_url",
    "ashmit": "bhiv_ashmit_base_url",
    "bucket": "bhiv_bucket_base_url",
    "keshav": "bhiv_keshav_base_url",
    "karma": "bhiv_karma_base_url",
    "prana": "bhiv_prana_base_url",
    "insightflow": "bhiv_insightflow_ingest_url",
    "central_depository": "central_depository_base_url",
}

_LOCAL_HOSTS = {
    "0.0.0.0",
    "127.0.0.1",
    "::1",
    "host.docker.internal",
    "localhost",
}


def _public_endpoint_error(value: str) -> str | None:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        return "must use HTTPS"
    if not hostname:
        return "must be an absolute URL with a hostname"
    if (
        hostname in _LOCAL_HOSTS
        or hostname.endswith((".internal", ".local", ".localhost"))
        or "." not in hostname
    ):
        return "must not use a loopback, local, or Docker-only hostname"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return None
    if not address.is_global:
        return "must not use a private, loopback, or reserved IP address"
    return None


def _configured_modules(
    settings: RuntimeSettings,
) -> tuple[list[str], dict[str, list[str]]]:
    configured: list[str] = []
    missing: dict[str, list[str]] = {}
    for module, requirements in _OWNER_REQUIREMENTS.items():
        missing_settings = [
            variable
            for attribute, variable in requirements
            if not getattr(settings, attribute)
        ]
        if missing_settings:
            missing[module] = missing_settings
        else:
            configured.append(module)
    return configured, missing


def deployment_parity_report(
    settings: RuntimeSettings,
) -> dict[str, Any]:
    configured, missing = _configured_modules(settings)
    blocking_issues: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    endpoint_checks: dict[str, dict[str, Any]] = {}

    if settings.require_ecosystem_ready:
        for module, variables in missing.items():
            blocking_issues.append(
                {
                    "code": "OWNER_CONFIGURATION_MISSING",
                    "component": module,
                    "message": (
                        f"{module} is required by this deployment but is not "
                        "fully configured"
                    ),
                    "required_settings": variables,
                }
            )

    for module, attribute in _OWNER_ENDPOINTS.items():
        value = getattr(settings, attribute)
        if not value:
            endpoint_checks[module] = {
                "configured": False,
                "portable": False,
            }
            continue
        error = _public_endpoint_error(value)
        portable = error is None
        endpoint_checks[module] = {
            "configured": True,
            "portable": portable,
        }
        if settings.require_public_owner_endpoints and error is not None:
            blocking_issues.append(
                {
                    "code": "OWNER_ENDPOINT_NOT_PORTABLE",
                    "component": module,
                    "message": f"{module} endpoint {error}",
                    "required_settings": [
                        _OWNER_REQUIREMENTS[module][0][1]
                    ],
                }
            )

    if settings.require_public_owner_endpoints:
        for source, target in settings.endpoint_overrides.items():
            error = _public_endpoint_error(target)
            if error is not None:
                blocking_issues.append(
                    {
                        "code": "ENDPOINT_OVERRIDE_NOT_PORTABLE",
                        "component": "product_endpoint_overrides",
                        "message": (
                            f"override for {source} {error}"
                        ),
                        "required_settings": [
                            "MITRA_COMPANION_ENDPOINT_OVERRIDES_JSON"
                        ],
                    }
                )

    durable = (
        settings.runtime_storage_mode == "persistent"
        and settings.persistent_runtime_enabled
    )
    if settings.require_durable_runtime and not durable:
        blocking_issues.append(
            {
                "code": "DURABLE_RUNTIME_STORAGE_REQUIRED",
                "component": "runtime_storage",
                "message": (
                    "this deployment requires persistent runtime state, but "
                    "the selected platform is configured for ephemeral or "
                    "non-persistent execution"
                ),
                "required_settings": [
                    "MITRA_COMPANION_RUNTIME_STORAGE_MODE=persistent",
                    "MITRA_COMPANION_PERSISTENT_RUNTIME_ENABLED=true",
                ],
            }
        )

    manifest_policy_portable = not any(
        (
            settings.allow_example_manifests,
            settings.allow_simulated_manifests,
            settings.allow_loopback_manifests,
            settings.allow_localhost_manifests,
        )
    )
    if settings.require_ecosystem_ready and not manifest_policy_portable:
        blocking_issues.append(
            {
                "code": "PRODUCTION_MANIFEST_POLICY_RELAXED",
                "component": "manifest_policy",
                "message": (
                    "strict ecosystem readiness cannot allow example, "
                    "simulated, loopback, or localhost manifests"
                ),
                "required_settings": [
                    "MITRA_COMPANION_ALLOW_EXAMPLE_MANIFESTS=false",
                    "MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS=false",
                    "MITRA_COMPANION_ALLOW_LOOPBACK_MANIFESTS=false",
                    "MITRA_COMPANION_ALLOW_LOCALHOST_MANIFESTS=false",
                ],
            }
        )

    manifest_directory_available = bool(
        settings.manifest_directory
        and settings.manifest_directory.is_dir()
    )
    if (
        settings.require_ecosystem_ready
        and settings.require_production_bootstrap_manifests
        and not manifest_directory_available
    ):
        blocking_issues.append(
            {
                "code": "PRODUCTION_MANIFEST_DIRECTORY_MISSING",
                "component": "manifest_policy",
                "message": (
                    "the required production manifest directory is not "
                    "available in this deployment"
                ),
                "required_settings": [
                    "MITRA_COMPANION_MANIFEST_DIRECTORY"
                ],
            }
        )

    if settings.release_revision == "unknown":
        warnings.append(
            {
                "code": "RELEASE_REVISION_UNKNOWN",
                "message": (
                    "set MITRA_COMPANION_RELEASE_REVISION or expose the "
                    "platform commit SHA to detect stale deployments"
                ),
            }
        )

    return {
        "ready": not blocking_issues,
        "checked_at": utc_now(),
        "platform": settings.deployment_platform,
        "environment": settings.deployment_environment,
        "release_revision": settings.release_revision,
        "enforcement": {
            "ecosystem_configuration": settings.require_ecosystem_ready,
            "public_owner_endpoints": (
                settings.require_public_owner_endpoints
            ),
            "durable_runtime": settings.require_durable_runtime,
        },
        "owner_configuration": {
            "configured_modules": configured,
            "pending_modules": sorted(missing),
            "endpoint_checks": endpoint_checks,
        },
        "runtime_storage": {
            "mode": settings.runtime_storage_mode,
            "persistent_runtime_enabled": (
                settings.persistent_runtime_enabled
            ),
            "durable": durable,
        },
        "manifest_policy": {
            "portable": manifest_policy_portable,
            "directory_available": manifest_directory_available,
        },
        "blocking_issues": blocking_issues,
        "warnings": warnings,
    }
