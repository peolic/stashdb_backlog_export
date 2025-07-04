# coding: utf-8
import logging
from collections.abc import Callable

import extract


CallabaleFilter = Callable[[logging.LogRecord], bool | logging.LogRecord]

class report_errors:
    """Context Manager"""
    def __init__(self, ci: bool):
        self.ci = ci
        self.logger = logging.getLogger(extract.__package__)
        self.header = ''

        self.github_handler: logging.Handler | None = None
        self.__header_filter: CallabaleFilter | None = None
        self.main_handler: logging.Handler | None = None

    def __enter__(self):
        if not self.ci:
            return self

        self.main_handler = next((h for h in self.logger.handlers if h.name == 'main_handler'), None)
        if self.main_handler:
            self.main_handler.addFilter(self.__never_filter)

        self.github_handler = self.__github_annotation_handler()
        self.logger.addHandler(self.github_handler)

        return self

    def set_header(self, header: str):
        print(f'>>> {header}')

        if self.github_handler:
            if self.__header_filter:
                self.github_handler.removeFilter(self.__header_filter)
            if header:
                self.__header_filter = self.__annotation_title_filter(header)
                self.github_handler.addFilter(self.__header_filter)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.ci:
            return

        if self.github_handler:
            self.logger.removeHandler(self.github_handler)
            if self.__header_filter:
                self.github_handler.removeFilter(self.__header_filter)
        if self.main_handler:
            self.main_handler.removeFilter(self.__never_filter)

    @staticmethod
    def __github_annotation_handler() -> logging.Handler:
        handler = logging.StreamHandler()
        handler.name = 'github_annotation'
        handler.setFormatter(GithubAnnotationFormatter())

        return handler

    def __annotation_title_filter(self, header: str) -> CallabaleFilter:
        def func(record: logging.LogRecord) -> bool | logging.LogRecord:
            # inject header as annotation title
            record.__dict__['title'] = header
            return record
        return func

    @staticmethod
    def __never_filter(record: logging.LogRecord) -> bool | logging.LogRecord:
        return False

class GithubAnnotationFormatter(logging.Formatter):

    def __init__(self, fmt: str = '{message}') -> None:
        super().__init__(fmt, style='{')

    def format(self, record: logging.LogRecord) -> str:
        obj = record.__dict__.get('obj')
        uuid = record.__dict__.get('uuid')
        if obj and uuid:
            record.__dict__['file'] = f'{obj}s/{uuid[:2]}/{uuid}.yml'

        # https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-a-notice-message
        a_params = ','.join(
            f'{param}={{{param}}}'  # title={title}
            for param in ('title', 'file', 'line', 'endLine', 'col', 'endColumn')
            if record.__dict__.get(param)
        )

        a_type = record.levelname.lower()
        if a_type == 'info':
            a_type = 'notice'

        row_num_fmt = 'Row {row_num:<4} | ' if record.__dict__.get('row_num') else ''

        if a_params:
            annotation = f'::{a_type} {a_params}::'
        else:
            annotation = f'::{a_type}::'

        self.__init__(annotation + row_num_fmt + '{message}')
        return super().format(record)
