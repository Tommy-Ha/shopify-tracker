from __future__ import annotations

import json
import logging
import logging.config

import datetime


LOG_RECORD_BUILTIN_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}

class CustomJSONFormatter(logging.Formatter):
    def __init__(
        self,
        *,
        fmt_keys: dict[str, str] | None = None,
    ):
        super().__init__()

        if fmt_keys is not None:
            self.fmt_keys = fmt_keys
        else:
            self.fmt_keys = {}

    def format(self, record: logging.LogRecord) -> str:
        message = self._prepare_log_dict(record)
        return json.dumps(message, default=str)

    def _prepare_log_dict(self, record: logging.LogRecord):
        always_fields = {
            "message": record.getMessage(),
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat(),
        }

        if record.exc_info is not None:
            always_fields["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info is not None:
            always_fields["stack_info"] = self.formatStack(record.stack_info)

        message = {
            key: value
            if (value := always_fields.pop(v, None)) is not None
            else getattr(record, v)
            for key, v in self.fmt_keys.items()
        }
        message.update(always_fields)

        for key, value in record.__dict__.items():
            if key not in LOG_RECORD_BUILTIN_ATTRS:
                message[key] = value

        return message


LOGGING_DICT_CONFIG = {
    "version": 1,
    "disable_existing_loggers": "false",
    "formatters": {
        "console": {
            "format": "[%(asctime)s] [%(name)s] [%(levelname)s] - %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
            "encoding": "utf-8"
        },
        "json": {
            "()": "src.logger.CustomJSONFormatter",
            "fmt_keys": {
                "level": "levelname",
                "message": "message",
                "timestamp": "timestamp",
                "logger": "name",
                "module": "module",
                "function": "funcName",
                "line": "lineno",
                "thread_name": "threadName"
            }
        }
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "console",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "json",
            "filename": "logs/trackers.log.jsonl",
            "maxBytes": 10000,
            "backupCount": 3,
        }
    },
    "loggers": {
        "root": {
            "level": "DEBUG",
            "handlers": [
                "stdout",
                # "file"
            ]
        },
        "general": {},
        "httpx": {
            "handlers": []
        },
        "tenacity": {},
        "sqlalchemy": {}
    }
}


class LoggerNotInConfig(Exception):
    ...


def get_logger(name: str) -> logging.Logger:
    if name not in LOGGING_DICT_CONFIG["loggers"].keys():
        raise LoggerNotInConfig

    return logging.getLogger(name=name)


def init_logger() -> None:
    logging.config.dictConfig(LOGGING_DICT_CONFIG)


def main() -> None:
    init_logger()



if __name__ == "__main__":
    main()
