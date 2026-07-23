from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.models.registry import ApiKey


async def main() -> None:
    key = os.environ.get("INSIGHTFLOW_REGISTRY_API_KEY")
    if not key:
        raise SystemExit("INSIGHTFLOW_REGISTRY_API_KEY is required")
    owner = "Mitra-Runtime"
    async with AsyncSessionLocal() as database:
        existing = await database.execute(
            select(ApiKey).where(ApiKey.owner_name == owner)
        )
        record = existing.scalar_one_or_none()
        if record is None:
            database.add(
                ApiKey(
                    key=key,
                    owner_name=owner,
                    description="Mitra canonical runtime telemetry bridge",
                    is_active=True,
                )
            )
        else:
            record.key = key
            record.is_active = True
        await database.commit()
    print("InsightFlow API key configured for Mitra-Runtime")


if __name__ == "__main__":
    asyncio.run(main())
