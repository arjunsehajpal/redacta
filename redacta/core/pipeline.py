from redacta.config import get_settings
from redacta.core.mapping_store import MappingStore
from redacta.core.pii_spacy import SpaCyPIIDetector
from redacta.core.placeholders import replace_with_placeholders, restore_from_placeholders
from redacta.kms import LocalKMS
from redacta.types import SanitizedChatResult, SanitizedResult


class Pipeline:
    """Orchestrates PII detection, sanitization, and restoration.

    The pipeline coordinates between the PII detector, placeholder system,
    encryption, and mapping storage to provide a complete redaction/restoration
    workflow.
    """

    def __init__(
        self,
        detector: SpaCyPIIDetector,
        kms: LocalKMS,
        mapping_store: MappingStore,
        verbose: bool = False,
    ):
        """Initialize the pipeline.

        Args:
            detector: PII detection engine
            kms: Key management system for encryption
            mapping_store: Store for placeholder mappings
            verbose: Enable verbose logging for decorator integrations
        """
        self.detector = detector
        self.kms = kms
        self.mapping_store = mapping_store
        self.verbose = verbose

    def sanitize_prompt(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        label_counters: dict[str, int] | None = None,
    ) -> SanitizedResult:
        """Sanitize a prompt by detecting and replacing PII.

        Args:
            prompt: The original prompt text
            session_id: Optional session id to reuse across multiple sanitizations
            label_counters: Optional shared label counters to keep placeholder numbering continuous

        Returns:
            SanitizedResult with sanitized text and encrypted mappings
        """
        entities = self.detector.detect(prompt)

        sanitized_text, plaintext_mapping = replace_with_placeholders(prompt, entities, label_counters)

        from uuid import uuid4

        session_id = session_id or uuid4().hex
        encrypted_mapping: dict[str, bytes] = {}
        for placeholder, original_value in plaintext_mapping.items():
            encrypted_value = self.kms.encrypt(original_value.encode("utf-8"))
            encrypted_mapping[placeholder] = encrypted_value
            session_key = f"{session_id}:{placeholder}"
            self.mapping_store.set(session_key, encrypted_value)

        return SanitizedResult(
            sanitized_text=sanitized_text,
            mapping=encrypted_mapping,
            original_text=prompt,
            session_id=session_id,
            entities=entities,
        )

    def sanitize_messages(self, messages: list[str]) -> SanitizedChatResult:
        """Sanitize a list of message contents with shared placeholders."""
        from uuid import uuid4

        label_counters: dict[str, int] = {}
        session_id = uuid4().hex
        sanitized_messages: list[str] = []
        combined_mapping: dict[str, bytes] = {}
        combined_entities = []

        for message in messages:
            sanitized = self.sanitize_prompt(message, session_id=session_id, label_counters=label_counters)
            sanitized_messages.append(sanitized.sanitized_text)
            combined_mapping.update(sanitized.mapping)
            combined_entities.extend(sanitized.entities)

        return SanitizedChatResult(
            sanitized_messages=sanitized_messages,
            mapping=combined_mapping,
            session_id=session_id,
            entities=combined_entities,
            original_messages=messages,
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


def build_default_pipeline(verbose: bool = False) -> Pipeline:
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

    return Pipeline(detector=detector, kms=kms, mapping_store=mapping_store, verbose=verbose)
