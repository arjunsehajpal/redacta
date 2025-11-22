from ..config import get_settings
from ..kms import LocalKMS
from ..types import SanitizedResult
from .mapping_store import MappingStore
from .pii_spacy import SpaCyPIIDetector
from .placeholders import replace_with_placeholders, restore_from_placeholders


class Pipeline:
    """Orchestrates PII detection, sanitization, and restoration.

    The pipeline coordinates between the PII detector, placeholder system,
    encryption, and mapping storage to provide a complete redaction/restoration
    workflow.
    """

    def __init__(self, detector: SpaCyPIIDetector, kms: LocalKMS, mapping_store: MappingStore):
        """Initialize the pipeline.

        Args:
            detector: PII detection engine
            kms: Key management system for encryption
            mapping_store: Store for placeholder mappings
        """
        self.detector = detector
        self.kms = kms
        self.mapping_store = mapping_store

    def sanitize_prompt(self, prompt: str) -> SanitizedResult:
        """Sanitize a prompt by detecting and replacing PII.

        Args:
            prompt: The original prompt text

        Returns:
            SanitizedResult with sanitized text and encrypted mappings
        """
        from uuid import uuid4

        entities = self.detector.detect(prompt)

        sanitized_text, plaintext_mapping = replace_with_placeholders(prompt, entities)

        session_id = uuid4().hex
        encrypted_mapping: dict[str, bytes] = {}
        for placeholder, original_value in plaintext_mapping.items():
            encrypted_value = self.kms.encrypt(original_value.encode("utf-8"))
            encrypted_mapping[placeholder] = encrypted_value
            session_key = f"{session_id}:{placeholder}"
            self.mapping_store.set(session_key, encrypted_value)

        return SanitizedResult(
            sanitized_text=sanitized_text, mapping=encrypted_mapping, original_text=prompt, session_id=session_id
        )

    def restore_response(self, text: str, sanitized_result: SanitizedResult, clear_mappings: bool = False) -> str:
        """Restore original PII in a response text.

        Args:
            text: Text containing placeholders
            sanitized_result: The SanitizedResult from sanitize_prompt
            clear_mappings: If True, remove the mappings from the store after restoration

        Returns:
            Text with placeholders replaced by original PII
        """
        decrypted_mapping: dict[str, str] = {}

        for placeholder, encrypted_value in sanitized_result.mapping.items():
            try:
                decrypted_value = self.kms.decrypt(encrypted_value)
                decrypted_mapping[placeholder] = decrypted_value.decode("utf-8")
            except Exception as e:
                decrypted_mapping[placeholder] = placeholder

        restored_text = restore_from_placeholders(text, decrypted_mapping)

        if clear_mappings:
            self.clear_session_mappings(sanitized_result)

        return restored_text

    def clear_session_mappings(self, sanitized_result: SanitizedResult) -> None:
        """Clear mappings for a specific sanitized result from the store.

        This is useful for cleaning up after restoration to prevent
        stale data accumulation in long-running applications.

        Uses the session_id to ensure only this session's mappings are cleared,
        preventing cross-session interference.

        Args:
            sanitized_result: The SanitizedResult whose mappings should be cleared
        """
        session_id = sanitized_result.session_id
        for placeholder in sanitized_result.mapping.keys():
            session_key = f"{session_id}:{placeholder}"
            self.mapping_store.remove(session_key)


def build_default_pipeline() -> Pipeline:
    """Build a pipeline with default configuration.

    This factory function creates a Pipeline using settings from
    the environment and default components.

    Returns:
        Configured Pipeline instance
    """
    settings = get_settings()

    detector = SpaCyPIIDetector(model_name=settings.spacy_model)
    kms = LocalKMS(key_path=settings.key_path)
    mapping_store = MappingStore()

    return Pipeline(detector=detector, kms=kms, mapping_store=mapping_store)
