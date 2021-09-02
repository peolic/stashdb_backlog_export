# coding: utf-8
import json
import re
from pathlib import Path
from typing import List, NamedTuple, Optional, Set, Union

# DEPENDENCIES
import bs4        # pip install beautifulsoup4
import cssutils   # pip install cssutils
import requests   # pip install requests

from .models import (
    DuplicatePerformersItem,
    DuplicateScenesItem,
    PerformersToSplitUpItem,
    SceneChangeFieldType,
    SceneChangeItem,
    SceneFingerprintsDict,
    SceneFingerprintsItem,
    SceneFixesDict,
)
from .utils import get_cell_url, get_multiline_text, is_uuid


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


class _DoneClassesMixin:

    def is_cell_done(self, cell: bs4.Tag) -> bool:
        if not hasattr(self, '_done_classes'):
            self._done_classes = self._get_done_classes()

        classes: Optional[List[str]] = cell.attrs.get('class')
        if classes:
            return any(c in self._done_classes for c in classes)
        return False

    def _get_done_classes(self):
        """Find the class names that are strike/line-through (partially completed entries)."""
        classes: Set[str] = set()

        soup: bs4.BeautifulSoup = getattr(self, 'soup')
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


class _BacklogExtractor(_DataExtractor):
    def __init__(self, gid: str, **kw):
        doc_id = '1eiOC-wbqbaK8Zp32hjF8YmaKql_aH-yeGLmvHP1oBKQ'
        super().__init__(doc_id=doc_id, gid=gid, **kw)


class SceneFixes(_BacklogExtractor):
    def __init__(self, skip_done: bool = True, **kw):
        """
        Args:
            skip_done   - Skip rows that are marked as done.
        """
        self.skip_done = skip_done

        super().__init__(gid='1419170166', **kw)

        self.column_scene_id   = self.get_column_index('td', text=re.compile('Scene ID'))
        self.column_field      = self.get_column_index('td', text=re.compile('Field'))
        self.column_new_data   = self.get_column_index('td', text=re.compile('New Data'))
        self.column_correction = self.get_column_index('td', text=re.compile('Correction'))

        self.data: SceneFixesDict = {}
        for row in self.data_rows:
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

            self.data.setdefault(row.scene_id, []).append(row.change)

    class RowResult(NamedTuple):
        num: int
        done: bool
        scene_id: str
        change: Optional[SceneChangeItem]

    def _transform_row(self, row: bs4.Tag) -> RowResult:
        done = self._is_row_done(row)
        row_num = self.get_row_num(row)

        all_cells = row.select('td')

        scene_id: str = all_cells[self.column_scene_id].text.strip()
        field: str = all_cells[self.column_field].text.strip()
        correction: Optional[str] = get_multiline_text(all_cells[self.column_correction]).strip() or None

        new_data_cell: bs4.Tag = all_cells[self.column_new_data]
        new_data = get_cell_url(new_data_cell)
        if not new_data:
            new_data: Optional[str] = get_multiline_text(new_data_cell).strip() or None

        if not scene_id:
            return self.RowResult(row_num, done, scene_id, None)

        if not field:
            print(f'Row {row_num:<4} | ERROR: Field is empty.')
            return self.RowResult(row_num, done, scene_id, None)

        if field in ('Overall',):
            print(f'Row {row_num:<4} | Skipping non-applicable field {field!r}.')
            return self.RowResult(row_num, done, scene_id, None)

        try:
            normalized_field = self._normalize_field(field)
        except ValueError:
            print(f'Row {row_num:<4} | ERROR: Field {field!r} is invalid.')
            return self.RowResult(row_num, done, scene_id, None)

        try:
            processed_new_data = self._transform_new_data(normalized_field, new_data)
        except SceneFixes.ValueWarning:
            processed_new_data = None
            print(f'Row {row_num:<4} | WARNING: '
                  f'Value {new_data!r} for field {field!r} replaced with: {processed_new_data!r}.')
        except ValueError:
            print(f'Row {row_num:<4} | ERROR: Value {new_data!r} for field {field!r} is invalid.')
            return self.RowResult(row_num, done, scene_id, None)

        change = SceneChangeItem(
            field=normalized_field,
            new_data=processed_new_data,
            correction=correction,
        )

        return self.RowResult(row_num, done, scene_id, change)

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


class DuplicateScenes(_BacklogExtractor, _DoneClassesMixin):
    def __init__(self, **kw):
        super().__init__(gid='1879471751', **kw)

        self.column_category = self.get_column_index('td', text=re.compile('Category'))
        self.column_studio   = self.get_column_index('td', text=re.compile('Studio'))
        self.column_main_id  = self.get_column_index('td', text=re.compile('Main ID'))

        self.data: List[DuplicateScenesItem] = []
        for row in self.data_rows:
            row = self._transform_row(row)

            # already processed
            if row.done:
                continue
            # useless row
            if not row.item['main_id'] or not row.item['duplicates']:
                continue

            self.data.append(row.item)

    class RowResult(NamedTuple):
        num: int
        done: bool
        item: DuplicateScenesItem

    def _transform_row(self, row: bs4.Tag) -> RowResult:
        done = self._is_row_done(row)
        row_num = self.get_row_num(row)

        all_cells = row.select('td')
        category: str = all_cells[self.column_category].text.strip()
        studio: str = all_cells[self.column_studio].text.strip()
        main_id: str = all_cells[self.column_main_id].text.strip()
        duplicates: List[str] = self._get_duplicate_scene_ids(all_cells[self.column_main_id + 1:], row_num)

        if main_id and not is_uuid(main_id):
            print(f"Row {row_num:<4} | WARNING: Invalid main scene UUID: '{main_id}'")
            main_id = None

        item: DuplicateScenesItem = { 'studio': studio, 'main_id': main_id, 'duplicates': duplicates }

        if category and category != 'Exact duplicate':
            item['category'] = category

        return self.RowResult(row_num, done, item)

    def _get_duplicate_scene_ids(self, cells: List[bs4.Tag], row_num: int) -> List[str]:
        results: List[str] = []

        for cell in cells:
            scene_id: str = cell.text.strip()

            # skip empty
            if not scene_id:
                continue

            # skip anything else
            if not is_uuid(scene_id):
                continue

            # skip completed
            if self.is_cell_done(cell):
                continue
                print(f'Row {row_num:<4} | skipped completed {scene_id}')

            if scene_id in results:
                print(f'Row {row_num:<4} | WARNING: Skipping duplicate scene ID: {scene_id}')
                continue

            results.append(scene_id)

        return results

    def __iter__(self):
        return iter(self.data)


