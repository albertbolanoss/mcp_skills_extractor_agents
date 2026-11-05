"""Per-tool-call observability recorder.

Wires the prompt log and agent transcript writers for one extraction-tool invocation,
so the 4 near-identical tool files in `server/tools/` can be instrumented identically
without duplicating the JSONL-writing logic in each of them.
"""

from typing import Any

from mcp_skills_extractor_agents.settings import SkillAgentSettings

from .agent_transcript import AgentTranscriptWriter
from .prompt_log import PromptLogWriter


class ToolObservability:
    """Records one extraction tool call's prompts/responses under `correlation_id`."""

    def __init__(
        self,
        settings: SkillAgentSettings,
        *,
        tool_name: str,
        correlation_id: str,
        model: str,
        system_prompt: str,
    ) -> None:
        self.tool_name = tool_name
        self.correlation_id = correlation_id
        self.model = model
        self.system_prompt = system_prompt
        self._prompt_log = PromptLogWriter(settings)
        self._transcript = AgentTranscriptWriter(settings)

    def log_attempt_prompt(self, *, prompt: str, attempt: int) -> None:
        """Call right before `_ask(client, prompt)` on every attempt."""
        self._prompt_log.log_prompt(
            correlation_id=self.correlation_id,
            tool_name=self.tool_name,
            model=self.model,
            system_prompt_name=self.tool_name,
            user_prompt=prompt,
            attempt=attempt,
        )
        if attempt == 1:
            self._transcript.session_start(
                self.correlation_id,
                self.tool_name,
                model=self.model,
                system_prompt=self.system_prompt,
                user_prompt=prompt,
            )

    def log_attempt_response(self, *, text: str, session_id: str | None) -> None:
        """Call right after `_ask(...)` returns, with the raw agent text."""
        self._transcript.assistant_text(
            self.correlation_id, self.tool_name, text=text, session_id=session_id
        )

    def log_retry(self, *, attempt: int, attempts: int, error: str) -> None:
        """Call when validation fails and a self-correction turn is queued."""
        self._transcript.retry(
            self.correlation_id, self.tool_name, attempt=attempt, attempts=attempts, error=error
        )

    def log_success(self, *, result: Any) -> None:
        """Call once the parsed/validated result is ready to return."""
        self._transcript.session_end(self.correlation_id, self.tool_name, is_error=False, result=result)

    def log_failure(self, *, error: str) -> None:
        """Call once every attempt has been exhausted, right before raising."""
        self._transcript.session_end(self.correlation_id, self.tool_name, is_error=True, error=error)
