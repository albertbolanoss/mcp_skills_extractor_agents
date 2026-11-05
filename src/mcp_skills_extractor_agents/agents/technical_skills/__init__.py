"""Evidence-grounded technical-skills extraction pipeline (Generator-Evaluator).

See `orchestrator.py` for the pipeline itself: a Generator agent extracts candidate
skills with verbatim evidence, a deterministic coordinator fans batches of them out to
an Evaluator agent that audits each item against the source document, and a
deterministic synthesizer filters/normalizes the verified result.
"""

from .orchestrator import run_technical_skills_pipeline

__all__ = ["run_technical_skills_pipeline"]
