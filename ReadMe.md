# Redacta ![Status](https://img.shields.io/badge/status-work--in--progress-orange)

**Privacy-first PII redaction & restoration middleware for LLM applications**

Redacta automatically detects and redacts personally identifiable information (PII) in prompts sent to LLMs, and seamlessly restores the original PII in the responses. This ensures that sensitive data never leaves your infrastructure in plaintext.

## Features

- **Automatic PII Detection** - Uses spaCy NER and regex patterns to detect PERSON names, EMAIL addresses, and PHONE numbers
- **Local Encryption** - Encrypts PII using AES-GCM before storage
- **Seamless Restoration** - Automatically restores original PII in LLM responses
- **Deterministic Placeholders** - Consistent placeholder generation (e.g., `@@EMAIL_1@@`)
- **Decorator Pattern** - Simple integration via Python decorators
- **Configurable** - Environment-based configuration with sensible defaults
- **Verbose Logging** - Optional JSON logs of sanitized prompts, detected entities, and placeholder responses

## Installation

```bash
pip install -e .
```

### Install spaCy Model

Redacta uses spaCy for entity recognition. Install the required language model:

```bash
# install pip
python -m ensurepip --upgrade    

# install spacy model
python3 -m spacy download en_core_web_sm
```

## Quick Start

```python
from openai import OpenAI
from redacta import pii_protect_openai_responses, build_default_pipeline

# Build the PII protection pipeline
pipeline = build_default_pipeline()

# Create OpenAI client
client = OpenAI()

# Wrap your API calls with the decorator
@pii_protect_openai_responses(pipeline=pipeline)
def ask(client, **kwargs):
    return client.responses.create(**kwargs)

# Use it normally - PII is automatically protected!
response = ask(
    client,
    model="gpt-4",
    input="Email a reminder to John Doe at john@example.com about his appointment."
)

print(response.output_text)
# Output contains the original email address, restored from the placeholder
```

## How It Works
1. **Detection**: Redacta scans your prompt and detects PII entities
2. **Redaction**: PII is replaced with deterministic placeholders (e.g., `@@EMAIL_1@@`)
3. **Encryption**: Original values are encrypted using AES-GCM and stored locally
4. **API Call**: Only the sanitized text is sent to the LLM
5. **Restoration**: Placeholders in the response are replaced with the original PII

### Example Flow
```
Original Input:  "Contact John Doe at john@example.com"
                          ↓
Sanitized Input: "Contact @@PERSON_1@@ at @@EMAIL_1@@"
                          ↓ (sent to LLM)
LLM Response:    "I'll contact @@EMAIL_1@@ right away"
                          ↓
Restored Output: "I'll contact john@example.com right away"
```

## Project Structure

```
redacta/
├── __init__.py              # Main package exports
├── types.py                 # Data types (EntitySpan, SanitizedResult)
├── decorators.py            # Decorator for OpenAI integration
├── config/
│   ├── settings.py          # Configuration management
├── core/
│   ├── pii_spacy.py         # spaCy-based PII detection
│   ├── placeholders.py      # Placeholder generation & replacement
│   ├── mapping_store.py     # In-memory mapping storage
│   └── pipeline.py          # Orchestration pipeline
├── kms/
│   └── local.py             # Local symmetric encryption (AES-GCM)
└── adapters/
    └── openai_responses.py  # OpenAI API integration helpers
```

## Configuration

Configure Redacta using environment variables:

```bash
# Enable/disable PII protection (default: true)
export REDACTA_ENABLE_PII_PROTECTION=true

# spaCy model to use (default: en_core_web_sm)
export REDACTA_SPACY_MODEL=en_core_web_sm

# Path to encryption key file (default: ./redacta.key)
export REDACTA_LOCAL_KEY_PATH=./redacta.key
```

## Advanced Usage

### Verbose Logging

Enable verbose JSON logging to inspect the sanitize/restore lifecycle during debugging. You can enable it when creating the pipeline or override it on a per-decorator basis.

