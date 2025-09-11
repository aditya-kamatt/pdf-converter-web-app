import logging
import logging.config
import os
import time

_configured = False  # simple idempotency guard


def setup_logging() -> None:
    global _configured
    if _configured:
        return

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    pdfminer_level = os.getenv("LOG_LEVEL_PDFMINER", "INFO").upper()
    use_utc = os.getenv("LOG_USE_UTC", "1") in {"1", "true", "yes"}
    stream = "ext://sys.stderr"  # better default for logs
    log_file = os.getenv("LOG_FILE")  # optional

    class _UTCFormatter(logging.Formatter):
        converter = time.gmtime

    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    formatter = {"format": fmt, "datefmt": datefmt}
    formatter_def = (
        {"()": _UTCFormatter, **formatter}
        if use_utc
        else {"()": "logging.Formatter", **formatter}
    )

    config: dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"default": formatter_def},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": "default",
                "stream": stream,
            }
        },
        "loggers": {
            "": {  # root
                "level": level,
                "handlers": ["console"],
                "propagate": False,
            },
            "pdfminer": {
                "level": pdfminer_level,
                "handlers": ["console"],
                "propagate": False,
            },
            # Uncomment if you use Flask
            # "werkzeug": {"level": "INFO", "handlers": ["console"], "propagate": False},
        },
    }

    if log_file:
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": level,
            "formatter": "default",
            "filename": log_file,
            "maxBytes": 2 * 1024 * 1024,
            "backupCount": 2,
        }
        config["loggers"][""]["handlers"].append("file")

    logging.config.dictConfig(config)
    _configured = True
