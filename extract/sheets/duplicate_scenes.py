# coding: utf-8
import re
from typing import List, NamedTuple

from ..base import BacklogBase
from ..classes import Sheet, SheetCell, SheetRow
from ..models import DuplicateScenesItem
from ..utils import is_uuid


class DuplicateScenes(BacklogBase):
    def __init__(self, sheet: Sheet):
        self.column_category = sheet.get_column_index(re.compile('Category'))
        self.column_studio   = sheet.get_column_index(re.compile('Studio'))
        self.column_main_id  = sheet.get_column_index(re.compile('Main ID'))
        self.column_user     = sheet.get_column_index(re.compile('Added by'))

        self.data = self._parse(sheet.rows)

    def _parse(self, rows: List[SheetRow]) -> List[DuplicateScenesItem]:
        data: List[DuplicateScenesItem] = []
        for row in rows:
            row = self._transform_row(row)

            # already processed
            if row.done:
                continue
            # useless row
            if not row.item['main_id'] or not row.item['duplicates']:
                continue

            data.append(row.item)

        return data

    class RowResult(NamedTuple):
        num: int
        done: bool
        item: DuplicateScenesItem

    def _transform_row(self, row: SheetRow) -> RowResult:
        done = row.is_done()

        category: str = row.cells[self.column_category].value.strip()
        studio: str = row.cells[self.column_studio].value.strip()
        main_id: str = row.cells[self.column_main_id].value.strip()
        duplicates: List[str] = self._get_duplicate_scene_ids(row.cells[self.column_main_id + 1:], row.num)
        user: str = row.cells[self.column_user].value.strip()

        if main_id and not is_uuid(main_id):
            print(f"Row {row.num:<4} | WARNING: Invalid main scene UUID: '{main_id}'")
            main_id = None  # type: ignore

        item: DuplicateScenesItem = { 'studio': studio, 'main_id': main_id, 'duplicates': duplicates }

        if category and category != 'Exact duplicate':
            item['category'] = category

        if user:
            item['user'] = user

        return self.RowResult(row.num, done, item)

    def _get_duplicate_scene_ids(self, cells: List[SheetCell], row_num: int) -> List[str]:
        results: List[str] = []

        for cell in cells:
            scene_id: str = cell.value.strip()

            # skip empty
            if not scene_id:
                continue

            # skip anything else
            if not is_uuid(scene_id):
                continue

            # skip completed
            if cell.done:
                continue
                print(f'Row {row_num:<4} | skipped completed {scene_id}')

            if scene_id in results:
                print(f'Row {row_num:<4} | WARNING: Skipping duplicate scene ID: {scene_id}')
                continue

            results.append(scene_id)

        return results

    def __iter__(self):
        return iter(self.data)
