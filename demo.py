from redacta.core.pipeline import build_default_pipeline


def demo_basic_usage():
    """Demonstrate basic PII detection and restoration."""
    print("=" * 60)
    print("Redacta Demo - PII Redaction & Restoration")
    print("=" * 60)

    pipeline = build_default_pipeline()

    test_prompts = [
        "Contact John Doe at john@example.com or call 555-123-4567.",
        "Send the report to alice@company.com and bob@company.com",
        "Dr. Jane Smith will present at the conference.",
        "What is the weather like today?",
        "Please email Sarah Johnson at sarah.j@example.org about the meeting.",
    ]

    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n{'─' * 60}")
        print(f"Test {i}")
        print(f"{'─' * 60}")
        print(f"Original:  {prompt}")

        result = pipeline.sanitize_prompt(prompt)
        print(f"Sanitized: {result.sanitized_text}")

        if result.mapping:
            print(f"Detected:  {len(result.mapping)} PII entities")

            llm_response = f"I received your message: '{result.sanitized_text}'"
            restored = pipeline.restore_response(llm_response, result)
            print(f"Restored:  {restored}")
        else:
            print("Detected:  No PII found")

    print(f"\n{'=' * 60}")
    print("Demo Complete!")
    print("=" * 60)


def demo_encryption():
    """Demonstrate encryption of PII data."""
    print("\n" + "=" * 60)
    print("Encryption Demo")
    print("=" * 60)

    pipeline = build_default_pipeline()

    prompt = "My secret email is confidential@example.com"
    result = pipeline.sanitize_prompt(prompt)

    print(f"\nOriginal: {prompt}")
    print(f"Sanitized: {result.sanitized_text}")

    if result.mapping:
        for placeholder, encrypted_value in result.mapping.items():
            print(f"\nPlaceholder: {placeholder}")
            print(f"Encrypted (first 40 bytes): {encrypted_value[:40].hex()}...")

            decrypted = pipeline.kms.decrypt(encrypted_value)
            print(f"Decrypted: {decrypted.decode('utf-8')}")


def demo_openai_style():
    """Demonstrate OpenAI-style integration pattern."""
    print("\n" + "=" * 60)
    print("OpenAI Integration Pattern Demo")
    print("=" * 60)

    from unittest.mock import MagicMock
    from redacta import pii_protect_openai_responses

    class MockResponse:
        def __init__(self, output_text):
            self.output_text = output_text

    mock_client = MagicMock()

    @pii_protect_openai_responses()
    def mock_api_call(client, **kwargs):
        input_text = kwargs.get("input", "")
        return MockResponse(f"Echo: {input_text}")

    test_input = "Please contact Alice Cooper at alice@example.com"

    print(f"\nInput to decorator: {test_input}")
    response = mock_api_call(mock_client, model="gpt-4", input=test_input)
    print(f"Output from decorator: {response.output_text}")
    print("\nNote: Email was protected during the 'API call' and restored in the output")


if __name__ == "__main__":
    try:
        demo_basic_usage()
        demo_encryption()
        demo_openai_style()

        print("\n✅ All demos completed successfully!")
        print("\nTo use Redacta with OpenAI:")
        print("  1. Install spaCy model: python -m spacy download en_core_web_sm")
        print("  2. Set your OpenAI API key: export OPENAI_API_KEY='your-key'")
        print("  3. Use the @pii_protect_openai_responses decorator")

    except Exception as e:
        print(f"\n❌ Error running demo: {e}")
        print("\nMake sure to install spaCy model:")
        print("  python -m spacy download en_core_web_sm")
        raise
