"""Tests for the common-languages MCP resource."""

from mcp_skills_extractor_agents.server.resources.common_languages import (
    COMMON_LANGUAGES,
    common_languages,
    normalize_language,
)


def test_common_languages_has_multiple_languages():
    # Act
    languages = common_languages()

    # Assert
    assert languages is COMMON_LANGUAGES
    assert len(languages) > 10
    assert {"English", "Spanish", "French"} <= languages.keys()


def test_normalize_language_resolves_known_alias():
    # Act / Assert
    assert normalize_language("Español") == "Spanish"
    assert normalize_language("Ingles") == "English"
    assert normalize_language("  Francais ") == "French"


def test_normalize_language_is_case_insensitive_on_canonical_name():
    # Act / Assert
    assert normalize_language("english") == "English"
    assert normalize_language("ENGLISH") == "English"


def test_normalize_language_returns_none_for_unknown_language():
    # Act / Assert
    assert normalize_language("some-made-up-language") is None
