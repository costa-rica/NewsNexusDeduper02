# LOGGING_METHODOLOGY_V02

## Overview

This document describes the new unified logging methodology for the **NewsNexusDeduper02** microservice.  
The goal is to support clear, environment-aware logging behavior for both **workstation** (local development) and **server** (production) environments.

---

## Objectives

1. **Use a single, unified logging system** across all modules.
2. **Use tqdm progress bars** when running locally (`RUN_ENVIRONMENT=workstation`).
3. **Emit 10% progress logs** when running on the server (`RUN_ENVIRONMENT=production` or other non-workstation values).
4. **Prefix all server logs** with the application name (defined in `.env` as `NAME_APP`).
5. Ensure logs remain **clean, structured, and readable** in PM2 logs and other aggregation systems.

---

## Environment Variables

The following variables are required in `.env`:

```bash
RUN_ENVIRONMENT=workstation    # or production / staging
NAME_APP=NewsNexusDeduper02
```

---

## Logging Implementation

### 1. Create `src/modules/logger.py`

This new module provides a reusable logger that automatically adjusts its formatting depending on the environment.

```python
# src/modules/logger.py
import os
import logging

def get_logger(name: str = None):
    """
    Returns a configured logger instance.
    - In workstation mode: simple, readable logs
    - In server mode: prefixed logs with [NAME_APP]
    """
    run_env = os.getenv("RUN_ENVIRONMENT", "production").lower()
    app_name = os.getenv("NAME_APP", "NewsNexusDeduper02")

    logger = logging.getLogger(name or app_name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()

    if run_env == "workstation":
        # Simple logs for local development
        formatter = logging.Formatter("%(levelname)s: %(message)s")
    else:
        # Structured logs for PM2 and server
        formatter = logging.Formatter(f"[{app_name}] %(message)s")

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
```

---

### 2. Replace tqdm progress bars with environment-aware progress logging

Any line currently using:
```python
with tqdm(total=len(records), desc="Processing embeddings", unit="records") as pbar:
```

Should be replaced with the following pattern:

```python
import os
from modules.logger import get_logger
logger = get_logger(__name__)

use_tqdm = os.getenv("RUN_ENVIRONMENT", "production").lower() == "workstation"
total = len(records)

if use_tqdm:
    from tqdm import tqdm
    progress_iter = tqdm(records, desc="Processing embeddings", unit="records")
else:
    progress_iter = records
    next_log_threshold = 0.1  # 10%

for i, record in enumerate(progress_iter, 1):
    # perform processing ...

    if not use_tqdm and total > 0:
        ratio = i / total
        if ratio >= next_log_threshold or i == total:
            percent = int(ratio * 100)
            logger.info(f"Processing embeddings: {percent}% ({i:,}/{total:,})")
            next_log_threshold += 0.1
```

This ensures:
- On **workstation**, tqdm displays a progress bar.
- On **server**, logs are emitted every ~10% of total progress.

---

### 3. Update all processors

Apply the same change to the following progress bars:

| Module | tqdm Description |
|---------|------------------|
| `load_processor.py` | `Processing combinations:` |
| `states_processor.py` | `Processing states:` |
| `url_check_processor.py` | `Processing URLs:` |
| `embedding_processor.py` | `Processing embeddings:` |

Each one should use the pattern above with an appropriate message.

---

### 4. Expected Behavior

#### Workstation (`RUN_ENVIRONMENT=workstation`)
```
INFO: Starting embedding process...
Processing embeddings: 100%|███████████████████████████████████████████████████████| 466697/466697 [13:30<00:00, 575.6records/s]
```

#### Server (`RUN_ENVIRONMENT=production`)
```
[NewsNexusDeduper02] Processing embeddings: 10% (46,670/466,697)
[NewsNexusDeduper02] Processing embeddings: 20% (93,339/466,697)
...
[NewsNexusDeduper02] Processing embeddings: 100% (466,697/466,697)
```

---

### 5. Notes

- This approach follows **Python logging best practices**: one logger with multiple formatters, depending on environment.
- It avoids duplicate log systems and keeps code maintainable.
- You can later add file or JSON handlers to `logger.py` if you adopt centralized logging.

---

**Version:** `V02`  
**Date:** `2025-10-31`  
**Author:** ChatGPT (GPT-5)`
