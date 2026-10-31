"""Configurable runtime and retry settings for specialized skill extraction agents."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ToolName(StrEnum):
    """Name of each extraction tool the MCP server can expose.

    Matches the `@mcp.tool()`-registered function name of its module under `server/tools/`.
    """

    TECHNICAL_SKILLS = "extract_technical_skills"
    SOFT_SKILLS = "extract_soft_skills"
    CERTIFICATIONS = "extract_certifications"
    LANGUAGES = "extract_languages"


class SkillAgentSettings(BaseSettings):
    """Environment-driven configuration for Claude SDK skill extraction agents."""

    model_config = SettingsConfigDict(env_prefix="CANDIDATE_SKILL_AGENT_")

    active_tools: frozenset[ToolName] | None = Field(
        default=None,
        description=(
            "Restricts the server to registering only these extraction tools, by tool name "
            "(e.g. 'extract_technical_skills,extract_certifications'). Unset registers every "
            "tool, which is what local development against the MCP Inspector wants. A future "
            "Helm chart will pin one or more values per deployed pod."
        ),
    )

    @field_validator("active_tools", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Accept a comma-separated env var string in addition to a real collection."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_skill_agent_settings() -> SkillAgentSettings:
    """Returns the cached SkillAgentSettings singleton."""
    return SkillAgentSettings()
