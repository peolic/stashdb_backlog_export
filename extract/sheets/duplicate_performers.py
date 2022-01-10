# coding: utf-8
import re
from typing import List, NamedTuple

from ..base import BacklogBase
from ..classes import Sheet, SheetCell, SheetRow
from ..models import DuplicatePerformersItem
from ..utils import is_uuid


class DuplicatePerformers(BacklogBase):
    def __init__(self, sheet: Sheet, skip_done: bool):
        self.skip_done = skip_done

        self.column_name    = sheet.get_column_index(re.compile('Performer'))
        self.column_main_id = sheet.get_column_index(re.compile('Main ID'))
        self.column_user    = sheet.get_column_index(re.compile('Added by'))

        self.data = self._parse(sheet.rows)

    def _parse(self, rows: List[SheetRow]) -> List[DuplicatePerformersItem]:
        data: List[DuplicatePerformersItem] = []
        for row in rows:
            row = self._transform_row(row)

            # already processed
            if self.skip_done and row.done:
                continue
            # empty row
            if not row.item['main_id']:
                continue
            # no duplicates listed
            if not row.item['duplicates']:
                continue

            data.append(row.item)

        return data

    class RowResult(NamedTuple):
        num: int
        done: bool
        item: DuplicatePerformersItem

    def _transform_row(self, row: SheetRow) -> RowResult:
        done = row.is_done()

        cell_name = row.cells[self.column_name]
        cells_duplicates = row.cells[self.column_main_id + 1:]

        notes = list(filter(str.strip, cell_name.note.split('\n')))

        name: str = cell_name.value.strip()
        main_id: str = row.cells[self.column_main_id].value.strip()
        duplicate_ids = self._get_duplicate_performer_ids(cells_duplicates, notes, row.num)
        notes = list(dict.fromkeys(filter(None, notes)))
        user: str = row.cells[self.column_user].value.strip()

        if main_id and not is_uuid(main_id):
            print(f"Row {row.num:<4} | WARNING: Invalid main performer UUID: '{main_id}'")
            main_id = None  # type: ignore

        item = DuplicatePerformersItem(
            name=name,
            main_id=main_id,
            duplicates=duplicate_ids,
        )

        if notes:
            item['notes'] = notes

        if user:
            item['user'] = user

        return self.RowResult(row.num, done, item)

    def _get_duplicate_performer_ids(self, cells: List[SheetCell], notes: List[str], row_num: int):
        results: List[str] = []

        for cell in cells:
            p_id: str = cell.value.strip()

            # skip empty
            if not p_id:
                continue

            # skip anything else, but add it as notes
            if not is_uuid(p_id):
                notes.append(cell.first_link or p_id)
                continue

            # skip completed
            if cell.done:
                continue
                print(f'Row {row_num:<4} | skipped completed {p_id}')

            if p_id in results:
                print(f'Row {row_num:<4} | WARNING: Skipping duplicate performer ID: {p_id}')
                continue

            results.append(p_id)

        return results

    def __iter__(self):
        return iter(self.data)
