"""MCP resource: canonical IT certification taxonomy.

A single, shared vocabulary of professional IT certifications — grouped by category,
each mapped to its issuing organization and the alternate spellings/abbreviations it's
commonly found under in a resume or job posting. Extraction tools/agents use it to
normalize whatever raw text they find (e.g. "AWS SAA", "CISSP") to one canonical title
and issuer (e.g. "AWS Certified Solutions Architect - Associate" / "Amazon Web
Services"), so every agent in the pipeline reports certifications in the same unified
language instead of each one inventing its own spelling.
"""

from ..mcp_server import mcp

COMMON_CERTIFICATIONS: dict[str, dict[str, dict[str, str | list[str]]]] = {
    "cloud": {
        "AWS Certified Solutions Architect - Associate": {
            "issuer": "Amazon Web Services",
            "aliases": ["AWS SAA", "AWS Solutions Architect Associate", "AWS CSA-A"],
        },
        "AWS Certified Solutions Architect - Professional": {
            "issuer": "Amazon Web Services",
            "aliases": ["AWS SAP", "AWS Solutions Architect Professional"],
        },
        "AWS Certified Developer - Associate": {
            "issuer": "Amazon Web Services",
            "aliases": ["AWS CDA", "AWS Developer Associate"],
        },
        "AWS Certified SysOps Administrator - Associate": {
            "issuer": "Amazon Web Services",
            "aliases": ["AWS SysOps Associate"],
        },
        "Microsoft Certified: Azure Administrator Associate": {
            "issuer": "Microsoft",
            "aliases": ["AZ-104", "Azure Administrator Associate"],
        },
        "Microsoft Certified: Azure Solutions Architect Expert": {
            "issuer": "Microsoft",
            "aliases": ["AZ-305", "Azure Solutions Architect Expert"],
        },
        "Google Cloud Professional Cloud Architect": {
            "issuer": "Google Cloud",
            "aliases": ["GCP Professional Cloud Architect"],
        },
        "Google Cloud Associate Cloud Engineer": {
            "issuer": "Google Cloud",
            "aliases": ["GCP Associate Cloud Engineer"],
        },
    },
    "security": {
        "CompTIA Security+": {
            "issuer": "CompTIA",
            "aliases": ["Security+", "SecurityPlus"],
        },
        "Certified Information Systems Security Professional": {
            "issuer": "ISC2",
            "aliases": ["CISSP"],
        },
        "Certified Ethical Hacker": {
            "issuer": "EC-Council",
            "aliases": ["CEH"],
        },
        "Certified Information Security Manager": {
            "issuer": "ISACA",
            "aliases": ["CISM"],
        },
        "GIAC Security Essentials": {
            "issuer": "GIAC",
            "aliases": ["GSEC"],
        },
    },
    "project_management": {
        "Project Management Professional": {
            "issuer": "Project Management Institute",
            "aliases": ["PMP"],
        },
        "Certified ScrumMaster": {
            "issuer": "Scrum Alliance",
            "aliases": ["CSM"],
        },
        "Certified Scrum Product Owner": {
            "issuer": "Scrum Alliance",
            "aliases": ["CSPO"],
        },
        "PMI Agile Certified Practitioner": {
            "issuer": "Project Management Institute",
            "aliases": ["PMI-ACP"],
        },
    },
    "devops": {
        "Certified Kubernetes Administrator": {
            "issuer": "Cloud Native Computing Foundation",
            "aliases": ["CKA"],
        },
        "Docker Certified Associate": {
            "issuer": "Docker",
            "aliases": ["DCA"],
        },
        "HashiCorp Certified: Terraform Associate": {
            "issuer": "HashiCorp",
            "aliases": ["Terraform Associate"],
        },
    },
    "data_analytics": {
        "SnowPro Core Certification": {
            "issuer": "Snowflake",
            "aliases": ["SnowPro Core"],
        },
        "Microsoft Certified: Azure Data Engineer Associate": {
            "issuer": "Microsoft",
            "aliases": ["DP-203", "Azure Data Engineer Associate"],
        },
        "Databricks Certified Data Engineer Associate": {
            "issuer": "Databricks",
            "aliases": [],
        },
        "Google Data Analytics Professional Certificate": {
            "issuer": "Google",
            "aliases": [],
        },
    },
    "networking": {
        "Cisco Certified Network Associate": {
            "issuer": "Cisco",
            "aliases": ["CCNA"],
        },
        "Cisco Certified Network Professional": {
            "issuer": "Cisco",
            "aliases": ["CCNP"],
        },
        "CompTIA Network+": {
            "issuer": "CompTIA",
            "aliases": ["Network+", "NetworkPlus"],
        },
    },
    "general_it": {
        "CompTIA A+": {
            "issuer": "CompTIA",
            "aliases": ["A+"],
        },
        "ITIL Foundation": {
            "issuer": "AXELOS",
            "aliases": ["ITIL Foundation Certificate in IT Service Management"],
        },
    },
}

# lowered canonical name/alias -> (category, canonical name, issuer), built once at
# import time so tools/agents can normalize a raw extracted string in O(1) without
# re-scanning COMMON_CERTIFICATIONS on every lookup.
_ALIAS_INDEX: dict[str, tuple[str, str, str]] = {
    variant.lower(): (category, canonical, info["issuer"])
    for category, certs in COMMON_CERTIFICATIONS.items()
    for canonical, info in certs.items()
    for variant in (canonical, *info["aliases"])
}

# canonical name -> issuer, built once at import time for lookups after normalization.
_ISSUER_INDEX: dict[str, str] = {
    canonical: info["issuer"]
    for certs in COMMON_CERTIFICATIONS.values()
    for canonical, info in certs.items()
}


def normalize_certification(raw: str) -> str | None:
    """Maps a raw certification title found in a resume/job posting to its canonical name.

    Lookup is case-insensitive against both canonical names and their known aliases.
    Returns None if `raw` isn't present in `COMMON_CERTIFICATIONS`, leaving the caller
    free to keep the raw value or discard it.
    """
    match = _ALIAS_INDEX.get(raw.strip().lower())
    return match[1] if match else None


def get_certification_issuer(canonical_title: str) -> str | None:
    """Returns the issuing organization for a canonical certification title.

    Returns None if `canonical_title` isn't a known canonical name in
    `COMMON_CERTIFICATIONS`.
    """
    return _ISSUER_INDEX.get(canonical_title)


@mcp.resource(
    "resource://common-certifications",
    name="common_certifications",
    title="Common IT Certifications",
    description=(
        "Canonical taxonomy of professional IT certifications (cloud, security, "
        "project management, DevOps, data/analytics, networking, general IT) with "
        "their issuing organization and common aliases. Agents extracting "
        "certifications from a resume or job posting use it to normalize what they "
        "find to one shared, unified vocabulary."
    ),
    mime_type="application/json",
)
def common_certifications() -> dict[str, dict[str, dict[str, str | list[str]]]]:
    """Returns the canonical IT certification taxonomy."""
    return COMMON_CERTIFICATIONS
