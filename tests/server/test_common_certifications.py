"""Tests for the common-certifications MCP resource."""

from candidate_skill_agent.server.resources.common_certifications import (
    COMMON_CERTIFICATIONS,
    common_certifications,
    get_certification_issuer,
    normalize_certification,
)


def test_common_certifications_has_multiple_categories_and_certifications():
    # Act
    taxonomy = common_certifications()

    # Assert
    assert taxonomy is COMMON_CERTIFICATIONS
    assert len(taxonomy) > 3
    assert all(len(certs) > 0 for certs in taxonomy.values())


def test_normalize_certification_resolves_known_alias():
    # Act / Assert
    assert normalize_certification("AWS SAA") == "AWS Certified Solutions Architect - Associate"
    assert (
        normalize_certification("CISSP")
        == "Certified Information Systems Security Professional"
    )
    assert normalize_certification("  PMP ") == "Project Management Professional"


def test_normalize_certification_is_case_insensitive_on_canonical_name():
    # Act / Assert
    assert normalize_certification("comptia security+") == "CompTIA Security+"
    assert normalize_certification("COMPTIA SECURITY+") == "CompTIA Security+"


def test_normalize_certification_returns_none_for_unknown_certification():
    # Act / Assert
    assert normalize_certification("some-made-up-certification") is None


def test_get_certification_issuer_resolves_known_canonical_title():
    # Act / Assert
    assert get_certification_issuer("Project Management Professional") == (
        "Project Management Institute"
    )
    assert get_certification_issuer("Certified Kubernetes Administrator") == (
        "Cloud Native Computing Foundation"
    )


def test_get_certification_issuer_returns_none_for_unknown_title():
    # Act / Assert
    assert get_certification_issuer("some-made-up-certification") is None
