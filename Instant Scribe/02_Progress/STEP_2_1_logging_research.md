# Research Notes – Implementing a Rotating File Logger in Python

## 1. Standard Library Support

**logging.handlers** module ships with two built-in rotating handlers:

1. **RotatingFileHandler** – rotates when the log file reaches a configured size.
2. **TimedRotatingFileHandler** – rotates at fixed time intervals (e.g., daily, hourly).

Both inherit from `BaseRotatingHandler` and are part of Python's standard library (no extra packages required).

---

## 2. RotatingFileHandler – Size-based Rotation

```python
from logging.handlers import RotatingFileHandler
import logging
import os

LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)  # ensure folder exists

handler = RotatingFileHandler(
    filename=os.path.join(LOG_DIR, "app.log"),
    mode="a",               # append; default
    maxBytes=5_000_000,      # 5 MB
    backupCount=3,           # keep 3 old files: app.log.1-3
    encoding="utf-8",
    delay=False              # open file immediately (default)
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[handler, logging.StreamHandler()]
)
```

Key parameters:
- **maxBytes**: trigger size (0 disables rotation).
- **backupCount**: how many old files to keep (0 → unlimited).
- On rollover, current file becomes `app.log.1`, etc.

---

## 3. TimedRotatingFileHandler – Time-based Rotation

```python
from logging.handlers import TimedRotatingFileHandler
import logging
import os, datetime

handler = TimedRotatingFileHandler(
    filename="logs/app.log",
    when="midnight",        # rotate at midnight (see table below)
    interval=1,              # every day
    backupCount=7,           # keep one week of logs
    encoding="utf-8",
    utc=True                 # use UTC timestamps
)
```

`when` values:
- "S" seconds │ "M" minutes │ "H" hours │ "D" days
- "W0"–"W6" weekday (0=Mon) │ "midnight"

---

## 4. Directory & Permissions

- Create a dedicated `logs/` directory in the project root.
- Ensure the application has write permissions in production.
- Consider log rotation policy of the host OS (e.g., logrotate on Linux) to avoid conflicts.

---

## 5. Thread/Process Safety

- **RotatingFileHandler** is *not* multi-process safe; concurrent writers can corrupt rotation.
- For multi-process apps, alternatives include:
  - `ConcurrentRotatingFileHandler` (third-party pkg `concurrent-log-handler`).
  - System tools (`logrotate`) + `WatchedFileHandler`.

---

## 6. Configuration via logging.config

Python supports declarative config (YAML/JSON/dict). Example snippet:

```python
LOGGING = {
    "version": 1,
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/app.log",
            "maxBytes": 10485760,  # 10 MB
            "backupCount": 5,
            "formatter": "std",
        }
    },
    "formatters": {
        "std": {
            "format": "%(asctime)s %(levelname)s %(name)s | %(message)s"
        }
    },
    "root": {"handlers": ["file"], "level": "INFO"},
}
```

---

## 7. Best Practices Checklist

- [ ] Create `logs/` on startup or via deployment script.
- [ ] Use UTF-8 encoding to avoid Unicode errors.
- [ ] Keep `backupCount` > 0 to enable rotation.
- [ ] Add a console handler for real-time debugging.
- [ ] In container/K8s environments, prefer stdout + external log collection.

---

## 8. References

1. Python Docs – logging.handlers: https://docs.python.org/3/library/logging.handlers.html
2. Mike Driscoll, *Python 101 – Creating Rotating Logs*: https://www.blog.pythonlibrary.org/2014/02/11/python-how-to-create-rotating-logs/
3. `concurrent-log-handler` package: https://pypi.org/project/concurrent-log-handler/