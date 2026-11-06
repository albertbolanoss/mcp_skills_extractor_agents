"""Per-tool-call observability wiring - see `documentation/prompt_log_and_agent_transcript.md`.

The actual prompt-log/agent-transcript JSONL writers live in `labs_agent_lib.observability`,
shared with the sibling `talent_distiller_agent` coordinator.
"""

from .tool_observability import ToolObservability

__all__ = ["ToolObservability"]
