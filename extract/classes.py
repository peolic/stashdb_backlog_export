# coding: utf-8
import re
from dataclasses import dataclass, field
from typing import List, Optional, Union
from urllib.parse import urlparse


@dataclass
class SheetCell:
    value: str
    links: List[str]
    note: str
    done: bool

    @classmethod
    def parse(cls, cell: dict):
        links: List[str] = []
        for fr in cell.get('textFormatRuns', []):
            if link := fr['format'].get('link', {}).get('uri'):
                if urlparse(link).netloc:
                    links.append(link)

        link: Optional[str] = cell.get('hyperlink')
        if link and urlparse(link).netloc:
            links.append(link)

        done = cell.get('effectiveFormat', {}).get('textFormat', {}).get('strikethrough', False)

        return cls(
            value=cell.get('formattedValue', ''),
            links=links,
            note=cell.get('note', ''),
            done=done,
        )

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

        def __str__(self) -> str:
            return f'Row {self.row_num:<4} | {super().__str__()}'


@dataclass
class Sheet:
    id: int
    title: str
    row_count: int
    column_count: int
    frozen_row_count: Optional[int]
    frozen_column_count: Optional[int]
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
            frozen_row_count=grid_props.get('frozenRowCount'),
            frozen_column_count=grid_props.get('frozenColumnCount'),
        )

    def parse_data(self, sheet: dict):
        row_data = sheet['data'][0]['rowData']

        # if frozen row is not set (== 0), default to head=0, data=1
        head_row = (self.frozen_row_count - 1) if self.frozen_row_count else 0
        data_row = self.frozen_row_count if self.frozen_row_count else 1

        self.columns = [
            col.get('formattedValue', '')
            for col in row_data[head_row]['values']
        ]

        col_count = len(self.columns)
        offset = self.frozen_row_count if self.frozen_row_count else 0
        for num, row in enumerate(row_data[data_row:], 1):
            row_obj = SheetRow.parse(row['values'], num + offset, fill=col_count)
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
                    effectiveFormat: {
                        textFormat: {
                            strikethrough: boolean
                        }
                    }
                    formattedValue?: string
                    hyperlink?: string
                    textFormatRuns?: Array<{
                        format: {
                            link?: {
                                uri: string
                            }
                        }
                    }>
                    note?: string
                }>
            }>
        }>
        properties: {
            sheetId: number
            title: string
            index: number
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
