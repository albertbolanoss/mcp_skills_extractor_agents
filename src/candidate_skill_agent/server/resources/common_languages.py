"""MCP resource: canonical spoken/written human-language taxonomy.

A single, shared vocabulary of human languages — each mapped to the alternate
spellings/names it's commonly found under in a resume or job posting (including
non-English spellings, e.g. "Español" for Spanish). Extraction tools/agents use it to
normalize whatever raw text they find to one canonical name, so every agent in the
pipeline reports languages in the same unified vocabulary instead of each one
inventing its own spelling.
"""

from ..mcp_server import mcp

COMMON_LANGUAGES: dict[str, list[str]] = {
    "English": ["Inglés", "Ingles"],
    "Spanish": ["Español", "Espanol", "Castellano"],
    "French": ["Français", "Francais"],
    "German": ["Deutsch", "Alemán", "Aleman"],
    "Portuguese": ["Português", "Portugues"],
    "Italian": ["Italiano"],
    "Mandarin Chinese": ["Chinese", "Mandarin", "Chino"],
    "Japanese": ["Japonés", "Japones"],
    "Korean": ["Coreano"],
    "Russian": ["Ruso"],
    "Arabic": ["Árabe", "Arabe"],
    "Hindi": [],
    "Dutch": ["Holandés", "Holandes"],
    "Polish": ["Polaco"],
    "Turkish": ["Turco"],
    "Vietnamese": ["Vietnamita"],
    "Thai": ["Tailandés", "Tailandes"],
    "Swedish": ["Sueco"],
    "Norwegian": ["Noruego"],
    "Danish": ["Danés", "Danes"],
    "Finnish": ["Finlandés", "Finlandes"],
    "Greek": ["Griego"],
    "Hebrew": ["Hebreo"],
    "Ukrainian": ["Ucraniano"],
    "Czech": ["Checo"],
    "Romanian": ["Rumano"],
    "Hungarian": ["Húngaro", "Hungaro"],
    "Indonesian": ["Indonesio", "Bahasa Indonesia"],
    "Catalan": ["Catalán"],
    "Basque": ["Euskera", "Vasco"],
}

# lowered canonical name/alias -> canonical name, built once at import time so
# tools/agents can normalize a raw extracted string in O(1).
_ALIAS_INDEX: dict[str, str] = {
    variant.lower(): canonical
    for canonical, aliases in COMMON_LANGUAGES.items()
    for variant in (canonical, *aliases)
}


def normalize_language(raw: str) -> str | None:
    """Maps a raw language string found in a resume/job posting to its canonical name.

    Lookup is case-insensitive against both canonical names and their known aliases.
    Returns None if `raw` isn't present in `COMMON_LANGUAGES`, leaving the caller
    free to keep the raw value or discard it.
    """
    return _ALIAS_INDEX.get(raw.strip().lower())


@mcp.resource(
    "resource://common-languages",
    name="common_languages",
    title="Common Spoken/Written Languages",
    description=(
        "Canonical taxonomy of spoken/written human languages with their common "
        "aliases (including non-English spellings). Agents extracting languages from "
        "a resume or job posting use it to normalize what they find to one shared, "
        "unified vocabulary."
    ),
    mime_type="application/json",
)
def common_languages() -> dict[str, list[str]]:
    """Returns the canonical human-language taxonomy."""
    return COMMON_LANGUAGES
