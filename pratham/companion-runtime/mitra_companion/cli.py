from __future__ import annotations

import argparse
import json
import os

import uvicorn

from .config import RuntimeSettings
from .runtime import CompanionRuntime


def main() -> None:
    parser = argparse.ArgumentParser(prog="mitra-companion")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the Companion Runtime API")
    serve.add_argument("--host", default=os.getenv("MITRA_COMPANION_HOST", "0.0.0.0"))
    serve.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MITRA_COMPANION_PORT", os.getenv("PORT", "8090"))),
    )
    serve.add_argument(
        "--workers",
        type=int,
        default=int(os.getenv("MITRA_COMPANION_UVICORN_WORKERS", "1")),
    )
    serve.add_argument(
        "--forwarded-allow-ips",
        default=os.getenv("MITRA_COMPANION_FORWARDED_ALLOW_IPS", "*"),
    )

    subparsers.add_parser("validate", help="Validate local runtime configuration")
    subparsers.add_parser("status", help="Print persisted runtime status")

    args = parser.parse_args()
    settings = RuntimeSettings.from_environment()
    settings.prepare()

    if args.command == "serve":
        uvicorn.run(
            "mitra_companion.app:app",
            host=args.host,
            port=args.port,
            workers=max(1, args.workers),
            proxy_headers=True,
            forwarded_allow_ips=args.forwarded_allow_ips,
        )
        return

    runtime = CompanionRuntime(settings)
    if args.command == "validate":
        print(
            json.dumps(
                {
                    "valid": True,
                    "database_path": str(settings.database_path),
                    "data_root": str(settings.data_root),
                },
                indent=2,
            )
        )
        return
    print(json.dumps(runtime.status(), indent=2))


if __name__ == "__main__":
    main()
