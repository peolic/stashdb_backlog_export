# coding: utf-8
import re
import string
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

strikethrough_pattern = re.compile(r'(~+)([^~]+)\1')


@dataclass
class SheetCell:
    value: str
    links: List[str]
    note: str
    done: bool

    @classmethod
    def parse(cls, cell: dict):
        value: str = cell.get('formattedValue', '')
        note: str = cell.get('note', '')
        done: bool = cell.get('effectiveFormat', {}).get('textFormat', {}).get('strikethrough', False)

        format_runs: List[Dict[str, Any]] = cell.get('textFormatRuns', [])

        links: List[str] = []
        for fr in format_runs:
            if link := fr['format'].get('link', {}).get('uri'):
                if urlparse(link).netloc and link not in links:
                    links.append(link)

        # Text can appear strike-through but effective format says not due to line breaks
        if not done and format_runs:
            # FIXME: second condition broken
            # done = all((
            #     (fr['format'].get('strikethrough', False)
            #      or value[fr.get('startIndex', 0)] in string.whitespace)
            #     for fr in format_runs
            # ))
            done = all((fr['format'].get('strikethrough', False) for fr in format_runs))

        # Mark strike-through text
        if not done:
            start: Optional[int] = None
            for fr in reversed(format_runs):
                end = start
                start = fr.get('startIndex', None)
                if not fr['format'].get('strikethrough', False):
                    continue

                # Prevent line breaks after start / before end
                if len(value[start:end]) > 1:
                    if start is not None and value[start] == '\n':
                        start += 1
                        fr['startIndex'] = start
                    if end is not None and value[end-1] == '\n':
                        end -= 1

                # Remove struckthrough link
                if st_link := fr['format'].get('link', {}).get('uri'):
                    with suppress(ValueError):
                        links.remove(st_link)

                value = ''.join((
                    value[:start] if start is not None else '',
                    '\u0002',
                    value[start:end],
                    '\u0003',
                    value[end:] if end is not None else '',
                ))

            note = strikethrough_pattern.sub('\u0002\\2\u0003', note)

        link: Optional[str] = cell.get('hyperlink')
        if link and urlparse(link).netloc and link not in links:
            links.append(link)

        return cls(value=value, links=links, note=note, done=done)

    @property
    def first_link(self) -> Optional[str]:
        return next(iter(self.links), None)


@dataclass
class SheetRow:
    num: int
    cells: List[SheetCell]

    @classmethod
    def parse(cls, row: List[dict], num: int, fill: int):
        cells = [SheetCell.parse(cell) for cell in row]
        if fill > (count := len(cells)):
            cells.extend(
                SheetCell(value='', links=[], note='', done=False)
                for _ in range(fill - count)
            )
        return cls(num=num, cells=cells)

    def is_done(self, which: int = 1) -> bool:
        checkboxes = [c.value == 'TRUE' for c in self.cells if c.value in ('TRUE', 'FALSE')]
        if not checkboxes:
            raise self.CheckboxNotFound('No checkboxes found!', self.num)

        try:
            return checkboxes[which - 1]
        except IndexError:
            es = 'es' if (count := len(checkboxes)) > 1 else ''
            raise self.CheckboxNotFound(f'Only {count} checkbox{es} found, cannot get checkbox #{which}!', self.num)

    class CheckboxNotFound(Exception):
        def __init__(self, message: str, row_num: int):
            # Call the base class constructor with the parameters it needs
            super().__init__(message)
            self.row_num = row_num


@dataclass
class Sheet:
    id: int
    title: str
    row_count: int
    column_count: int
    frozen_row_count: int
    frozen_column_count: int
    columns: List[str] = field(default_factory=list, repr=False)
    rows: List[SheetRow] = field(default_factory=list, repr=False)

    @classmethod
    def parse(cls, sheet: dict):
        props = sheet['properties']
        grid_props = props['gridProperties']

        return cls(
            id=props['sheetId'],
            title=props['title'],
            row_count=grid_props['rowCount'],
            column_count=grid_props['columnCount'],
            frozen_row_count=grid_props.get('frozenRowCount', 0),
            frozen_column_count=grid_props.get('frozenColumnCount', 0),
        )

    def parse_data(self, sheet: dict):
        row_data = sheet['data'][0]['rowData']

        # if frozen row is not set (== 0), fail
        if not self.frozen_row_count:
            raise ValueError(f'Frozen Row Count is undefined ({self.frozen_row_count})')

        # if frozen row is not set (== 0), default to head=0, data=1
        head_row = (self.frozen_row_count - 1) if self.frozen_row_count else 0
        data_row = self.frozen_row_count if self.frozen_row_count else 1

        self.columns = [
            col.get('formattedValue', '')
            for col in row_data[head_row]['values']
        ]

        col_count = len(self.columns)
        for num, row in enumerate(row_data[data_row:], (self.frozen_row_count or 0) + 1):
            row_obj = SheetRow.parse(row['values'], num, fill=col_count)
            self.rows.append(row_obj)

        # noop
        setattr(self, 'parse_data', lambda: None)

    def get_column_index(self, text: Union[str, re.Pattern]) -> int:
        for idx, col in enumerate(self.columns):
            if isinstance(text, re.Pattern) and text.search(col):
                return idx
            if isinstance(text, str) and text in col:
                return idx

        return -1

    def get_all_column_indices(self, text: Union[str, re.Pattern]) -> List[int]:
        return [
            idx for idx, col in enumerate(self.columns)
            if isinstance(text, re.Pattern) and text.search(col)
            or isinstance(text, str) and text in col
        ]


"""
interface DataStructure {
    sheets: Array<{
        data: Array<{
            rowData: Array<{
                values: Array<{
                    formattedValue?: string
                    hyperlink?: string
                    note?: string
                    effectiveFormat: {
                        textFormat: {
                            strikethrough: boolean
                        }
                    }
                    textFormatRuns?: Array<{
                        startIndex?: number
                        format: {
                            link?: {
                                uri: string
                            }
                            strikethrough?: boolean
                        }
                    }>
                }>
            }>
        }>
        properties: {
            sheetId: number
            title: string
            gridProperties: {
                rowCount: number
                columnCount: number
                frozenRowCount?: number
                frozenColumnCount?: number
            }
        }
    }>
}
"""
