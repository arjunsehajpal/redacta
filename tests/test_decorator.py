from unittest.mock import MagicMock

import pytest

from redacta.core.mapping_store import MappingStore
from redacta.core.pii_spacy import SpaCyPIIDetector
from redacta.core.pipeline import Pipeline
from redacta.decorators import pii_protect_openai_responses
from redacta.kms.local import LocalKMS


class MockResponse:
    """Mock OpenAI response object."""
    
    def __init__(self, output_text: str):
        self.output_text = output_text


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


def test_decorator_sanitizes_input(pipeline):
    """Test that the decorator sanitizes input."""
    mock_client = MagicMock()
    
    @pii_protect_openai_responses(pipeline=pipeline)
    def mock_api_call(client, **kwargs):
        return MockResponse(f"Echo: {kwargs['input']}")
    
    response = mock_api_call(
        mock_client,
        model="gpt-4",
        input="Contact john@example.com"
    )
    
    assert "john@example.com" in response.output_text


def test_decorator_with_no_pii(pipeline):
    """Test decorator with input containing no PII."""
    mock_client = MagicMock()
    
    @pii_protect_openai_responses(pipeline=pipeline)
    def mock_api_call(client, **kwargs):
        return MockResponse(kwargs['input'])
    
    response = mock_api_call(
        mock_client,
        model="gpt-4",
        input="What is the capital of France?"
    )
    
    assert response.output_text == "What is the capital of France?"


def test_decorator_preserves_function_signature(pipeline):
    """Test that decorator preserves the original function signature."""
    @pii_protect_openai_responses(pipeline=pipeline)
    def my_function(client, **kwargs):
        """Original docstring."""
        return MockResponse("test")
    
    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ is not None and "Original docstring" in my_function.__doc__


def test_decorator_with_no_input():
    """Test decorator when no input is provided in kwargs."""
    @pii_protect_openai_responses()
    def mock_api_call(client, **kwargs):
        return MockResponse("response")
    
    response = mock_api_call(MagicMock(), model="gpt-4")
    
    assert response.output_text == "response"


def test_decorator_restores_pii_in_response(pipeline):
    """Test that PII is restored in the API response."""
    mock_client = MagicMock()
    
    @pii_protect_openai_responses(pipeline=pipeline)
    def mock_api_call(client, **kwargs):
        input_text = kwargs['input']
        if "@@EMAIL" in input_text:
            return MockResponse(f"I will contact {input_text.split()[1]}")
        return MockResponse(input_text)
    
    response = mock_api_call(
        mock_client,
        model="gpt-4",
        input="Email alice@example.com"
    )
    
    assert "alice@example.com" in response.output_text
    assert "@@EMAIL" not in response.output_text


def test_decorator_with_disabled_protection(pipeline, monkeypatch):
    """Test decorator when PII protection is disabled."""
    monkeypatch.setenv("REDACTA_ENABLE_PII_PROTECTION", "false")
    
    from redacta.config.settings import Settings
    Settings.model_rebuild()
    
    mock_client = MagicMock()
    
    @pii_protect_openai_responses(pipeline=pipeline)
    def mock_api_call(client, **kwargs):
        return MockResponse(kwargs['input'])
    
    response = mock_api_call(
        mock_client,
        model="gpt-4",
        input="Contact john@example.com"
    )
    
    assert response.output_text == "Contact john@example.com"
