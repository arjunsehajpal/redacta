from __future__ import annotations

import copy
import re
from typing import Any, Iterable, Iterator
from uuid import uuid4

from redacta.core.placeholders import get_placeholder_pattern, restore_from_placeholders
from redacta.types import SanitizedChatResult


def extract_messages_from_kwargs(kwargs: dict[str, Any]) -> list[Any] | None:
    """Extract the messages array from kwargs if present and valid."""
    messages = kwargs.get("messages")
    if isinstance(messages, list):
        return messages
    return None


def set_messages_in_kwargs(kwargs: dict[str, Any], sanitized_messages: list[Any]) -> None:
    """Replace messages in kwargs in-place."""
    if "messages" in kwargs:
        kwargs["messages"] = sanitized_messages


def sanitize_messages(messages: list[Any], pipeline) -> tuple[list[Any], SanitizedChatResult]:
    """Sanitize string content values across all messages with shared placeholders."""
    messages_copy = copy.deepcopy(messages)
    label_counters: dict[str, int] = {}
    session_id = uuid4().hex
    combined_mapping: dict[str, bytes] = {}
    combined_entities = []
    sanitized_messages: list[Any] = []

    for message in messages_copy:
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                sanitized = pipeline.sanitize_prompt(content, session_id=session_id, label_counters=label_counters)
                message["content"] = sanitized.sanitized_text
                combined_mapping.update(sanitized.mapping)
                combined_entities.extend(sanitized.entities)
        elif isinstance(message, str):
            sanitized = pipeline.sanitize_prompt(message, session_id=session_id, label_counters=label_counters)
            message = sanitized.sanitized_text
            combined_mapping.update(sanitized.mapping)
            combined_entities.extend(sanitized.entities)

        sanitized_messages.append(message)

    chat_result = SanitizedChatResult(
        sanitized_messages=sanitized_messages,
        mapping=combined_mapping,
        session_id=session_id,
        entities=combined_entities,
        original_messages=messages,
    )

    return sanitized_messages, chat_result


def _extract_chunk_text(chunk: Any) -> str | None:
    """Pull text content from a streaming chunk for restoration."""
    if chunk is None:
        return None

    if hasattr(chunk, "choices") and chunk.choices:
        first_choice = chunk.choices[0]
        if hasattr(first_choice, "delta") and hasattr(first_choice.delta, "content"):
            return first_choice.delta.content
        if hasattr(first_choice, "message") and hasattr(first_choice.message, "content"):
            return first_choice.message.content
        if hasattr(first_choice, "text"):
            return first_choice.text

    if isinstance(chunk, dict):
        try:
            choices = chunk.get("choices") or []
            if choices:
                choice = choices[0]
                delta = choice.get("delta") or choice.get("message") or {}
                content = delta.get("content") if isinstance(delta, dict) else None
                if content is None and "text" in choice:
                    content = choice.get("text")
                return content if isinstance(content, str) else None
        except Exception:
            return None

    if hasattr(chunk, "content"):
        content = getattr(chunk, "content")
        return content if isinstance(content, str) else None

    if isinstance(chunk, str):
        return chunk

    return None


def _set_chunk_text(chunk: Any, new_text: str) -> Any:
    """Write restored text back to a streaming chunk."""
    if hasattr(chunk, "choices") and chunk.choices:
        first_choice = chunk.choices[0]
        if hasattr(first_choice, "delta") and hasattr(first_choice.delta, "content"):
            try:
                first_choice.delta.content = new_text
                return chunk
            except Exception:
                pass
        if hasattr(first_choice, "message") and hasattr(first_choice.message, "content"):
            try:
                first_choice.message.content = new_text
                return chunk
            except Exception:
                pass
        if hasattr(first_choice, "text"):
            try:
                first_choice.text = new_text
                return chunk
            except Exception:
                pass

    if isinstance(chunk, dict):
        try:
            if "choices" in chunk and chunk["choices"]:
                choice = chunk["choices"][0]
                if "delta" in choice and isinstance(choice["delta"], dict):
                    choice["delta"]["content"] = new_text
                elif "message" in choice and isinstance(choice["message"], dict):
                    choice["message"]["content"] = new_text
                elif "text" in choice:
                    choice["text"] = new_text
            elif "content" in chunk:
                chunk["content"] = new_text
        except Exception:
            return chunk
        return chunk

    if hasattr(chunk, "content"):
        try:
            chunk.content = new_text
            return chunk
        except Exception:
            return chunk

    if isinstance(chunk, str):
        return new_text

    return chunk


def restore_streaming_response(
    chunks: Iterable[Any],
    pipeline,
    chat_result: SanitizedChatResult,
) -> Iterator[Any]:
    """Restore placeholders in a streaming response safely across chunk boundaries."""
    placeholder_pattern = get_placeholder_pattern()
    partial_pattern = re.compile(r"@@[A-Z_0-9]*$")

    decrypted_mapping: dict[str, str] = {}
    for placeholder, encrypted_value in chat_result.mapping.items():
        try:
            decrypted_value = pipeline.kms.decrypt(encrypted_value)
            decrypted_mapping[placeholder] = decrypted_value.decode("utf-8")
        except Exception:
            decrypted_mapping[placeholder] = placeholder

    buffer = ""

    for chunk in chunks:
        text = _extract_chunk_text(chunk)
        if not isinstance(text, str) or text == "":
            yield chunk
            continue

        buffer += text

        safe_cut = len(buffer)
        partial_match = partial_pattern.search(buffer)
        if partial_match and not placeholder_pattern.fullmatch(partial_match.group()):
            safe_cut = partial_match.start()

        emit_text = buffer[:safe_cut]
        buffer = buffer[safe_cut:]

        restored_emit_text = restore_from_placeholders(emit_text, decrypted_mapping)
        yield _set_chunk_text(chunk, restored_emit_text)

    if buffer:
        restored_tail = restore_from_placeholders(buffer, decrypted_mapping)
        tail_chunk = {"choices": [{"delta": {"content": restored_tail}}]}
        yield tail_chunk