class DuplicatePerformers(_BacklogExtractor, _DoneClassesMixin):
    def __init__(self, skip_done: bool = True, **kw):
        """
        Args:
            skip_done - Skip rows and/or cells that are marked as done.
        """
        self.skip_done = skip_done

        super().__init__(gid='0', **kw)

        self.column_name   = self.get_column_index('td', text=re.compile('Performer'))
        self.column_main_id = self.get_column_index('td', text=re.compile('Main ID'))

        self.data: List[DuplicatePerformersItem] = []
        for row in self.data_rows:
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

            self.data.append(row.item)

    class RowResult(NamedTuple):
        num: int
        done: bool
        item: DuplicatePerformersItem

    def _transform_row(self, row: bs4.Tag) -> RowResult:
        done = self._is_row_done(row)
        row_num = self.get_row_num(row)

        all_cells = row.select('td')

        name: str = all_cells[self.column_name].text.strip()
        main_id: str = all_cells[self.column_main_id].text.strip()
        duplicate_ids: List[str] = self._get_duplicate_performer_ids(all_cells[self.column_main_id + 1:], row_num)

        if main_id and not is_uuid(main_id):
            print(f"Row {row_num:<4} | WARNING: Invalid main performer UUID: '{main_id}'")
            main_id = None

        return self.RowResult(row_num, done, { 'name': name, 'main_id': main_id, 'duplicates': duplicate_ids })

    def _get_duplicate_performer_ids(self, cells: List[bs4.Tag], row_num: int):
        results: List[str] = []

        for cell in cells:
            p_id: str = cell.text.strip()

            # skip empty
            if not p_id:
                continue

            # skip anything else
            if not is_uuid(p_id):
                continue

            # skip completed
            if self.is_cell_done(cell):
                continue
                print(f'Row {row_num:<4} | skipped completed {p_id}')

            if p_id in results:
                print(f'Row {row_num:<4} | WARNING: Skipping duplicate performer ID: {p_id}')
                continue

            results.append(p_id)

        return results

    def __iter__(self):
        return iter(self.data)


class SceneFingerprints(_BacklogExtractor):
    def __init__(self, skip_done: bool = True, skip_no_correct_scene: bool = True, **kw):
        """
        Args:
            skip_done             - Skip rows and/or cells that are marked as done.
            skip_no_correct_scene - Skip rows that don't provide the correct scene's ID.
        """
        self.skip_done = skip_done
        self.skip_no_correct_scene = skip_no_correct_scene

        super().__init__(gid='357846927', **kw)

        self.column_scene_id = self.get_column_index('td', text=re.compile('Scene ID'))
        self.column_algorithm = self.get_column_index('td', text=re.compile('Algorithm'))
        self.column_fingerprint = self.get_column_index('td', text=re.compile('Fingerprint'))
        self.column_correct_scene_id = self.get_column_index('td', text=re.compile('Correct Scene ID'))

        self.data: SceneFingerprintsDict = {}
        for row in self.data_rows:
            row_num = self.get_row_num(row)

            # already processed
            if self.skip_done and self._is_row_done(row):
                continue

            all_cells = row.select('td')
            scene_id: str = all_cells[self.column_scene_id].text.strip()
            algorithm: str = all_cells[self.column_algorithm].text.strip()
            fp_hash: str = all_cells[self.column_fingerprint].text.strip()
            correct_scene_id: Optional[str] = all_cells[self.column_correct_scene_id].text.strip() or None

            # useless row
            if not (scene_id and algorithm and fp_hash):
                continue

            if self.skip_no_correct_scene and not correct_scene_id:
                print(f'Row {row_num:<4} | WARNING: Skipped due to missing correct scene ID')
                continue

            if algorithm not in ('phash', 'oshash', 'md5'):
                print(f'Row {row_num:<4} | WARNING: Skipped due to invalid algorithm')
                continue

            if (
                re.fullmatch(r'^[a-f0-9]+$', fp_hash) is None
                or algorithm in ('phash', 'oshash') and len(fp_hash) != 16
                or algorithm == 'md5' and len(fp_hash) != 32
            ):
                print(f'Row {row_num:<4} | WARNING: Skipped due to invalid hash')
                continue

            if not is_uuid(scene_id):
                print(f'Row {row_num:<4} | WARNING: Skipped due to invalid scene ID')
                continue

            if correct_scene_id and not is_uuid(correct_scene_id):
                print(f'Row {row_num:<4} | WARNING: Skipped due to invalid correct scene ID')
                continue

            item = SceneFingerprintsItem(
                algorithm=algorithm,
                hash=fp_hash,
                correct_scene_id=correct_scene_id,
            )
            self.data.setdefault(scene_id, []).append(item)

    def __iter__(self):
        return iter(self.data.items())


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
