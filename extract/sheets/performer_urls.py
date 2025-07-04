# coding: utf-8
import re
from typing import Dict, List

from ..base import BacklogBase
from ..classes import Sheet, SheetRow
from ..logger import LoggerMixin
from ..models import PerformerURLsDict, PerformerURLItem
from ..utils import is_uuid


class PerformerURLs(BacklogBase, LoggerMixin):
    def __init__(self, sheet: Sheet, skip_done: bool):
        LoggerMixin.__init__(self, __name__, 'performer')
        self.skip_done = skip_done

        self.column_name = sheet.get_column_index('name')
        self.column_p_id = sheet.get_column_index('id')
        self.column_url  = sheet.get_column_index('url')
        # self.column_user = sheet.get_column_index('user')
        self.column_text = sheet.get_column_index('text')

        self.data = self._parse(sheet.rows)

    def _parse(self, rows: List[SheetRow]) -> PerformerURLsDict:
        data: PerformerURLsDict = {}
        last_seen: Dict[str, int] = {}

        for row in rows:
            try:
                submitted = row.is_done(1)
                done = row.is_done(2)
            except row.CheckboxNotFound:
                submitted = False
                try:
                    done = row.is_done()
                except row.CheckboxNotFound as error:
                    self.log('error', str(error), error.row_num)
                    done = False

            name = row.cells[self.column_name].value.strip()
            p_id = row.cells[self.column_p_id].value.strip()
            url  = row.cells[self.column_url].value.strip()
            # user = row.cells[self.column_user].value.strip()
            text = row.cells[self.column_text].value.strip()

            # useless row
            if not (p_id and url and name):
                continue

            # already processed
            if self.skip_done and done:
                if last_seen.get(p_id, None):
                    last_seen[p_id] = row.num
                continue

            last_row = last_seen.get(p_id, None)
            if last_row and row.num > (last_row + 1):
                self.log('warning', f'Ungrouped entries for performer ID {p_id!r} last seen row {last_row}',
                         row.num, uuid=p_id)
            else:
                last_seen[p_id] = row.num

            if not url:
                self.log('warning', f'Skipped due to empty URL', row.num)
                continue

            if not is_uuid(p_id):
                self.log('warning', f'Skipped due to invalid performer ID', row.num)
                continue

            item = PerformerURLItem(url=url, name=name, text=text)

            if submitted:
                item['submitted'] = submitted

            data.setdefault(p_id, []).append(item)

        return data

    def __iter__(self):
        return iter(self.data.items())
