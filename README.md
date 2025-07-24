# sparkjar-shared

Shared utilities and common code for SparkJAR services.

## Overview

This package provides shared functionality used across SparkJAR services:
- Database models and connections
- Authentication utilities
- Common API models
- Logging and monitoring
- Schema validation utilities

## Installation

```bash
# Install from local path (for development)
pip install -e /path/to/sparkjar-shared

# Or add to requirements.txt
-e ../sparkjar-shared  # For local development
```

## Usage

```python
# Database models
from sparkjar_shared.database import BaseModel, get_session

# Authentication
from sparkjar_shared.auth import verify_token, create_token

# Common models
from sparkjar_shared.models import JobStatus, ActorType

# Logging
from sparkjar_shared.logging import get_logger
```

## Project Structure

```
sparkjar-shared/
├── sparkjar_shared/
│   ├── __init__.py
│   ├── auth/          # Authentication utilities
│   ├── database/      # Database models and connections
│   ├── models/        # Shared Pydantic models
│   ├── logging/       # Logging configuration
│   └── utils/         # Common utilities
├── tests/
├── setup.py
└── requirements.txt
```

## Development

```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .

# Run tests
pytest tests/
```

## Publishing

```bash
# Build package
python setup.py sdist bdist_wheel

# Upload to PyPI (when ready)
twine upload dist/*
```

## Notes

- Extracted from sparkjar-crew monorepo
- Used by all SparkJAR services
- Consider publishing to PyPI for easier deployment
- Keep dependencies minimal to avoid conflicts