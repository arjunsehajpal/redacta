import re
from typing import Pattern

from ..types import EntitySpan


def replace_with_placeholders(text: str, entities: list[EntitySpan]) -> tuple[str, dict[str, str]]:
    """Replace PII entities with deterministic placeholders.

    Args:
        text: Original text containing PII
        entities: List of detected EntitySpan objects

    Returns:
        Tuple of (sanitized_text, placeholder_mapping)
        where placeholder_mapping maps placeholder -> original_text
    """
    if not entities:
        return text, {}

    entities_sorted = sorted(entities, key=lambda e: e.start, reverse=True)

    label_counters: dict[str, int] = {}
    mapping: dict[str, str] = {}
    result = text

    for entity in entities_sorted:
        label = entity.label
        if label not in label_counters:
            label_counters[label] = 0
        label_counters[label] += 1

        placeholder = f"@@{label}_{label_counters[label]}@@"
        mapping[placeholder] = entity.text

        result = result[: entity.start] + placeholder + result[entity.end :]

    return result, mapping


def restore_from_placeholders(text: str, mapping: dict[str, str]) -> str:
    """Restore original PII from placeholders in text.

    Args:
        text: Text containing placeholders
        mapping: Dictionary mapping placeholders to original values

    Returns:
        Text with placeholders replaced by original values
    """
    result = text

    placeholder_pattern = re.compile(r"@@[A-Z_0-9]+@@")

    for match in placeholder_pattern.finditer(text):
        placeholder = match.group()
        if placeholder in mapping:
            result = result.replace(placeholder, mapping[placeholder], 1)

    return result


def get_placeholder_pattern() -> Pattern[str]:
    """Get the regex pattern for matching placeholders.

    Returns:
        Compiled regex pattern
    """
    return re.compile(r"@@[A-Z_0-9]+@@")
