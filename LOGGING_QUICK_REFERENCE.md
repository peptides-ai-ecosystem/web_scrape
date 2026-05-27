# Quick Reference: Adding Logging to Code

## Copy-Paste Templates

### 1. Import at Top of File
```python
from src.config import log_error, log_debug
```

### 2. Log in Try-Except Block
```python
def scrape_url(url):
    try:
        log_debug(f"Starting scrape: {url}", "page_scraper.py")
        
        # Your code here
        result = perform_scrape(url)
        
        log_debug(f"Scrape successful: {url}", "page_scraper.py")
        return result
        
    except Exception as e:
        log_error(f"Scrape failed for {url}: {str(e)}", "page_scraper.py")
        raise
```

### 3. Log Important Milestones
```python
def process_batch(items):
    log_debug(f"Processing {len(items)} items", "batch_processor.py")
    
    results = []
    for item in items:
        try:
            result = process_item(item)
            results.append(result)
        except Exception as e:
            log_error(f"Item processing failed: {item}: {str(e)}", "batch_processor.py")
    
    log_debug(f"Processed {len(results)} items successfully", "batch_processor.py")
    return results
```

### 4. Log with Context Variables
```python
def extract_data(url, category):
    try:
        log_debug(f"Extracting {category} from {url}", "extractor.py")
        data = extract(url, category)
        log_debug(f"Extracted {len(data)} items from {category}", "extractor.py")
        return data
    except Exception as e:
        log_error(f"Extraction failed ({category}): {str(e)}", "extractor.py")
        return []
```

### 5. Log Loop Progress (for debugging)
```python
def process_urls(urls):
    for idx, url in enumerate(urls, 1):
        log_debug(f"[{idx}/{len(urls)}] Processing {url}", "url_processor.py")
        try:
            result = process(url)
        except Exception as e:
            log_error(f"Failed to process ({idx}/{len(urls)}): {url}: {str(e)}", "url_processor.py")
```

### 6. Log Performance Metrics
```python
import time

def scrape_urls(urls):
    start = time.time()
    log_debug(f"Starting scrape of {len(urls)} URLs", "scraper.py")
    
    results = []
    for url in urls:
        try:
            result = scrape(url)
            results.append(result)
        except Exception as e:
            log_error(f"Failed: {url}: {str(e)}", "scraper.py")
    
    elapsed = round(time.time() - start, 2)
    log_debug(f"Completed in {elapsed}s: {len(results)} successful", "scraper.py")
    return results
```

### 7. Log Configuration/Setup
```python
class DataManager:
    def __init__(self, config):
        self.config = config
        log_debug(f"DataManager initialized: {config}", "data_manager.py")
    
    def load_data(self):
        try:
            log_debug("Loading data from database", "data_manager.py")
            data = self._query_db()
            log_debug(f"Loaded {len(data)} records", "data_manager.py")
            return data
        except Exception as e:
            log_error(f"Database load failed: {str(e)}", "data_manager.py")
            return []
```

### 8. Log State Changes
```python
def update_status(item_id, status):
    try:
        log_debug(f"Updating item {item_id} status to {status}", "state_manager.py")
        update_db(item_id, status)
        log_debug(f"Item {item_id} status updated successfully", "state_manager.py")
    except Exception as e:
        log_error(f"Status update failed ({item_id}): {str(e)}", "state_manager.py")
```

## File-Specific Logger Names

Use these conventions for filename parameter:

| Module | Filename Parameter |
|--------|-------------------|
| Page scraper | `"page_scraper.py"` |
| Scraper manager | `"scraper_manager.py"` |
| CSV storage | `"csv_storage.py"` |
| Hero extractor | `"hero_extractor.py"` |
| Section extractor | `"section_extractor.py"` |
| Community extractor | `"community_extractor.py"` |
| Graph extractor | `"graph_extractor.py"` |
| Quick guide extractor | `"quick_guide_extractor.py"` |
| WebDriver factory | `"webdriver_factory.py"` |
| Main entry point | `"main.py"` |

## Logging Checklist

When adding a new module/function:

- [ ] Import `log_error` and `log_debug` at top
- [ ] Wrap main logic in try-except
- [ ] Log function entry with `log_debug()`
- [ ] Log key operations/milestones with `log_debug()`
- [ ] Log function success with `log_debug()`
- [ ] Log all exceptions with `log_error()`
- [ ] Include filename parameter in all log calls
- [ ] Use f-strings for context in messages

## Common Logging Patterns

### Pattern 1: Start-Process-Complete
```python
log_debug("Starting process", "file.py")
# ... do work ...
log_debug("Process completed", "file.py")
```

### Pattern 2: Error Handling
```python
try:
    # code
except Exception as e:
    log_error(f"Operation failed: {str(e)}", "file.py")
    # handle error
```

### Pattern 3: Status Updates
```python
log_debug(f"Status changed: {old} -> {new}", "file.py")
```

### Pattern 4: Data Flow
```python
log_debug(f"Input: {len(input_data)} items", "file.py")
result = transform(input_data)
log_debug(f"Output: {len(result)} items", "file.py")
```

### Pattern 5: Performance Tracking
```python
start = time.time()
# code
elapsed = time.time() - start
log_debug(f"Completed in {elapsed:.2f}s", "file.py")
```

## Do's and Don'ts

### ✓ DO
```python
log_debug("Scraping URL: https://example.com/peptide", "scraper.py")
log_error("Connection timeout after 30s: https://example.com", "scraper.py")
log_debug(f"Found {len(results)} results", "scraper.py")
```

### ✗ DON'T
```python
log_debug("Scraping")  # Too vague
log_error("Error")  # No context
log_debug(f"Results: {results}")  # Too much data in log
```

## Debugging with Logs

### Find errors in a specific module
```bash
grep "\[csv_storage.py\]" output/error_log.txt
```

### Count errors by module
```bash
grep -o "\[.*\.py\]" output/error_log.txt | sort | uniq -c
```

### Find specific error types
```bash
grep "timeout" output/error_log.txt
grep "Connection" output/error_log.txt
```

### Compare execution flow in debug log
```bash
grep "Processing" output/debug_log.txt
```

### Real-time monitoring during development
```bash
tail -f output/debug_log.txt | grep "scraper"
```
