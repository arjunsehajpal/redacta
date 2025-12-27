from __future__ import annotations

import copy
import re
from typing import Any, Iterable, Iterator, Optional
from uuid import uuid4

from redacta.core.placeholders import get_placeholder_pattern, restore_from_placeholders
from redacta.types import SanitizedChatResult


def extract_anthropic_messages_from_kwargs(kwargs: dict[str, Any]) -> list[Any] | None:
    """Extract messages for Anthropic API calls."""
    messages = kwargs.get("messages")
    if isinstance(messages, list):
        return messages
    return None


def set_anthropic_messages_in_kwargs(kwargs: dict[str, Any], sanitized_messages: list[Any]) -> None:
    """Replace messages in kwargs for Anthropic calls."""
    if "messages" in kwargs:
        kwargs["messages"] = sanitized_messages


def sanitize_anthropic_messages(messages: list[Any], pipeline) -> tuple[list[Any], SanitizedChatResult]:
    """Sanitize Anthropic message content (string or text blocks) with shared placeholders."""
    messages_copy = copy.deepcopy(messages)
    label_counters: dict[str, int] = {}
    session_id = uuid4().hex
    combined_mapping: dict[str, bytes] = {}
    combined_entities = []
    sanitized_messages: list[Any] = []

    def _sanitize_text(text: str):
        sanitized = pipeline.sanitize_prompt(text, session_id=session_id, label_counters=label_counters)
        combined_mapping.update(sanitized.mapping)
        combined_entities.extend(sanitized.entities)
        return sanitized.sanitized_text

    for message in messages_copy:
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                message["content"] = _sanitize_text(content)
            elif isinstance(content, list):
                new_blocks = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                        block_copy = copy.deepcopy(block)
                        block_copy["text"] = _sanitize_text(block_copy["text"])
                        new_blocks.append(block_copy)
                    else:
                        new_blocks.append(block)
                message["content"] = new_blocks
        elif isinstance(message, str):
            message = _sanitize_text(message)

        sanitized_messages.append(message)

    chat_result = SanitizedChatResult(
        sanitized_messages=sanitized_messages,
        mapping=combined_mapping,
        session_id=session_id,
        entities=combined_entities,
        original_messages=messages,
    )

    return sanitized_messages, chat_result


def get_anthropic_output_text(response: Any) -> Optional[str]:
    """Extract text from an Anthropic response (non-streaming)."""
    if response is None:
        return None

    if isinstance(response, dict):
        content = response.get("content")
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                    texts.append(block["text"])
            if texts:
                return "".join(texts)
        if isinstance(content, str):
            return content

    if hasattr(response, "content"):
        content = getattr(response, "content")
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                    texts.append(block["text"])
            if texts:
                return "".join(texts)
        elif isinstance(content, str):
            return content

    return None


def set_anthropic_output_text(response: Any, new_text: str) -> Any:
    """Set text back on an Anthropic response (non-streaming)."""
    if response is None:
        return response

    def _set_on_content_list(content: list[Any]) -> list[Any]:
        updated_blocks = []
        text_set = False
        for block in content:
            if not text_set and isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                block = copy.deepcopy(block)
                block["text"] = new_text
                text_set = True
            updated_blocks.append(block)
        if not text_set:
            updated_blocks.append({"type": "text", "text": new_text})
        return updated_blocks

    if isinstance(response, dict):
        content = response.get("content")
        if isinstance(content, list):
            response["content"] = _set_on_content_list(content)
        else:
            response["content"] = [{"type": "text", "text": new_text}]
        return response

    if hasattr(response, "content"):
        content = getattr(response, "content")
        if isinstance(content, list):
            try:
                response.content = _set_on_content_list(content)
            except Exception:
                pass
        else:
            try:
                response.content = [{"type": "text", "text": new_text}]
            except Exception:
                pass
    return response


def _extract_anthropic_chunk_text(chunk: Any) -> str | None:
    """Extract streaming text from Anthropics chunks."""
    if chunk is None:
        return None

    if isinstance(chunk, dict):
        delta = chunk.get("delta")
        if isinstance(delta, dict):
            text = delta.get("text")
            if isinstance(text, str):
                return text
        if "text" in chunk and isinstance(chunk["text"], str):
            return chunk["text"]
    if hasattr(chunk, "delta") and hasattr(chunk.delta, "text"):
        text = getattr(chunk.delta, "text")
        return text if isinstance(text, str) else None
    if hasattr(chunk, "text"):
        text = getattr(chunk, "text")
        return text if isinstance(text, str) else None
    return None


def _set_anthropic_chunk_text(chunk: Any, new_text: str) -> Any:
    """Set streaming text back onto an Anthropics chunk."""
    if isinstance(chunk, dict):
        if "delta" in chunk and isinstance(chunk["delta"], dict):
            chunk = copy.deepcopy(chunk)
            chunk["delta"]["text"] = new_text
            return chunk
        if "text" in chunk:
            chunk = copy.deepcopy(chunk)
            chunk["text"] = new_text
            return chunk
    if hasattr(chunk, "delta") and hasattr(chunk.delta, "text"):
        try:
            chunk.delta.text = new_text
            return chunk
        except Exception:
            return chunk
    if hasattr(chunk, "text"):
        try:
            chunk.text = new_text
            return chunk
        except Exception:
            return chunk
    return chunk


def restore_anthropic_streaming_response(
    chunks: Iterable[Any],
    pipeline,
    chat_result: SanitizedChatResult,
) -> Iterator[Any]:
    """Restore placeholders in Anthropics streaming responses."""
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
        text = _extract_anthropic_chunk_text(chunk)
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
        yield _set_anthropic_chunk_text(chunk, restored_emit_text)

    if buffer:
        restored_tail = restore_from_placeholders(buffer, decrypted_mapping)
        yield _set_anthropic_chunk_text({"delta": {"text": ""}}, restored_tail)
