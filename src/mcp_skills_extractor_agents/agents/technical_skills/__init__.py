"""Technical-skills evidence-grounded extraction & evaluation pipeline.

Exports `run_technical_skills_pipeline`, the single entrypoint the MCP tool wrapper
(`server/tools/technical_skill_extraction.py`) delegates to.
"""

from .orchestrator import run_technical_skills_pipeline

__all__ = ["run_technical_skills_pipeline"]
