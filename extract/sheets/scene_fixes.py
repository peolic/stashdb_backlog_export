# coding: utf-8
import re
from typing import Dict, List, NamedTuple, Optional

from ..base import BacklogBase
from ..classes import Sheet, SheetRow
from ..logger import LoggerMixin
from ..models import SceneChangeFieldType, SceneChangeItem, SceneFixesDict
from ..utils import is_uuid, parse_duration


class SceneFixes(BacklogBase, LoggerMixin):
    def __init__(self, sheet: Sheet, skip_done: bool):
        LoggerMixin.__init__(self, __name__, 'scene')
        self.skip_done = skip_done

        self.column_scene_id   = sheet.get_column_index(re.compile('Scene ID'))
        self.column_field      = sheet.get_column_index(re.compile('Field'))
        self.column_new_data   = sheet.get_column_index(re.compile('New Data'))
        self.column_correction = sheet.get_column_index(re.compile('Correction'))
        self.column_user       = sheet.get_column_index(re.compile('Added by'))

        self.data = self._parse(sheet.rows)

    def _parse(self, rows: List[SheetRow]) -> SceneFixesDict:
        data: SceneFixesDict = {}
        last_seen: Dict[str, int] = {}

        for row in rows:
            row = self._transform_row(row)

            # already processed
            if self.skip_done and row.done:
                continue

            last_row = last_seen.get(row.scene_id, None)
            if last_row and row.num > (last_row + 1):
                self.log('warning', f'Ungrouped entries for scene ID {row.scene_id!r} last seen row {last_row}',
                         row.num, uuid=row.scene_id)
            else:
                last_seen[row.scene_id] = row.num

            # empty row or error
            if not row.scene_id or not row.change:
                continue

            # invalid scene id
            if not is_uuid(row.scene_id):
                if row.scene_id.casefold().startswith('multiple'):
                    continue
                self.log('warning', f'Skipped due to invalid scene ID: {row.scene_id}', row.num)
                continue

            data.setdefault(row.scene_id, []).append(row.change)

        return data

    class RowResult(NamedTuple):
        num: int
        done: bool
        scene_id: str
        change: Optional[SceneChangeItem]

    def _transform_row(self, row: SheetRow) -> RowResult:
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
            self.log('error', f'Field is empty.', row.num, uuid=scene_id)
            return self.RowResult(row.num, done, scene_id, None)

        if field in ('Overall',):
            self.log('', f'Skipping non-applicable field {field!r}.', row.num)
            return self.RowResult(row.num, done, scene_id, None)

        try:
            normalized_field = self._normalize_field(field)
        except ValueError:
            self.log('error', f'Field {field!r} is invalid.', row.num, uuid=scene_id)
            return self.RowResult(row.num, done, scene_id, None)

        try:
            processed_new_data = self._transform_new_data(normalized_field, new_data)
        except SceneFixes.ValueWarning:
            processed_new_data = None
            self.log('', f'Value {new_data!r} for field {field!r} replaced with: {processed_new_data!r}.',
                     row.num, uuid=scene_id)
        except ValueError:
            self.log('error', f'Value {new_data!r} for field {field!r} is invalid.', row.num, uuid=scene_id)
            return self.RowResult(row.num, done, scene_id, None)

        change = SceneChangeItem(
            field=normalized_field,
            new_data=processed_new_data,
            correction=correction,
        )

        if submitted:
            change['submitted'] = submitted

        if done:
            change['done'] = done

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
        if field == 'Studio Code':
            return 'code'
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
            if duration := parse_duration(value):
                return str(duration)
            raise ValueError

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
