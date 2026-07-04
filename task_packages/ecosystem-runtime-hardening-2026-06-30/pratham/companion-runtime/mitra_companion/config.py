from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RuntimeSettings:
    service_root: Path
    data_root: Path
    database_path: Path
    telemetry_log_path: Path | None = None
    http_timeout_seconds: float = 10.0
    manifest_directory: Path | None = None

    @classmethod
    def from_environment(cls) -> "RuntimeSettings":
        service_root = Path(__file__).resolve().parents[3]
        data_root = Path(
            os.getenv(
                "MITRA_COMPANION_DATA_ROOT",
                str(service_root / "var"),
            )
        ).resolve()
        database_path = Path(
            os.getenv(
                "MITRA_COMPANION_DATABASE_PATH",
                str(data_root / "companion-runtime.db"),
            )
        ).resolve()
        manifest_directory = os.getenv("MITRA_COMPANION_MANIFEST_DIRECTORY")
        return cls(
            service_root=service_root,
            data_root=data_root,
            database_path=database_path,
            telemetry_log_path=Path(
                os.getenv(
                    "MITRA_COMPANION_TELEMETRY_LOG_PATH",
                    str(data_root / "runtime-telemetry.jsonl"),
                )
            ).resolve(),
            http_timeout_seconds=float(
                os.getenv("MITRA_COMPANION_HTTP_TIMEOUT_SECONDS", "10")
            ),
            manifest_directory=(
                Path(manifest_directory).resolve()
                if manifest_directory
                else None
            ),
        )

    def prepare(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        if self.telemetry_log_path is not None:
            self.telemetry_log_path.parent.mkdir(parents=True, exist_ok=True)
