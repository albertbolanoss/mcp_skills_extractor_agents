"""Resume-extraction MCP tools, one module per tool.

`SkillAgentSettings.active_tools` decides which of these modules get imported — and
therefore which `@mcp.tool()` actually registers. Unset (the default) imports every
tool, which is what local development against the MCP Inspector wants. A future Helm
chart will set `MCP_SKILLS_EXTRACTOR_AGENTS_ACTIVE_TOOLS` per deployed pod to restrict it to
a subset of tools.
"""

from mcp_skills_extractor_agents.settings import ToolName, get_skill_agent_settings

_active_tools = get_skill_agent_settings().active_tools
_registered: list[str] = []

if _active_tools is None or ToolName.TECHNICAL_SKILLS in _active_tools:
    from .technical_skill_extraction import extract_technical_skills  # noqa: F401

    _registered.append(ToolName.TECHNICAL_SKILLS.value)

if _active_tools is None or ToolName.SOFT_SKILLS in _active_tools:
    from .soft_skill_extraction import extract_soft_skills  # noqa: F401

    _registered.append(ToolName.SOFT_SKILLS.value)

if _active_tools is None or ToolName.CERTIFICATIONS in _active_tools:
    from .certification_skill_extraction import extract_certifications  # noqa: F401

    _registered.append(ToolName.CERTIFICATIONS.value)

if _active_tools is None or ToolName.LANGUAGES in _active_tools:
    from .language_skill_extraction import extract_languages  # noqa: F401

    _registered.append(ToolName.LANGUAGES.value)

EXTRACTION_TOOL_NAMES: tuple[str, ...] = tuple(_registered)

__all__ = ["EXTRACTION_TOOL_NAMES"]
