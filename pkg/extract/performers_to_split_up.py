# coding: utf-8
import re
from typing import List

from ..models import PerformersToSplitUpItem
from ..utils import is_uuid
from .base import BacklogBase
from .classes import Sheet, SheetRow


class PerformersToSplitUp(BacklogBase):
    def __init__(self, sheet: Sheet, skip_done: bool):
        self.skip_done = skip_done

        self.column_name = sheet.get_column_index('Performer')
        self.column_main_id = sheet.get_column_index(re.compile('Performer Stash ID'))

        self.data = self._parse(sheet.rows)

    def _parse(self, rows: List[SheetRow]) -> List[PerformersToSplitUpItem]:
        data: List[PerformersToSplitUpItem] = []
        for row in rows:
            # already processed
            if self.skip_done and row.is_done():
                continue

            name: str = row.cells[self.column_name].value.strip()
            main_id: str = row.cells[self.column_main_id].value.strip()

            # useless row
            if not main_id:
                continue

            if not is_uuid(main_id):
                continue

            item = PerformersToSplitUpItem(name=name, main_id=main_id)
            data.append(item)

        return data

    def sort_key(self, item: PerformersToSplitUpItem):
        # Performer name, ASC
        return item['name'].casefold()

    def __iter__(self):
        return iter(self.data)