```python
import logging
from redacta import build_default_pipeline, pii_protect_openai_responses

logging.basicConfig(level=logging.INFO)

pipeline = build_default_pipeline(verbose=True)

@pii_protect_openai_responses(pipeline=pipeline)
def ask(client, **kwargs):
    return client.responses.create(**kwargs)

# Override the shared pipeline if needed:
@pii_protect_openai_responses(pipeline=pipeline, verbose=False)
def quiet_call(client, **kwargs):
    return client.responses.create(**kwargs)
```

Logs are emitted to the `redacta.pii` logger at `INFO` level as single-line JSON entries that share a `session_id` for easy correlation:

```json
{"stage":"sanitize_prompt","text":"Email @@PERSON_1@@ at @@EMAIL_1@@","session_id":"a3f4..."}
{"stage":"detected_entities","session_id":"a3f4...","entities":[{"label":"PERSON","start":6,"end":14,"text":"John Doe"},{"label":"EMAIL","start":18,"end":33,"text":"john@example.com"}]}
{"stage":"llm_response_placeholders","session_id":"a3f4...","text":"I'll email @@EMAIL_1@@ today"}
```

### Manual Pipeline Usage

```python
from redacta.core.pipeline import build_default_pipeline

pipeline = build_default_pipeline()

# Sanitize a prompt
result = pipeline.sanitize_prompt("Email john@example.com")
print(result.sanitized_text)  # "Email @@EMAIL_1@@"

# Restore PII in a response
restored = pipeline.restore_response(
    "I sent it to @@EMAIL_1@@",
    result
)
print(restored)  # "I sent it to john@example.com"
```

### Custom Pipeline

```python
from redacta.core.pipeline import Pipeline
from redacta.core.pii_spacy import SpaCyPIIDetector
from redacta.core.mapping_store import MappingStore
from redacta.kms.local import LocalKMS

detector = SpaCyPIIDetector(model_name="en_core_web_lg")
kms = LocalKMS(key_path="./custom.key")
mapping_store = MappingStore()

pipeline = Pipeline(detector, kms, mapping_store)
```

### Session Management and Cleanup

Each `SanitizedResult` includes a unique `session_id` that isolates its mappings in the MappingStore. This prevents cross-session interference when multiple sanitization operations are in flight.

For long-running applications, you should clean up sessions after restoration to prevent memory accumulation:

```python
pipeline = build_default_pipeline()

result = pipeline.sanitize_prompt("Email john@example.com")

response_text = pipeline.restore_response(
    llm_output, 
    result, 
    clear_mappings=True  # Automatically clean up after restoration
)

pipeline.clear_session_mappings(result)
```

**Key Points:**
- Each sanitization creates a new session with a unique UUID
- Session IDs ensure mappings don't interfere across concurrent requests
- Use `clear_mappings=True` or call `clear_session_mappings()` for cleanup
- The `SanitizedResult.mapping` contains all data needed for restoration (MappingStore is optional)

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest tests/
```

### Install in Editable Mode

```bash
pip install -e .
```

## Security Considerations

- **Local Encryption**: PII is encrypted using AES-GCM with a 256-bit key
- **Key Management**: The encryption key is stored locally (default: `./redacta.key`)
- **In-Memory Storage**: Mappings are stored in memory during the request lifecycle
- **No External Dependencies**: PII never leaves your infrastructure unencrypted

**Important**: Protect your encryption key file and ensure it's not committed to version control!

## Supported PII Types

Currently supported entity types:

- **PERSON** - Personal names (via spaCy NER)
- **EMAIL** - Email addresses (via regex)
- **PHONE** - Phone numbers via regex (US formats and Indian mobile numbers)

## Future Enhancements

- Additional PII types (SSN, credit cards, addresses)
- Redis-based mapping storage for distributed systems
- Support for additional LLM providers
- Async/await support
- Custom entity detection rules
