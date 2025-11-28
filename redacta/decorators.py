import json
import logging
from functools import wraps
from typing import Any, Callable, Optional

from redacta.adapters.openai_responses import extract_input_from_kwargs, get_output_text, set_input_in_kwargs, set_output_text
from redacta.config import get_settings
from redacta.core.pipeline import Pipeline, build_default_pipeline

logger = logging.getLogger("redacta.pii")


_MISSING = object()


def _log_verbose(stage: str, session_id: str, *, text=_MISSING, entities=_MISSING) -> None:
    payload: dict[str, Any] = {"stage": stage, "session_id": session_id}
    if text is not _MISSING:
        payload["text"] = text
    if entities is not _MISSING:
        payload["entities"] = [
            {"label": entity.label, "start": entity.start, "end": entity.end, "text": entity.text}
            for entity in entities
        ]
    logger.info(json.dumps(payload))


def pii_protect_openai_responses(
    pipeline: Optional[Pipeline] = None,
    *,
    verbose: Optional[bool] = None,
) -> Callable[[Callable], Callable]:
    """Decorator to add PII protection to OpenAI Responses API calls.

    This decorator intercepts calls to OpenAI's responses API, sanitizes
    the input by replacing PII with placeholders, sends the sanitized input
    to the API, and then restores the original PII in the response.

    Args:
        pipeline: Optional Pipeline instance. If None, a default pipeline
            will be created.
        verbose: Override verbose logging behavior. If omitted, falls back
            to the pipeline's verbose flag (default False).

    Returns:
        Decorator function

    Example:
        ```python
        from openai import OpenAI
        from redacta import pii_protect_openai_responses, build_default_pipeline

        pipeline = build_default_pipeline()
        client = OpenAI()

        @pii_protect_openai_responses(pipeline=pipeline)
        def ask(client, **kwargs):
            return client.responses.create(**kwargs)

        response = ask(
            client,
            model="gpt-4",
            input="Email John Doe at john@example.com"
        )
        ```
    """
    settings = get_settings()

    if pipeline is None:
        pipeline = build_default_pipeline(verbose=verbose if verbose is not None else False)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not settings.enable_pii_protection:
                return func(*args, **kwargs)

            input_text = extract_input_from_kwargs(kwargs)

            if input_text is None:
                return func(*args, **kwargs)

            sanitized_result = pipeline.sanitize_prompt(input_text)

            set_input_in_kwargs(kwargs, sanitized_result.sanitized_text)

            effective_verbose = verbose if verbose is not None else getattr(pipeline, "verbose", False)
            if effective_verbose:
                _log_verbose(
                    "sanitize_prompt",
                    sanitized_result.session_id,
                    text=sanitized_result.sanitized_text,
                )
                _log_verbose(
                    "detected_entities",
                    sanitized_result.session_id,
                    entities=sanitized_result.entities,
                )

            response = func(*args, **kwargs)

            output_text = get_output_text(response)

            if effective_verbose:
                _log_verbose(
                    "llm_response_placeholders",
                    sanitized_result.session_id,
                    text=output_text,
                )

            if output_text is not None:
                restored_text = pipeline.restore_response(output_text, sanitized_result)
                set_output_text(response, restored_text)

            return response

        return wrapper

    return decorator
