# coding: utf-8
import logging
from typing import Literal

def setup_logging():
    logger = logging.getLogger(__package__)
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler()
    handler.name = 'main_handler'
    handler.setFormatter(SimpleFormatter())
    logger.addHandler(handler)

    return logger

class SimpleFormatter(logging.Formatter):

    def __init__(self, fmt: str = '{message}') -> None:
        super().__init__(fmt, style='{')

    def format(self, record: logging.LogRecord) -> str:
        row_num_fmt = 'Row {row_num:<4} | ' if record.__dict__.get('row_num') else ''
        self.__init__(row_num_fmt + '{message}')
        return super().format(record)

class LoggerMixin:
    def __init__(self, name: str, object_type: Literal['performer', 'scene'] | None = None):
        # logging.getLogger('.'.join((__name__, type(self).__qualname__)))
        super().__init__()
        self.__logger = logging.getLogger(name)

        # inject object type to every log
        def inject(record: logging.LogRecord) -> bool | logging.LogRecord:
            record.__dict__['obj'] = object_type
            return record

        self.__logger.addFilter(inject)

    def log(self,
            level: Literal['', 'warning', 'error'],
            text: str,
            row_num: int | None = None,
            *,
            uuid: str | None = None):

        match level:
            case 'error':
                logging_level = logging.ERROR
            case 'warning':
                logging_level = logging.WARNING
            case _:
                logging_level = logging.INFO

        if level:
            text = f'{level.upper()}: {text}'

        self.__logger.log(
            logging_level,
            text,
            extra=dict(
                row_num=row_num,
                uuid=uuid,
            ),
        )
