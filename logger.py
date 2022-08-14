# coding: utf-8
import io
import sys
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass
from typing import List, Literal, Optional

LOG_LEVEL = Literal['debug', 'notice', 'warning', 'error']

@dataclass
class Message:
    level: Literal['', LOG_LEVEL]
    text: str
    filename: Optional[str] = None
    line: Optional[int] = None
    end_line: Optional[int] = None
    title: Optional[str] = None

    def __str__(self) -> str:
        if False:
            return f'{self.level.upper()}: {self.text}' if self.level else self.text

        # https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-a-notice-message
        params: List[str] = []
        if self.filename:
            params.append(f'file={self.filename}')
        if self.line:
            params.append(f'line={self.line}')
        if self.end_line:
            params.append(f'endLine={self.end_line}')
        if self.title:
            params.append(f'title={self.title}')

        params_str = f"' {','.join(params)}" if params else ''
        return f'::{self.level or "notice"}{params_str}::{self.text}'


@contextmanager
def report_errors(ci: bool):
    stdout = sys.stdout

    with redirect_stdout(io.StringIO()) as buffer:
        yield

        if not (output := buffer.getvalue()):
            return

        if not ci:
            print(output, file=stdout)
            return

        for line in output.splitlines():
            level = 'notice'
            if 'WARNING:' in line:
                level = 'warning'
            if 'ERROR' in line:
                level = 'error'
            print(Message(level, line), file=stdout)
