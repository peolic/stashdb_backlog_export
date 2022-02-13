# coding: utf-8
import re
from typing import Dict, List

from ..base import BacklogBase
from ..classes import Sheet, SheetRow
from ..models import PerformerURLsDict, PerformerURLItem
from ..utils import is_uuid


class PerformerURLs(BacklogBase):
    def __init__(self, sheet: Sheet, skip_done: bool):
        self.skip_done = skip_done

        self.column_name = sheet.get_column_index('name')
        self.column_p_id = sheet.get_column_index('id')
        self.column_url  = sheet.get_column_index('url')
        # self.column_user = sheet.get_column_index('user')

        self.data = self._parse(sheet.rows)

    def _parse(self, rows: List[SheetRow]) -> PerformerURLsDict:
        data: PerformerURLsDict = {}
        last_seen: Dict[str, int] = {}

        for row in rows:
            # already processed
            if self.skip_done and row.is_done():
                continue

            name = row.cells[self.column_name].value.strip()
            p_id = row.cells[self.column_p_id].value.strip()
            url  = row.cells[self.column_url].value.strip()
            # user = row.cells[self.column_user].value.strip()

            # useless row
            if not (p_id and url and name):
                continue

            last_row = last_seen.get(p_id, None)
            if last_row and row.num > (last_row + 1):
                print(f'Row {row.num:<4} | WARNING: Ungrouped entries for scene ID {p_id!r} last seen row {last_row}')
            else:
                last_seen[p_id] = row.num

            if not url:
                print(f'Row {row.num:<4} | WARNING: Skipped due to empty URL')
                continue

            if not is_uuid(p_id):
                print(f'Row {row.num:<4} | WARNING: Skipped due to invalid performer ID')
                continue

            item = PerformerURLItem(url=url, name=name)

            data.setdefault(p_id, []).append(item)

        return data

    def __iter__(self):
        return iter(self.data.items())
