# Logging System Guide

## Overview

The application now has a complete logging system with three key components:

1. **MASTER_CSV** - Main data output file
2. **ERROR_LOG** - Error logging for exceptions and failures
3. **DEBUG_LOG** - Debug logging for execution flow (no errors)

## Configuration

All paths are configured in `src/config.py`:

```python
OUTPUT_DIR = Path("output")
MASTER_CSV = OUTPUT_DIR / "pep_pedia_master.csv"
ERROR_LOG = OUTPUT_DIR / "error_log.txt"
DEBUG_LOG = OUTPUT_DIR / "debug_log.txt"
```

Environment variable override (optional):
```bash
export OUTPUT_DIR=/custom/path
```

## Logging Functions

### 1. `log_error(message, filename=None)`

Log error messages to ERROR_LOG with timestamp.

**Usage:**
```python
from src.config import log_error

# Log error with file context
log_error("Failed to connect to database", "db_manager.py")

# Log error without file context
log_error("Unknown error occurred")
```

**Output (ERROR_LOG):**
```
[2026-05-27 06:04:06] [db_manager.py] Failed to connect to database
[2026-05-27 06:04:07] Unknown error occurred
```

### 2. `log_debug(message, filename=None)`

Log debug messages to DEBUG_LOG with timestamp (for tracking normal flow).

**Usage:**
```python
from src.config import log_debug

# Log debug with file context
log_debug("Processing URL: https://example.com", "page_scraper.py")

# Log debug without file context
log_debug("Starting scraper execution")
```

**Output (DEBUG_LOG):**
```
[2026-05-27 06:04:05] [page_scraper.py] Processing URL: https://example.com
[2026-05-27 06:04:06] Starting scraper execution
```

### 3. `clear_logs()`

Clear both ERROR_LOG and DEBUG_LOG files (useful at start of execution).

**Usage:**
```python
from src.config import clear_logs

# Clear logs
clear_logs()  # Prints confirmation message
```

### 4. Import All Logging Variables

```python
from src.config import (
    MASTER_CSV,      # Path to CSV output
    ERROR_LOG,       # Path to error log
    DEBUG_LOG,       # Path to debug log
    OUTPUT_DIR,      # Output directory
    log_error,       # Error logging function
    log_debug,       # Debug logging function
    clear_logs       # Clear logs function
)
```

## Log File Structure

### ERROR_LOG Example
```
[2026-05-27 06:04:06] [page_scraper.py] URL not accessible: Connection timeout
[2026-05-27 06:04:10] [csv_storage.py] Failed to save CSV: Disk full error
[2026-05-27 06:04:15] Fatal error during scraping: WebDriver crashed
```

### DEBUG_LOG Example
```
[2026-05-27 06:04:00] [main.py] Starting scraper execution
[2026-05-27 06:04:01] [scraper_manager.py] ScraperManager initialized with 4 processes
[2026-05-27 06:04:05] [scraper_manager.py] Starting scrape batch with 50 URLs
[2026-05-27 06:04:06] [page_scraper.py] Processing URL: https://peptide1.org
[2026-05-27 06:04:10] [page_scraper.py] Found 3 categories for https://peptide1.org
[2026-05-27 06:04:12] [page_scraper.py] Successfully scraped 3 results from URL
[2026-05-27 06:05:30] [scraper_manager.py] Saving 150 records to output/pep_pedia_master.csv
[2026-05-27 06:05:35] [csv_storage.py] Successfully saved 150 rows to output/pep_pedia_master.csv
[2026-05-27 06:05:36] [main.py] Total execution time: 95.5 seconds
```

## Current Implementation

### Files Updated:

1. **src/config.py**
   - Settings class with all configuration variables
   - Module-level exports for backward compatibility
   - Three logging functions: `log_error()`, `log_debug()`, `clear_logs()`

2. **main.py**
   - Clears logs at start of execution
   - Logs debug messages for start/completion
   - Logs errors if scraping fails

3. **src/services/page_scraper.py**
   - Logs when URL processing starts/completes
   - Logs category information
   - Logs errors with context

4. **src/services/scraper_manager.py**
   - Logs manager initialization
   - Logs batch start and completion
   - Logs results saved

5. **src/infrastructure/csv_storage.py**
   - Wrapped save operation in try-except
   - Logs successful CSV saves
   - Logs errors if save fails

6. **src/data_summary.py**
   - Updated imports to use new config

## Best Practices

### 1. Always Include File Context
```python
# ✓ Good - Includes file context
log_error("Error occurred", "page_scraper.py")
log_debug("Processing started", "scraper_manager.py")

# ✗ Avoid - No file context
log_error("Error occurred")
log_debug("Processing started")
```

### 2. Use Descriptive Messages
```python
# ✓ Good
log_debug(f"Processing category '{cat}' for {url}", "page_scraper.py")
log_error(f"Failed to scrape {url}: Connection timeout", "page_scraper.py")

# ✗ Avoid
log_debug("Processing", "page_scraper.py")
log_error("Error", "page_scraper.py")
```

### 3. Clear Logs at Application Start
```python
# In main.py or entry point
if __name__ == "__main__":
    clear_logs()
    # Rest of application...
```

### 4. Log Both Success and Failure
```python
try:
    result = perform_operation()
    log_debug(f"Operation successful: {result}", "module.py")
    return result
except Exception as e:
    log_error(f"Operation failed: {str(e)}", "module.py")
    raise
```

## Monitoring

To monitor logs during execution:

```bash
# Watch ERROR_LOG in real-time
tail -f output/error_log.txt

# Watch DEBUG_LOG in real-time
tail -f output/debug_log.txt

# View all errors
cat output/error_log.txt

# View all debug messages
cat output/debug_log.txt

# Count errors
wc -l output/error_log.txt

# Find specific error patterns
grep "timeout" output/error_log.txt
grep "[csv_storage.py]" output/debug_log.txt
```

## Example: Complete Logging Flow

```python
from src.config import (
    MASTER_CSV,
    ERROR_LOG,
    DEBUG_LOG,
    log_error,
    log_debug,
    clear_logs
)

def process_data():
    clear_logs()  # Start fresh
    
    try:
        log_debug("Loading data", "data_processor.py")
        data = load_data()
        
        log_debug(f"Loaded {len(data)} records", "data_processor.py")
        
        results = transform_data(data)
        log_debug(f"Transformed to {len(results)} records", "data_processor.py")
        
        save_results(results)
        log_debug(f"Saved results to {MASTER_CSV}", "data_processor.py")
        
    except Exception as e:
        log_error(f"Processing failed: {str(e)}", "data_processor.py")
        raise
```

## Troubleshooting

### Logs not appearing?
1. Check that OUTPUT_DIR directory exists
2. Verify write permissions on output folder
3. Check for file lock issues (log files open in editor)

### ERROR_LOG but no DEBUG_LOG entries?
- This is normal if no debug calls were made
- Use `log_debug()` calls explicitly in your code

### Logs getting too large?
- Implement log rotation (add to config.py)
- Periodically archive old logs
- Use `clear_logs()` between execution batches
