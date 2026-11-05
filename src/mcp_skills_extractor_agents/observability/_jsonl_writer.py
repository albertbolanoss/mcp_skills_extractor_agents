"""Shared JSONL append helper backing the prompt log and agent transcript writers."""

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

SERVICE_NAME = "mcp_skills_extractor_agents"


def append_jsonl(directory: str, file_stem: str, record: dict[str, Any]) -> None:
    """Appends one JSON line to `{directory}/{file_stem}.jsonl`, creating the directory if needed."""
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, default=str)
    with (path / f"{file_stem}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def utc_now_iso() -> str:
    """Returns the current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def file_stem_for(correlation_id: str, agent: str) -> str:
    """Builds the per-tool file stem.

    Each tool owns its own file so the 4 extraction tools can run concurrently for the
    same `correlation_id` without interleaving writes to a shared file.
    """
    return f"{correlation_id or 'no-correlation-id'}__{agent}"
