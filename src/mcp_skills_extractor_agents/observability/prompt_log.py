"""Prompt log: one audit line per outbound LLM request attempt - "what we asked the model".

Complements the agent transcript (the full play-by-play of a tool call). See
`documentation/prompt_log_and_agent_transcript.md` for the full cross-service design,
shared with the sibling `talent_distiller_agent` coordinator.
"""

from typing import Any

from mcp_skills_extractor_agents.settings import SkillAgentSettings

from ._jsonl_writer import SERVICE_NAME, append_jsonl, file_stem_for, utc_now_iso


class PromptLogWriter:
    """Appends one line per LLM call attempt to `{prompt_log_dir}/{correlation_id}__{tool_name}.jsonl`."""

    def __init__(self, settings: SkillAgentSettings) -> None:
        self.settings = settings

    def log_prompt(
        self,
        *,
        correlation_id: str,
        tool_name: str,
        model: str,
        system_prompt_name: str,
        user_prompt: str,
        attempt: int = 1,
    ) -> None:
        """Records one outbound prompt. No-ops when `settings.observability_enabled` is `False`."""
        if not self.settings.observability_enabled:
            return

        record: dict[str, Any] = {
            "timestamp": utc_now_iso(),
            "correlation_id": correlation_id,
            "service": SERVICE_NAME,
            "agent": tool_name,
            "event": "prompt",
            "model": model,
            "system_prompt_name": system_prompt_name,
            "user_prompt": user_prompt,
            "attempt": attempt,
        }
        append_jsonl(self.settings.prompt_log_dir, file_stem_for(correlation_id, tool_name), record)
