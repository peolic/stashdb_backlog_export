# coding: utf-8
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Union

import bs4
import cssutils
import requests

from ..classes import Sheet, SheetCell, SheetRow
from ...utils import get_cell_url, get_multiline_text


class HTMLInterface:

    def __init__(self, spreadsheet_id: str, sheet_ids: List[int]):
        print('fetching HTML spreadsheet...')
        resp = requests.get(f'https://docs.google.com/spreadsheets/d/{spreadsheet_id}/htmlview')
        resp.raise_for_status()

        soup = bs4.BeautifulSoup(resp.text, 'html.parser')

        self._sheets = {
            sheet_id: LegacySheet.parse(soup=soup, sheet_id=sheet_id)
            for sheet_id in sheet_ids
        }

    def get_sheet(self, sheet_id: int):
        return self._sheets[sheet_id]


@dataclass
class LegacySheetCell(SheetCell):
    link: Optional[str]

    @classmethod
    def parse(cls, cell: bs4.Tag, done: bool):
        value = get_multiline_text(cell)

        if checkbox := cell.select_one('use[href$="CheckboxId"], use[xlink\\:href$="CheckboxId"]'):
            try:
                href = checkbox.attrs['href']
            except KeyError:
                href = checkbox.attrs['xlink:href']

            value = str(href == '#checkedCheckboxId').upper()

        return cls(
            value=value,
            link=get_cell_url(cell),
            note='',
            done=done,
        )


@dataclass
class LegacySheetRow(SheetRow):
    cells: List[LegacySheetCell]

    @classmethod
    def parse(cls, row: bs4.Tag, done_classes: Set[str]):

        def is_done(cell: bs4.Tag):
            classes: Optional[List[str]] = cell.attrs.get('class')  # type: ignore
            if classes:
                return any(c in done_classes for c in classes)
            return False

        cells = [
            LegacySheetCell.parse(cell, is_done(cell))
            for cell in row.select('td')
        ]
        obj = cls(num=cls.get_row_num(row), cells=cells)
        return obj

    @staticmethod
    def get_row_num(row: bs4.Tag):
        gutter: Optional[bs4.Tag] = row.select_one('th')
        if not gutter:
            raise Exception('Failed to get row number')
        return int(gutter.text)

    class CheckboxNotFound(Exception):
        ...


@dataclass
class LegacySheet(Sheet):
    rows: List[LegacySheetRow] = field(default_factory=list, repr=False)

    @classmethod
    def parse(cls, soup: bs4.BeautifulSoup, sheet_id: int):
        sheet = soup.select_one(f'div[id="{sheet_id}"]')
        if not sheet:
            raise Exception('ERROR: Sheet not found')

        if title := soup.select_one(f'li[id="sheet-button-{sheet_id}"] > a'):
            title = title.get_text(strip=True)
        else:
            title = '<unknown>'

        self = cls(
            id=sheet_id,
            title=title,
            row_count=(-1),
            column_count=(-1),
            frozen_row_count=get_frozen_row_count(sheet),
            frozen_column_count=(-1),
        )

        all_rows = sheet.select('tbody > tr')

        # if frozen row is not set (== 0), default to head=0, data=1
        head_row = (self.frozen_row_count - 1) if self.frozen_row_count else 0
        data_row = (self.frozen_row_count + 1) if self.frozen_row_count else 1

        self.columns = [
            col.get_text()
            for col in all_rows[head_row].select('td')
        ]

        done_classes = get_done_classes(soup)

        for row in all_rows[data_row:]:
            row_obj = LegacySheetRow.parse(row, done_classes)
            self.rows.append(row_obj)

        return self

    def parse_data(self, *args, **kwargs):
        pass

    def get_column_index(self, text: Union[str, re.Pattern, None]) -> int:
        for idx, col in enumerate(self.columns):
            if isinstance(text, re.Pattern) and text.search(col):
                return idx
            if isinstance(text, str) and text in col:
                return idx

        return -1

    def get_all_column_indices(self, text: Union[str, re.Pattern, None]) -> List[int]:
        return [
            idx for idx, col in enumerate(self.columns)
            if isinstance(text, re.Pattern) and text.search(col)
            or isinstance(text, str) and text in col
        ]


def get_frozen_row_count(sheet: bs4.Tag) -> int:
    all_rows = sheet.select('tbody > tr')

    # <th style="height:3px;" class="freezebar-cell freezebar-horizontal-handle">
    frozen_row_handle = sheet.select_one('.freezebar-horizontal-handle')
    if not frozen_row_handle:
        raise Exception('ERROR: Frozen row handler not found')

    # <tr>
    frozen_row: Optional[bs4.Tag] = frozen_row_handle.parent
    if not frozen_row:
        raise Exception('ERROR: Frozen row not found')

    return all_rows.index(frozen_row)


def get_done_classes(soup: bs4.BeautifulSoup) -> Set[str]:
    """Find the class names that are strike/line-through (partially completed entries)."""
    classes: Set[str] = set()

    if not soup:
        print('WARNING: Unable to determine partially completed entries')
        return classes

    style: Optional[bs4.Tag] = soup.select_one('head > style')
    if style is None:
        print('WARNING: Unable to determine partially completed entries')
        return classes

    stylesheet = cssutils.parseString(style.decode_contents(), validate=False)

    for rule in stylesheet:
        if rule.type == rule.STYLE_RULE and rule.style.textDecoration == 'line-through':
            selector: str = rule.selectorText
            classes.update(c.lstrip('.') for c in selector.split(' ') if c.startswith('.s'))

    return classes
