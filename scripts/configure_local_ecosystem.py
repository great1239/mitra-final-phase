from __future__ import annotations

import argparse
import json
import secrets
import subprocess
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
ASHMIT_ENV = ROOT.parent / "Ashmit-Mitra-T42" / "backend" / ".env"
BUCKET_ROOT = ROOT.parent / "BHIV-Bucket"
UNIGURU_ENV = ROOT.parent / "uniguru_ai" / ".env.local"
TRADEBOT_ROOT = ROOT.parent / "trade-bot-main" / "backend"
KESHAV_ROOT = ROOT.parent / "KESHAV-4"
TARGET_ENV = ROOT / ".env"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_local_mongo_uri(
    username: str,
    password: str,
    database_name: str,
) -> str:
    return (
        f"mongodb://{quote(username, safe='')}:{quote(password, safe='')}"
        "@ashmit-mongo:27017/"
        f"{quote(database_name, safe='')}?authSource=admin"
    )


def source_revision() -> str:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{revision}-dirty" if dirty else revision


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rotate-insightflow-keys",
        action="store_true",
        help="replace only the generated registry and bridge API keys",
    )
    args = parser.parse_args()

    if not ASHMIT_ENV.exists():
        raise SystemExit(f"Ashmit environment file is missing: {ASHMIT_ENV}")
    if not (BUCKET_ROOT / "main.py").exists():
        raise SystemExit(
            "Bucket owner repository is missing. Clone "
            "https://github.com/siddheshnarkar76/bucket.git to "
            f"{BUCKET_ROOT}"
        )
    ashmit = read_env(ASHMIT_ENV)
    required = ["API_KEY", "JWT_SECRET_KEY", "MONGODB_URI", "DATABASE_NAME"]
    missing = [key for key in required if not ashmit.get(key)]
    if missing:
        raise SystemExit(f"Ashmit environment is missing: {', '.join(missing)}")
    if not UNIGURU_ENV.exists():
        raise SystemExit(f"UniGuru environment file is missing: {UNIGURU_ENV}")
    if not (TRADEBOT_ROOT / "Dockerfile").exists() or not (
        TRADEBOT_ROOT / "api_server.py"
    ).exists():
        raise SystemExit(
            "Trade Bot owner repository is missing or incomplete. Clone "
            "https://github.com/harshapawar136/trade-bot-main to "
            f"{TRADEBOT_ROOT.parent}"
        )
    if not (KESHAV_ROOT / "Dockerfile").exists() or not (
        KESHAV_ROOT / "api.py"
    ).exists():
        raise SystemExit(
            "KESHAV owner repository is missing or incomplete. Clone "
            "https://github.com/blackholeinfiverse106-creator/KESHAV-4 "
            f"to {KESHAV_ROOT}"
        )
    uniguru = read_env(UNIGURU_ENV)
    uniguru_required = [
        "UNIGURU_API_TOKEN",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
    ]
    uniguru_missing = [key for key in uniguru_required if not uniguru.get(key)]
    if uniguru_missing:
        raise SystemExit(
            "UniGuru environment is missing: " + ", ".join(uniguru_missing)
        )
    uniguru_token = uniguru["UNIGURU_API_TOKEN"]

    existing = read_env(TARGET_ENV) if TARGET_ENV.exists() else {}

    def local_secret(name: str, *, rotate: bool = False) -> str:
        if not rotate and existing.get(name):
            return existing[name]
        return secrets.token_urlsafe(32)

    mongo_user = existing.get("ASHMIT_MONGO_ROOT_USER") or "mitra_ashmit"
    mongo_password = local_secret("ASHMIT_MONGO_ROOT_PASSWORD")
    database_name = ashmit["DATABASE_NAME"]
    local_mongo_uri = build_local_mongo_uri(
        mongo_user,
        mongo_password,
        database_name,
    )

    product_endpoint_overrides = {
        "https://uni-guru.in": "http://uniguru:8000",
        "https://trade-bot-api.onrender.com": "http://trade-bot:8000",
    }
    values = {
        "ASHMIT_BACKEND_CONTEXT": "../Ashmit-Mitra-T42/backend",
        "ASHMIT_API_KEY": ashmit["API_KEY"],
        "ASHMIT_MONGODB_URI": ashmit["MONGODB_URI"],
        "ASHMIT_LOCAL_MONGODB_URI": local_mongo_uri,
        "ASHMIT_MONGO_ROOT_USER": mongo_user,
        "ASHMIT_MONGO_ROOT_PASSWORD": mongo_password,
        "ASHMIT_DATABASE_NAME": database_name,
        "ASHMIT_JWT_SECRET_KEY": ashmit["JWT_SECRET_KEY"],
        "BUCKET_CONTEXT": "../BHIV-Bucket",
        "BUCKET_MONGODB_URI": local_mongo_uri,
        "BUCKET_REDIS_PASSWORD": local_secret("BUCKET_REDIS_PASSWORD"),
        "TRADEBOT_BACKEND_CONTEXT": "../trade-bot-main/backend",
        "KESHAV_CONTEXT": "../KESHAV-4",
        "UNIGURU_CONTEXT": "../uniguru_ai",
        "UNIGURU_ENV_FILE": "../uniguru_ai/.env.local",
        "UNIGURU_SUPABASE_URL": uniguru["SUPABASE_URL"],
        "UNIGURU_SUPABASE_ANON_KEY": uniguru["SUPABASE_ANON_KEY"],
        "MITRA_PRODUCT_UNIGURU_BEARER_TOKEN": uniguru_token,
        "MITRA_PRODUCT_UNIGURU_RAG_TOKEN": uniguru_token,
        "MITRA_COMPANION_ENDPOINT_OVERRIDES_JSON": json.dumps(
            product_endpoint_overrides,
            separators=(",", ":"),
        ),
        "MITRA_COMPANION_RELEASE_REVISION": source_revision(),
        "INSIGHTFLOW_POSTGRES_USER": "bhiv",
        "INSIGHTFLOW_POSTGRES_PASSWORD": local_secret(
            "INSIGHTFLOW_POSTGRES_PASSWORD"
        ),
        "INSIGHTFLOW_POSTGRES_DATABASE": "bhiv_registry",
        "INSIGHTFLOW_REGISTRY_API_KEY": local_secret(
            "INSIGHTFLOW_REGISTRY_API_KEY",
            rotate=args.rotate_insightflow_keys,
        ),
        "INSIGHTFLOW_BRIDGE_API_KEY": local_secret(
            "INSIGHTFLOW_BRIDGE_API_KEY",
            rotate=args.rotate_insightflow_keys,
        ),
        "RAJ_API_KEY": local_secret("RAJ_API_KEY"),
        "RAJ_ENDPOINT_OVERRIDES_JSON": json.dumps(
            {
                "https://pratham-bhiv-bucket.onrender.com": (
                    "http://bucket:8000"
                ),
                **product_endpoint_overrides,
            },
            separators=(",", ":"),
        ),
        "KARMA_GENESIS_HASH": "0" * 64,
    }
    content = "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
    temporary = TARGET_ENV.with_suffix(".env.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(TARGET_ENV)
    print(
        "Configured Git-ignored local ecosystem variables: "
        + ", ".join(values)
    )


if __name__ == "__main__":
    main()
