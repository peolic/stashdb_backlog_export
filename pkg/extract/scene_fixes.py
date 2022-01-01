# coding: utf-8
import re
from typing import List, NamedTuple, Optional

from ..models import SceneChangeFieldType, SceneChangeItem, SceneFixesDict
from ..utils import is_uuid
from .base import BacklogBase
from .classes import Sheet, SheetRow


class SceneFixes(BacklogBase):
    def __init__(self, sheet: Sheet, skip_done: bool):
        self.skip_done = skip_done

        self.column_scene_id   = sheet.get_column_index(re.compile('Scene ID'))
        self.column_field      = sheet.get_column_index(re.compile('Field'))
        self.column_new_data   = sheet.get_column_index(re.compile('New Data'))
        self.column_correction = sheet.get_column_index(re.compile('Correction'))
        self.column_user       = sheet.get_column_index(re.compile('Added by'))

        self.data = self._parse(sheet.rows)

    def _parse(self, rows: List[SheetRow]) -> SceneFixesDict:
        data: SceneFixesDict = {}
        for row in rows:
            row = self._transform_row(row)

            # already processed
            if self.skip_done and row.done:
                continue
            # empty row or error
            if not row.scene_id or not row.change:
                continue
            # invalid scene id
            if not is_uuid(row.scene_id):
                continue

            data.setdefault(row.scene_id, []).append(row.change)

        return data

    class RowResult(NamedTuple):
        num: int
        done: bool
        scene_id: str
        change: Optional[SceneChangeItem]

    def _transform_row(self, row: SheetRow) -> RowResult:
        done = row.is_done()

        scene_id: str = row.cells[self.column_scene_id].value.strip()
        field: str = row.cells[self.column_field].value.strip()
        correction: Optional[str] = row.cells[self.column_correction].value.strip() or None
        user: str = row.cells[self.column_user].value.strip()

        new_data_cell = row.cells[self.column_new_data]
        new_data = new_data_cell.first_link
        if not new_data:
            new_data = new_data_cell.value.strip() or None

        if not scene_id or done:
            return self.RowResult(row.num, done, scene_id, None)

        if not field:
            print(f'Row {row.num:<4} | ERROR: Field is empty.')
            return self.RowResult(row.num, done, scene_id, None)

        if field in ('Overall',):
            print(f'Row {row.num:<4} | Skipping non-applicable field {field!r}.')
            return self.RowResult(row.num, done, scene_id, None)

        try:
            normalized_field = self._normalize_field(field)
        except ValueError:
            print(f'Row {row.num:<4} | ERROR: Field {field!r} is invalid.')
            return self.RowResult(row.num, done, scene_id, None)

        try:
            processed_new_data = self._transform_new_data(normalized_field, new_data)
        except SceneFixes.ValueWarning:
            processed_new_data = None
            print(f'Row {row.num:<4} | WARNING: '
                  f'Value {new_data!r} for field {field!r} replaced with: {processed_new_data!r}.')
        except ValueError:
            print(f'Row {row.num:<4} | ERROR: Value {new_data!r} for field {field!r} is invalid.')
            return self.RowResult(row.num, done, scene_id, None)

        change = SceneChangeItem(
            field=normalized_field,
            new_data=processed_new_data,
            correction=correction,
        )

        if user:
            change['user'] = user

        return self.RowResult(row.num, done, scene_id, change)

    @staticmethod
    def _normalize_field(field: str) -> SceneChangeFieldType:
        if field == 'Title':
            return 'title'
        if field == 'Description':
            return 'details'
        if field == 'Date':
            return 'date'
        if field == 'Studio ID':
            return 'studio_id'
        if field == 'Director':
            return 'director'
        if field == 'Duration':
            return 'duration'
        if field == 'Image':
            return 'image'
        if field == 'URL':
            return 'url'

        raise ValueError(f'Unsupported field: {field}')

    @staticmethod
    def _transform_new_data(field: SceneChangeFieldType, value: Optional[str]) -> Optional[str]:
        if field == 'duration':
            if not value:
                raise ValueError
            try:
                parts = value.split(':')
            except AttributeError:
                raise ValueError

            parts[0:0] = ('0',) * (3 - len(parts))
            (hours, minutes, seconds) = [int(i) for i in parts]
            return str(hours * 3600 + minutes * 60 + seconds)

        if field == 'studio_id':
            if value == 'missing':
                raise SceneFixes.ValueWarning
            if not (value and is_uuid(value)):
                raise ValueError

        return value

    def __iter__(self):
        return iter(self.data.items())

    class ValueWarning(Exception):
        ...
