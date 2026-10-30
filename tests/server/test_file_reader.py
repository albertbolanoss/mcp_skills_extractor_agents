"""Tests for the read_document tool."""

import pytest
from labs_agent_lib.file_reader import UnsupportedFileTypeError

from candidate_skill_agent.server.tools.file_reader import read_document


def test_read_document_returns_text_content(tmp_path):
    # Arrange
    resume = tmp_path / "resume.txt"
    resume.write_text("Jane Doe - Senior Engineer")

    # Act
    result = read_document(str(resume))

    # Assert
    assert result == "Jane Doe - Senior Engineer"


def test_read_document_raises_for_missing_file(tmp_path):
    # Arrange
    missing = tmp_path / "missing.txt"

    # Act / Assert
    with pytest.raises(FileNotFoundError):
        read_document(str(missing))


def test_read_document_raises_for_unsupported_extension(tmp_path):
    # Arrange
    unsupported = tmp_path / "resume.xyz"
    unsupported.write_text("content")

    # Act / Assert
    with pytest.raises(UnsupportedFileTypeError):
        read_document(str(unsupported))
