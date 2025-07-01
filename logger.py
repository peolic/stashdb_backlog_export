# coding: utf-8
import io
import re
import sys
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass, KW_ONLY
from typing import List, Literal, Optional

LOG_LEVEL = Literal['debug', 'notice', 'warning', 'error']

@dataclass
class Message:
    level: Literal['', LOG_LEVEL]
    text: str
    _: KW_ONLY
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

        params_str = f" {','.join(params)}" if params else ''
        return f'::{self.level or "notice"}{params_str}::{self.text}'


@contextmanager
def report_errors(ci: bool, header: Optional[str] = None):
    stdout = sys.stdout

    if header:
        print(f'>>> {header}')

    with redirect_stdout(io.StringIO()) as buffer:
        yield

        if not (output := buffer.getvalue()):
            return

        if not ci:
            print(output, file=stdout)
            return

        for text in output.splitlines():
            level = 'notice'
            if 'WARNING:' in text:
                level = 'warning'
            if 'ERROR' in text:
                level = 'error'

            row_num: Optional[int] = None
            if row_match := pattern_row.match(text):
                row_num = int(row_match.group(1))

            print(Message(level, text, title=header, line=row_num), file=stdout)

pattern_row = re.compile(r'\bRow (\d+)\b')
