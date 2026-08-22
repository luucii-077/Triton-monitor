import gzip
import json
import logging
import logging.config
import logging.handlers
import os
import queue
import shutil
from datetime import datetime, timezone
from typing import Any


def gzip_namer(name: str) -> str:
    return f"{name}.gz"


def gzip_rotator(source: str, destination: str) -> None:
    with open(source, "rb") as source_file, gzip.open(
        destination, "wb", compresslevel=9
    ) as destination_file:
        shutil.copyfileobj(source_file, destination_file)
    os.remove(source)


class AsyncJSONFormatter(logging.Formatter):
    def _serialize_exception(self, error: BaseException) -> dict[str, Any]:
        serialized: dict[str, Any] = {
            "class": type(error).__name__,
            "message": str(error),
            "notes": list(getattr(error, "__notes__", [])),
        }
        if isinstance(error, BaseExceptionGroup):
            serialized["nested_exceptions"] = [
                self._serialize_exception(child) for child in error.exceptions
            ]
        if error.__cause__ is not None:
            serialized["cause"] = self._serialize_exception(error.__cause__)
        elif error.__context__ is not None and not error.__suppress_context__:
            serialized["context"] = self._serialize_exception(error.__context__)
        return serialized

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat().replace("+00:00", "Z")
        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "process": record.process,
            "thread_name": record.threadName,
            "task_name": getattr(record, "taskName", None),
            "filename": record.filename,
            "line": record.lineno,
        }
        if record.exc_info:
            _, error, _ = record.exc_info
            if error is not None:
                payload["exception_tree"] = self._serialize_exception(error)
                payload["stack_trace"] = self.formatException(record.exc_info)

        reserved = set(vars(logging.LogRecord("", 0, "", 0, "", (), None)))
        reserved.update({"message", "asctime", "taskName"})
        payload.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in reserved and not key.startswith("_")
            }
        )
        return json.dumps(payload, ensure_ascii=False, default=str)


class _PreservingQueueHandler(logging.handlers.QueueHandler):
    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        prepared = super().prepare(record)
        prepared.exc_info = record.exc_info
        return prepared


def setup_triton_logging(log_filename: str = "triton_services.log") -> logging.Logger:
    schema = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": "triton_telemetry.logging_engine.AsyncJSONFormatter"},
            "console": {"format": "%(asctime)s [%(levelname)s] %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "console",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "json",
                "filename": log_filename,
                "maxBytes": 2 * 1024 * 1024,
                "backupCount": 3,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "triton_monitor": {
                "level": "DEBUG",
                "handlers": ["console", "file"],
                "propagate": False,
            }
        },
    }
    logging.config.dictConfig(schema)
    logger = logging.getLogger("triton_monitor")
    handlers = logger.handlers[:]
    file_handler = next(
        handler
        for handler in handlers
        if isinstance(handler, logging.handlers.RotatingFileHandler)
    )
    file_handler.namer = gzip_namer
    file_handler.rotator = gzip_rotator

    log_queue: queue.Queue[logging.LogRecord] = queue.Queue()
    queue_handler = _PreservingQueueHandler(log_queue)
    listener = logging.handlers.QueueListener(
        log_queue, *handlers, respect_handler_level=True
    )
    logger.handlers = [queue_handler]
    listener.start()
    logger.triton_listener = listener  # type: ignore[attr-defined]
    return logger
