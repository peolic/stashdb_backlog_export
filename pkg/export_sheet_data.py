# coding: utf-8
import json
import re
from pathlib import Path
from typing import List, NamedTuple, Optional, Union

# DEPENDENCIES
import bs4        # pip install beautifulsoup4
import requests   # pip install requests

from .models import (
    DuplicatePerformersItem,
    PerformersToSplitUpItem,
    SceneFingerprintsDict,
    SceneFingerprintsItem,
)
from .utils import is_uuid


class _DataExtractor:

    class BaseRows(NamedTuple):
        head: int
        data: int

    class CheckboxNotFound(Exception):
        ...

    def __init__(self, doc_id: str, gid: str, reuse_soup: Optional[bs4.BeautifulSoup] = None):
        if reuse_soup is not None:
            self.soup = reuse_soup
        else:
            resp = requests.get(
                url=f'https://docs.google.com/spreadsheets/d/{doc_id}/htmlview',
                params={'gid': gid},
            )
            resp.raise_for_status()

            self.soup = bs4.BeautifulSoup(resp.text, 'html.parser')

        _sheet: Optional[bs4.Tag] = self.soup.select_one(f'div[id="{gid}"]')
        if not _sheet:
            raise Exception('ERROR: Sheet not found')

        self.sheet = _sheet

        self._all_rows: bs4.ResultSet = self.sheet.select('tbody > tr')

        self._base_rows = self._get_base_rows()

        self.data = []

    def _get_base_rows(self) -> BaseRows:
        # <th style="height:3px;" class="freezebar-cell freezebar-horizontal-handle">
        frozen_row_handle: Optional[bs4.Tag] = self.sheet.select_one('.freezebar-horizontal-handle')
        if not frozen_row_handle:
            raise Exception('ERROR: Frozen row handler not found')

        # <tr>
        frozen_row: Optional[bs4.Tag] = frozen_row_handle.parent
        if not frozen_row:
            raise Exception('ERROR: Frozen row not found')

        row_num = self._all_rows.index(frozen_row)
        # if frozen row is not set (== 0), default to head=0, data=1
        return self.BaseRows(
            head = (row_num - 1) if row_num else 0,
            data = (row_num + 1) if row_num else 1,
        )

    def get_column_index(self, name: str, text: Union[str, re.Pattern, None]) -> int:
        header_cell: Optional[bs4.Tag] = self.header_row.find(name, text=text)
        # indices start at 1, we need 0
        return -1 + self.header_row.index(header_cell)

    def get_all_column_indices(self, name: str, text: Union[str, re.Pattern, None]) -> List[int]:
        header_cells: List[bs4.Tag] = self.header_row.find_all(name, text=text)
        # indices start at 1, we need 0
        return [-1 + self.header_row.index(c) for c in header_cells]

    @property
    def header_row(self) -> bs4.Tag:
        return self._all_rows[self._base_rows.head]

    @property
    def data_rows(self) -> List[bs4.Tag]:
        return self._all_rows[self._base_rows.data:]

    @staticmethod
    def get_row_num(row: bs4.Tag) -> int:
        gutter: Optional[bs4.Tag] = row.select_one('th')
        if not gutter:
            raise Exception('Failed to get row number')
        return int(gutter.text)

    def _is_row_done(self, row: bs4.Tag, which: int = 1) -> bool:
        checkboxes = row.select('td use[href$="CheckboxId"]') or row.select('td use[xlink\\:href$="CheckboxId"]')
        if not checkboxes:
            raise self.CheckboxNotFound('No checkboxes found!')

        try:
            checkbox: bs4.Tag = checkboxes[which - 1]
        except IndexError:
            es = 'es' if (count := len(checkboxes)) > 1 else ''
            raise self.CheckboxNotFound(f'Only {count} checkbox{es} found, cannot get checkbox #{which}!')

        try:
            href = checkbox.attrs['href']
        except KeyError:
            href = checkbox.attrs['xlink:href']

        return href == '#checkedCheckboxId'

    def sort(self):
        if sort_key := getattr(self, 'sort_key', None):
            self.data.sort(key=sort_key)

    def write(self, target: Path):
        self.sort()

        target.write_bytes(
            json.dumps(self.data, indent=2).encode('utf-8')
        )

    def __str__(self):
        return '\n'.join(json.dumps(item) for item in self.data)

    def __len__(self):
        return len(self.data)


class _BacklogExtractor(_DataExtractor):
    def __init__(self, gid: str, **kw):
        doc_id = '1eiOC-wbqbaK8Zp32hjF8YmaKql_aH-yeGLmvHP1oBKQ'
        super().__init__(doc_id=doc_id, gid=gid, **kw)


class PerformersToSplitUp(_BacklogExtractor):
    def __init__(self, skip_done: bool = True, **kw):
        """
        NOTE: PARTIAL EXTRACTOR

        Args:
            skip_done - Skip rows and/or cells that are marked as done.
        """
        self.skip_done = skip_done

        super().__init__(gid='1067038397', **kw)

        self.column_name = self.get_column_index('td', text='Performer')
        self.column_main_id = self.get_column_index('td', text=re.compile('Performer Stash ID'))

        self.data: List[PerformersToSplitUpItem] = []
        for row in self.data_rows:
            # already processed
            if self.skip_done and self._is_row_done(row):
                continue

            all_cells = row.select('td')
            name: str = all_cells[self.column_name].text.strip()
            main_id: str = all_cells[self.column_main_id].text.strip()

            # useless row
            if not main_id:
                continue

            if not is_uuid(main_id):
                continue

            item = PerformersToSplitUpItem(name=name, main_id=main_id)
            self.data.append(item)

    def sort_key(self, item: PerformersToSplitUpItem):
        # Performer name, ASC
        return item['name'].casefold()

    def __iter__(self):
        return iter(self.data)
