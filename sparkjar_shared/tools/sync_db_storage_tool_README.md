# SyncDBStorageTool

A synchronous database storage tool for the SparkJAR Crew book ingestion system. This tool stores transcribed book pages to client-specific PostgreSQL databases with proper transaction management and error handling.

## Overview

The `SyncDBStorageTool` is designed specifically for the book ingestion crew to store OCR-processed manuscript pages. It handles:

- Client-specific database connections
- Automatic page number extraction from filenames
- Proper transaction management with rollback on errors
- BookIngestions table schema compliance
- Comprehensive error handling and logging

## Features

### Core Functionality
- **Synchronous Operations**: Uses synchronous SQLAlchemy for reliable database operations
- **Client Database Lookup**: Automatically retrieves client database URLs from the main database
- **Page Number Extraction**: Intelligent extraction of page numbers from various filename patterns
- **Upsert Behavior**: Updates existing pages or creates new ones as needed
- **Transaction Management**: Proper commit/rollback handling with error recovery

### Filename Pattern Recognition
The tool can extract page numbers from various filename patterns:
- `page_001.jpg`, `page 5.png`, `page15.tiff`
- `p_10.jpg`, `p 25.png`, `p99.webp`
- `pg_007.jpg`, `pg 12.png`, `pg33.gif`
- `manuscript_001.jpg`, `scan_042.png`
- `001_handwritten.jpg`, `025_manuscript.png`
- `document_15_final.jpg`, `Book_Chapter_05_Page_123.jpg`

### Error Handling
- Input validation with descriptive error messages
- Database connection error handling
- Transaction rollback on failures
- Graceful handling of missing clients or invalid UUIDs
- Comprehensive logging for debugging

## Usage

### Basic Usage

```python
from sync_db_storage_tool import SyncDBStorageTool

tool = SyncDBStorageTool()

# Store a page with explicit page number
result = tool._run(
    client_user_id="550e8400-e29b-41d4-a716-446655440000",
    book_key="hemingway_old_man_sea_manuscript",
    page_number=1,
    file_name="page_001.jpg",
    language_code="en",
    page_text="The Old Man and the Sea...",
    ocr_metadata={
        "file_id": "google_drive_file_id",
        "processing_stats": {"total_words": 35},
        "ocr_passes": 3,
        "model_used": "gpt-4o"
    }
)
```

### Auto Page Number Extraction

```python
# Page number will be extracted from filename
result = tool._run(
    client_user_id="550e8400-e29b-41d4-a716-446655440000",
    book_key="scientific_journal_1923",
    file_name="manuscript_page_042.tiff",  # Page 42 extracted
    language_code="en",
    page_text="Journal content...",
    ocr_metadata={"file_id": "123", "ocr_passes": 3}
)
```

### CrewAI Integration

In your CrewAI configuration:

```yaml
# agents.yaml
storage_agent:
  role: "Data Storage Specialist"
  goal: "Store transcribed pages in database"
  backstory: "Efficiently stores OCR results with proper error handling"
  model: "gpt-4.1-nano"
  tools:
    - SyncDBStorageTool

# tasks.yaml
storage_task:
  description: "Store the transcribed page using SyncDBStorageTool"
  expected_output: "JSON confirmation with page_id and storage status"
  agent: storage_agent
  context: [ocr_task]
```

## Input Schema

### Required Parameters
- `client_user_id` (str): Client user UUID
- `book_key` (str): Book identifier
- `file_name` (str): Original filename
- `language_code` (str): Language code (e.g., "en", "es")
- `page_text` (str): Transcribed text from OCR

### Optional Parameters
- `page_number` (int): Page number (extracted from filename if not provided)
- `ocr_metadata` (dict): OCR processing metadata (default: {})
- `version` (str): Version identifier (default: "original")

## Output Format

### Success Response
```json
{
  "success": true,
  "page_id": "uuid-string",
  "book_key": "book_identifier",
  "page_number": 1,
  "action": "created|updated",
  "stored_at": "2024-01-01T12:00:00"
}
```

### Error Response
```json
{
  "success": false,
  "error": "Detailed error message"
}
```

## Database Schema

The tool stores data in the `book_ingestions` table:

```sql
CREATE TABLE book_ingestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_key TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    language_code TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'original',
    page_text TEXT NOT NULL,
    ocr_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## OCR Metadata Format

Expected OCR metadata structure:

```json
{
  "file_id": "google_drive_file_id",
  "processing_stats": {
    "total_words": 150,
    "normal_transcription": 120,
    "context_logic_transcription": 25,
    "unable_to_transcribe": 5
  },
  "unclear_sections": ["word1", "phrase2"],
  "ocr_passes": 3,
  "model_used": "gpt-4o",
  "processing_time_seconds": 12.5,
  "confidence_scores": {
    "overall": 0.87,
    "by_section": [0.92, 0.85, 0.81, 0.89]
  }
}
```

## Error Types

### Validation Errors
- Missing required fields
- Invalid UUID format
- Invalid data types

### Database Errors
- Client not found
- Database connection failures
- Transaction failures
- Schema constraint violations

### Processing Errors
- Page number extraction failures
- File handling errors
- Unexpected exceptions

## Configuration

### Environment Variables
- `DATABASE_URL_DIRECT`: Main database URL for client lookup

### Database Requirements
- PostgreSQL with UUID extension
- Client database URLs stored in `client_secrets` table
- Proper database permissions for the service account

## Testing

Run the test suite:

```bash
# Basic functionality tests
python test_sync_db_storage_tool.py

# Integration tests with realistic data
python test_sync_db_storage_integration.py

# Usage examples
python sync_db_storage_tool_example.py
```

## Performance Considerations

- **Connection Caching**: Database engines are cached per client
- **Transaction Efficiency**: Single transaction per page storage
- **Memory Management**: Automatic cleanup of database connections
- **Error Recovery**: Fast failure with detailed error messages

## Security

- **SQL Injection Protection**: Uses SQLAlchemy ORM with parameterized queries
- **Connection Security**: Secure database connections with proper credentials
- **Data Validation**: Input validation prevents malformed data storage
- **Error Sanitization**: Sensitive information excluded from error messages

## Monitoring and Logging

The tool provides comprehensive logging:
- Info level: Successful operations and page number extractions
- Warning level: Page number extraction failures
- Error level: Database errors and validation failures
- Debug level: Connection cleanup and minor issues

## Troubleshooting

### Common Issues

1. **"User not found" errors**: Verify client_user_id exists in client_users table
2. **"Database URL not found"**: Ensure client has database_url in client_secrets
3. **Connection errors**: Check database connectivity and credentials
4. **Page number extraction failures**: Verify filename follows supported patterns

### Debug Mode

Enable debug logging to see detailed operation information:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

## Requirements

- Python 3.8+
- SQLAlchemy 2.0+
- psycopg2-binary
- pydantic
- crewai

## License

Part of the SparkJAR Crew system. See project license for details.