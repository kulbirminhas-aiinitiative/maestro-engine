# Audit Logger Library

Enterprise-grade audit logging for AI workflows and chat interactions.

## Overview

The Audit Logger Library provides comprehensive audit logging capabilities for AI applications, chat interfaces, and automated workflows. It captures detailed information about interactions, performance metrics, file operations, and errors with optional full content logging for compliance and debugging purposes.

## Features

- **Comprehensive Logging**: Track chat interactions, persona activities, tool usage, file operations, performance metrics, and errors
- **Full Content Capture**: Optional complete storage of prompts and responses with secure file handling
- **Configurable Security**: Content hashing, encryption options, and secure file storage
- **Multiple Export Formats**: JSON and CSV exports with full content indexing
- **Analytics & Reporting**: Built-in analytics and reporting capabilities
- **Modular Architecture**: Clean separation of concerns with dedicated modules
- **Preset Configurations**: Ready-to-use configurations for development, production, compliance, and minimal setups

## Installation

Since this is a custom library, add the library path to your Python path:

```python
import sys
from pathlib import Path
sys.path.append(str(Path("path/to/maestro-v1")))

from libraries.audit_logger import AuditLogger, AuditConfig, AuditExporter, AuditViewer
from libraries.audit_logger.config import PresetConfigs
```

## Quick Start

### Basic Usage

```python
from pathlib import Path
from libraries.audit_logger import AuditLogger
from libraries.audit_logger.config import PresetConfigs

# Create configuration
config = PresetConfigs.development(
    session_id="my_session_001",
    project_path=Path("/path/to/your/project")
)

# Initialize logger
audit_logger = AuditLogger(config)

# Log a chat interaction
chat_id = audit_logger.log_chat_interaction(
    interaction_type="api_request",
    prompt="What is the weather today?",
    response="I cannot access real-time weather data...",
    model="claude-3",
    tokens_used=45,
    duration_seconds=1.2
)

# Log tool usage
tool_id = audit_logger.log_tool_usage(
    tool_name="weather_api",
    operation="get_forecast",
    parameters={"location": "New York"},
    result={"temperature": 72, "condition": "sunny"},
    success=True,
    duration_seconds=0.5
)

# Finalize session
summary = audit_logger.finalize_session()
```

### Configuration Presets

Choose from pre-configured setups:

```python
from libraries.audit_logger.config import PresetConfigs

# Development environment (30-day retention, auto-cleanup)
config = PresetConfigs.development(session_id, project_path)

# Production environment (encrypted, 1-year retention)
config = PresetConfigs.production(session_id, project_path)

# High compliance (encrypted, 7-year retention)
config = PresetConfigs.compliance(session_id, project_path)

# Minimal logging (basic tracking only)
config = PresetConfigs.minimal(session_id, project_path)
```

### Custom Configuration

```python
from libraries.audit_logger import AuditConfig

config = AuditConfig(
    session_id="custom_session",
    project_path=Path("/path/to/project"),
    full_content_logging=True,
    encrypt_sensitive_content=True,
    max_log_age_days=180,
    store_content_hashes=True,
    custom_metadata={"department": "AI", "compliance": "SOX"}
)
```

## Advanced Features

### Viewing and Analytics

```python
from libraries.audit_logger import AuditViewer

# Create viewer for active session
viewer = AuditViewer(audit_logger)

# Or load from existing audit files
viewer = AuditViewer(audit_path=Path("/path/to/audit_logs"))

# Get session summary
summary = viewer.get_session_summary()

# Get recent chat interactions
recent_chats = viewer.get_chat_interactions(limit=10)

# Get full content for specific interaction
full_content = viewer.get_full_interaction_content(interaction_id)

# Generate comprehensive analytics report
analytics = viewer.generate_analytics_report()
```

### Data Export

```python
from libraries.audit_logger import AuditExporter

exporter = AuditExporter(audit_logger)

# Export all data to JSON
export_data = exporter.export_to_json(
    output_path=Path("audit_complete.json"),
    include_full_content=True
)

# Export specific data to CSV
exporter.export_chat_interactions_to_csv(Path("chats.csv"))
exporter.export_tool_usages_to_csv(Path("tools.csv"))

# Export everything to directory
export_files = exporter.export_complete_audit_to_directory(
    output_dir=Path("audit_exports"),
    include_full_content=True
)
```

