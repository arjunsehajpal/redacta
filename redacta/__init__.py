from redacta.core.pipeline import Pipeline, build_default_pipeline
from redacta.decorators import pii_protect_openai_responses
from redacta.types import EntitySpan, SanitizedResult

__version__ = "1.0.0"

__all__ = [
    "pii_protect_openai_responses",
    "build_default_pipeline",
    "Pipeline",
    "EntitySpan",
    "SanitizedResult",
]
