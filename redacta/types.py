from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class EntitySpan:
    """Represents a detected PII entity in text.

    Attributes:
        label: The type of entity (e.g., 'PERSON', 'EMAIL', 'PHONE')
        start: Starting character index in the original text
        end: Ending character index in the original text
        text: The actual text of the entity
    """

    label: str
    start: int
    end: int
    text: str


@dataclass
class SanitizedResult:
    """Result of sanitizing text with PII detection and replacement.

    Attributes:
        sanitized_text: Text with PII replaced by placeholders
        mapping: Dictionary mapping placeholders to encrypted original values
        original_text: The original unsanitized text (for reference)
        session_id: Unique identifier for this sanitization session
    """

    sanitized_text: str
    mapping: dict[str, bytes]
    original_text: str = ""
    session_id: str = field(default_factory=lambda: uuid4().hex)
    entities: list[EntitySpan] = field(default_factory=list)


@dataclass
class SanitizedChatResult:
    """Aggregated result for multi-message chat sanitization."""

    sanitized_messages: list[Any]
    mapping: dict[str, bytes]
    session_id: str
    entities: list[EntitySpan] = field(default_factory=list)
    original_messages: list[Any] | None = None