## API Reference

### AuditLogger

Main logging class that captures all audit events.

#### Key Methods

- `log_chat_interaction()` - Log AI chat interactions with full content
- `log_persona_activity()` - Log persona-specific activities
- `log_tool_usage()` - Log API calls and tool operations
- `log_file_operation()` - Log file creation/modification/deletion
- `log_performance_metric()` - Log timing and performance data
- `log_error()` - Log errors and exceptions
- `finalize_session()` - Complete session and generate summary

### AuditConfig

Configuration management with security and retention options.

#### Key Properties

- `full_content_logging` - Enable/disable complete content capture
- `encrypt_sensitive_content` - Enable encryption for sensitive data
- `store_content_hashes` - Generate SHA256 hashes for integrity
- `max_log_age_days` - Retention policy in days
- `custom_metadata` - Additional session metadata

### AuditViewer

Data viewing and analytics functionality.

#### Key Methods

- `get_session_summary()` - Session overview and statistics
- `get_chat_interactions()` - Retrieve chat data with filtering
- `get_full_interaction_content()` - Access complete conversation content
- `generate_analytics_report()` - Comprehensive analytics and insights

### AuditExporter

Data export in multiple formats.

#### Key Methods

- `export_to_json()` - Complete data export in JSON format
- `export_chat_interactions_to_csv()` - Chat data in CSV format
- `export_complete_audit_to_directory()` - Multi-format export to directory

## Data Models

### ChatInteraction
- Full conversation tracking with content, tokens, timing
- Optional full content storage in secure files
- Content hashing for integrity verification

### PersonaActivity
- Track activities by specific personas/users
- Duration tracking and detailed context

### ToolUsage
- API calls and tool operations
- Success/failure tracking with error details
- Parameter and result logging

### FileOperation
- File system operations (create, modify, delete)
- File size and hash tracking
- Success/failure monitoring

### PerformanceMetric
- Custom performance and timing metrics
- Contextual metadata support
- Multiple unit types

### AuditError
- Exception and error logging
- Stack trace capture
- Contextual error information

## File Structure

When initialized, the audit logger creates this structure:

```
project_path/
└── audit_logs/
    ├── chat_interactions_{session_id}.jsonl
    ├── persona_activities_{session_id}.jsonl
    ├── tool_usage_{session_id}.jsonl
    ├── file_operations_{session_id}.jsonl
    ├── performance_metrics_{session_id}.jsonl
    ├── errors_{session_id}.jsonl
    ├── session_{session_id}.json
    └── full_interactions/              # If full content logging enabled
        ├── prompt_{interaction_id}.txt
        ├── response_{interaction_id}.txt
        └── manifest_{interaction_id}.json
```

## Security Features

- **Content Hashing**: SHA256 hashes for data integrity
- **Encryption Support**: Optional encryption for sensitive content
- **Secure File Storage**: Separate files for full content with manifests
- **Access Control**: Configurable inclusion of sensitive data in exports
- **Retention Policies**: Automated cleanup with configurable retention periods

## Compliance Support

The library supports compliance requirements through:

- **Complete Audit Trail**: Full interaction logging with timestamps
- **Data Integrity**: Content hashing and verification
- **Long-term Retention**: Configurable retention periods (up to 7+ years)
- **Secure Export**: Multiple export formats with integrity checks
- **Metadata Tracking**: Custom metadata for regulatory requirements

## Performance Considerations

- **Async Logging**: Optional asynchronous logging for high-throughput scenarios
- **Memory Management**: Configurable memory buffers and batch writing
- **File Rotation**: Automatic log file management
- **Selective Logging**: Choose between full content and summary logging

## Example Use Cases

1. **AI Chat Applications**: Track all user interactions with conversation content
2. **Automated Workflows**: Monitor tool usage and file operations
3. **Compliance Auditing**: Maintain detailed logs for regulatory requirements
4. **Performance Monitoring**: Track response times and system metrics
5. **Error Analysis**: Comprehensive error logging with context
6. **Development Debugging**: Full content logging for troubleshooting

## License

MIT License - See LICENSE file for details.

## Version History

- **v2.0.0**: Modular library architecture with full content logging
- **v1.0.0**: Initial integrated logging implementation

---

For more examples and advanced usage, see the `audit_library_demo.py` file.
