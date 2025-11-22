import pytest

from redacta.config.settings import Settings
from redacta.core.mapping_store import MappingStore
from redacta.core.pii_spacy import SpaCyPIIDetector
from redacta.core.pipeline import Pipeline, build_default_pipeline
from redacta.kms.local import LocalKMS


@pytest.fixture
def temp_key_path(tmp_path):
    """Provide a temporary key path for testing."""
    return tmp_path / "test.key"


@pytest.fixture
def pipeline(temp_key_path):
    """Create a test pipeline instance."""
    detector = SpaCyPIIDetector()
    kms = LocalKMS(temp_key_path)
    mapping_store = MappingStore()
    return Pipeline(detector, kms, mapping_store)


def test_sanitize_simple_pii(pipeline):
    """Test sanitization of simple PII."""
    prompt = "Contact John Doe at john@example.com or call 555-123-4567."
    
    result = pipeline.sanitize_prompt(prompt)
    
    assert result.sanitized_text != prompt
    assert "john@example.com" not in result.sanitized_text
    assert "@@EMAIL" in result.sanitized_text
    assert len(result.mapping) > 0


def test_restore_response(pipeline):
    """Test restoration of PII in responses."""
    prompt = "Email john@example.com about the meeting."
    
    sanitized = pipeline.sanitize_prompt(prompt)
    
    llm_response = f"I will send an email to {sanitized.sanitized_text.split()[1]}."
    
    restored = pipeline.restore_response(llm_response, sanitized)
    
    assert "@@EMAIL" not in restored
    assert "john@example.com" in restored


def test_no_pii_passthrough(pipeline):
    """Test that text without PII passes through unchanged."""
    prompt = "What is the weather like today?"
    
    result = pipeline.sanitize_prompt(prompt)
    
    assert result.sanitized_text == prompt
    assert len(result.mapping) == 0


def test_multiple_entities_same_type(pipeline):
    """Test handling of multiple entities of the same type."""
    prompt = "Contact alice@example.com and bob@example.com"
    
    result = pipeline.sanitize_prompt(prompt)
    
    assert "@@EMAIL_1@@" in result.sanitized_text
    assert "@@EMAIL_2@@" in result.sanitized_text
    assert "alice@example.com" not in result.sanitized_text
    assert "bob@example.com" not in result.sanitized_text


def test_build_default_pipeline(temp_key_path, monkeypatch):
    """Test building a pipeline with default configuration."""
    monkeypatch.setenv("REDACTA_LOCAL_KEY_PATH", str(temp_key_path))
    
    Settings.model_rebuild()
    
    pipeline = build_default_pipeline()
    
    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.detector, SpaCyPIIDetector)
    assert isinstance(pipeline.kms, LocalKMS)
    assert isinstance(pipeline.mapping_store, MappingStore)


def test_encryption_decryption(pipeline):
    """Test that PII is properly encrypted and decrypted."""
    prompt = "My email is secret@example.com"
    
    sanitized = pipeline.sanitize_prompt(prompt)
    
    for placeholder, encrypted_value in sanitized.mapping.items():
        assert isinstance(encrypted_value, bytes)
        decrypted = pipeline.kms.decrypt(encrypted_value)
        assert isinstance(decrypted, bytes)
        assert decrypted.decode('utf-8') in ["secret@example.com"]


def test_person_detection(pipeline):
    """Test detection of PERSON entities."""
    prompt = "John Smith will attend the meeting."
    
    result = pipeline.sanitize_prompt(prompt)
    
    assert "@@PERSON" in result.sanitized_text
    assert "John Smith" not in result.sanitized_text or len(result.mapping) > 0


def test_us_phone_detection(pipeline):
    """Ensure US-format phone numbers are detected and sanitized."""
    prompt = "Call me at 555-123-4567 for details."
    
    result = pipeline.sanitize_prompt(prompt)
    
    assert "@@PHONE_1@@" in result.sanitized_text
    assert "555-123-4567" not in result.sanitized_text


