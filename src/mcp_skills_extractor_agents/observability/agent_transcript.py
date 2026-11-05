"""Agent transcript: the full, ordered play-by-play of one extraction tool call.

Complements the prompt log (a flat index of what was asked). See
`documentation/prompt_log_and_agent_transcript.md` for the full cross-service design,
shared with the sibling `talent_distiller_agent` coordinator.
"""

from typing import Any

from mcp_skills_extractor_agents.settings import SkillAgentSettings

from ._jsonl_writer import SERVICE_NAME, append_jsonl, file_stem_for, utc_now_iso


class AgentTranscriptWriter:
    """Appends one event line per step of a tool call to `{agent_transcript_dir}/{correlation_id}__{tool_name}.jsonl`."""

    def __init__(self, settings: SkillAgentSettings) -> None:
        self.settings = settings

    def _write(
        self,
        correlation_id: str,
        agent: str,
        event: str,
        *,
        session_id: str | None = None,
        **fields: Any,
    ) -> None:
        if not self.settings.observability_enabled:
            return

        record: dict[str, Any] = {
            "timestamp": utc_now_iso(),
            "correlation_id": correlation_id,
            "service": SERVICE_NAME,
            "agent": agent,
            "session_id": session_id,
            "event": event,
            **fields,
        }
        append_jsonl(self.settings.agent_transcript_dir, file_stem_for(correlation_id, agent), record)

    def session_start(
        self,
        correlation_id: str,
        agent: str,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> None:
        """Records the opening of the first attempt, including the system prompt once."""
        self._write(
            correlation_id,
            agent,
            "session_start",
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    def assistant_text(
        self,
        correlation_id: str,
        agent: str,
        *,
        text: str,
        session_id: str | None = None,
    ) -> None:
        """Records the raw text the sub-agent returned for one attempt."""
        self._write(correlation_id, agent, "assistant_text", text=text, session_id=session_id)

    def retry(self, correlation_id: str, agent: str, *, attempt: int, attempts: int, error: str) -> None:
        """Records a self-correction turn triggered by a schema/validation failure."""
        self._write(correlation_id, agent, "retry", attempt=attempt, attempts=attempts, error=error)

    def session_end(
        self,
        correlation_id: str,
        agent: str,
        *,
        is_error: bool,
        result: Any = None,
        error: str | None = None,
    ) -> None:
        """Records the final outcome of the tool call."""
        self._write(correlation_id, agent, "session_end", is_error=is_error, result=result, error=error)
