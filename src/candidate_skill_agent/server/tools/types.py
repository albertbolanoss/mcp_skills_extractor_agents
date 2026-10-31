"""Shared typing primitives for the extraction tools."""

from typing import Literal

DocumentTypeLiteral = Literal["resume", "job_posting"]
"""Identifies whether a tool's `content` argument is a candidate resume or a job posting."""