def test_indian_mobile_detection(pipeline):
    """Ensure Indian mobile numbers are detected via the regex pattern."""
    prompt = "+919876543210"
    
    result = pipeline.sanitize_prompt(prompt)
    
    assert result.sanitized_text == "@@PHONE_1@@"
    restored = pipeline.restore_response(result.sanitized_text, result)
    assert restored == prompt


def test_sequential_calls_no_interference(pipeline):
    """Test that sequential sanitize/restore calls don't interfere with each other."""
    prompt1 = "Contact alice@example.com"
    prompt2 = "Email bob@company.com"
    
    result1 = pipeline.sanitize_prompt(prompt1)
    result2 = pipeline.sanitize_prompt(prompt2)
    
    assert "@@EMAIL_1@@" in result1.sanitized_text
    assert "@@EMAIL_1@@" in result2.sanitized_text
    
    response1 = pipeline.restore_response("Send to @@EMAIL_1@@", result1)
    response2 = pipeline.restore_response("Contact @@EMAIL_1@@", result2)
    
    assert "alice@example.com" in response1
    assert "bob@company.com" in response2
    assert "alice@example.com" not in response2
    assert "bob@company.com" not in response1


def test_mapping_store_cleanup(pipeline):
    """Test that mappings can be cleaned up after restoration."""
    prompt = "Email test@example.com"
    
    initial_store_size = len(pipeline.mapping_store)
    
    result = pipeline.sanitize_prompt(prompt)
    assert len(pipeline.mapping_store) == initial_store_size + 1
    
    pipeline.restore_response("Contact @@EMAIL_1@@", result, clear_mappings=True)
    assert len(pipeline.mapping_store) == initial_store_size


def test_clear_session_mappings(pipeline):
    """Test explicit clearing of session mappings."""
    prompt = "Contact alice@example.com and bob@example.com"
    
    result = pipeline.sanitize_prompt(prompt)
    assert len(pipeline.mapping_store) >= 2
    
    pipeline.clear_session_mappings(result)
    
    for placeholder in result.mapping.keys():
        assert pipeline.mapping_store.get(placeholder) is None


def test_stale_data_accumulation_prevention(pipeline):
    """Test that multiple sessions can be cleaned up to prevent stale data."""
    prompts = [
        "Email user1@example.com and admin1@example.com",
        "Contact user2@example.com and admin2@example.com",
        "Send to user3@example.com and admin3@example.com",
    ]
    
    results = []
    for prompt in prompts:
        result = pipeline.sanitize_prompt(prompt)
        results.append(result)
    
    store_size_before_cleanup = len(pipeline.mapping_store)
    assert store_size_before_cleanup > 0
    
    for result in results:
        pipeline.clear_session_mappings(result)
    
    assert len(pipeline.mapping_store) == 0


def test_overlapping_sessions_no_interference(pipeline):
    """Test that cleanup of one session doesn't affect other sessions.
    
    This regression test ensures session-scoped cleanup prevents
    cross-session interference even when placeholders have the same names.
    """
    pipeline.mapping_store.clear()
    
    result1 = pipeline.sanitize_prompt("Send to alice@example.com")
    result2 = pipeline.sanitize_prompt("Contact bob@example.com")
    result3 = pipeline.sanitize_prompt("Reply to carol@example.com")
    
    initial_store_size = len(pipeline.mapping_store)
    assert initial_store_size >= 3
    
    pipeline.clear_session_mappings(result1)
    after_first_cleanup = len(pipeline.mapping_store)
    assert after_first_cleanup < initial_store_size
    
    response2 = pipeline.restore_response("Contact @@EMAIL_1@@", result2)
    assert "bob@example.com" in response2
    
    response3 = pipeline.restore_response("Send to @@EMAIL_1@@", result3)
    assert "carol@example.com" in response3
    
    pipeline.clear_session_mappings(result2)
    after_second_cleanup = len(pipeline.mapping_store)
    assert after_second_cleanup < after_first_cleanup
    
    response3_again = pipeline.restore_response("Reply to @@EMAIL_1@@", result3)
    assert "carol@example.com" in response3_again
    
    pipeline.clear_session_mappings(result3)
    assert len(pipeline.mapping_store) == 0
