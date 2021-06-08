# coding: utf-8
import json
import re
from pathlib import Path
from typing import Dict, List, Literal, NamedTuple, Optional, Set, Tuple, Union

# DEPENDENCIES
import bs4        # pip install beautifulsoup4
import cssutils   # pip install cssutils
import requests   # pip install requests

from .models import (
    AnyPerformerEntry,
    DuplicatePerformersItem,
    DuplicateScenesItem,
    PerformerEntry,
    PerformerUpdateEntry,
    PerformersToSplitItem,
    SceneChangeFieldType,
    SceneChangeItem,
    SceneFixesDict,
    ScenePerformersItem,
)
from .utils import format_performer, format_studio, get_all_entries, get_cell_url, parse_stashdb_url

# Scene-Performers configuration
# ==============================
# Skip items completely if at least one if the performers' IDs could not be extracted
SKIP_NO_ID = True


def main_scene_performers():
    from .paths import path_scene_performers
    data = ScenePerformers()
    data.write(path_scene_performers)
    print(f'Success: {len(data)} scene entries')

def main_scenes_fixes():
    from .paths import path_scene_fixes
    data = SceneFixes()
    data.write(path_scene_fixes)
    print(f'Success: {len(data)} scene entries')

def main_duplicate_scenes():
    from .paths import path_duplicate_scenes
    data = DuplicateScenes()
    data.write(path_duplicate_scenes)
    print(f'Success: {len(data)} scene entries')

def main_duplicate_performers():
    from .paths import path_duplicate_performers
    data = DuplicatePerformers()
    data.write(path_duplicate_performers)
    print(f'Success: {len(data)} performer entries')


def first_performer_name(item: ScenePerformersItem, entry_type: Literal['update', 'append', 'remove']) -> str:
    try:
        return item[entry_type][0]['name']
    except IndexError:
        return ''
    except KeyError:
        if entry_type == 'update':
            return ''
        raise


def get_multiline_text(cell: bs4.Tag, **get_text_kwargs) -> str:
    for br in cell.find_all('br'):
        br.replace_with('\n')
    return cell.get_text(**get_text_kwargs)


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
            print('ERROR: Sheet not found')
            return

        self.sheet = _sheet

        self._all_rows: bs4.ResultSet = self.sheet.select('tbody > tr')

        self._base_rows = self._get_base_rows()
        if not self._base_rows:
            return

        self.data = []

    def _get_base_rows(self) -> Optional[BaseRows]:
        # <th style="height:3px;" class="freezebar-cell freezebar-horizontal-handle">
        frozen_row_handle: Optional[bs4.Tag] = self.sheet.select_one('.freezebar-horizontal-handle')
        if not frozen_row_handle:
            print('ERROR: Frozen row handler not found')
            return

        # <tr>
        frozen_row: Optional[bs4.Tag] = frozen_row_handle.parent
        if not frozen_row:
            print('ERROR: Frozen row not found')
            return

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

    def _is_row_done(self, row: bs4.Tag, which: int = 1) -> bool:
        checkboxes = row.select('td use[xlink\\:href$="CheckboxId"]')
        if not checkboxes:
            raise self.CheckboxNotFound('No checkboxes found!')

        try:
            checkbox: bs4.Tag = checkboxes[which - 1]
        except IndexError:
            es = 'es' if (count := len(checkboxes)) > 1 else ''
            raise self.CheckboxNotFound(f'Only {count} checkbox{es} found, cannot get checkbox #{which}!')

        return checkbox.attrs['xlink:href'] == '#checkedCheckboxId'

    def sort(self):
        if sort_key := getattr(self, 'sort_key', None):
            self.data.sort(key=sort_key)
            return

        raise NotImplementedError

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


class ScenePerformers(_BacklogExtractor, _DoneClassesMixin):
    def __init__(self, skip_done: bool = True, skip_no_id: bool = SKIP_NO_ID, **kw):
        """
        Args:
            skip_done   - Skip rows and/or cells that are marked as done.
            skip_no_id  - Skip items completely if at least one if the performers' IDs could not be extracted
        """
        self.skip_done = skip_done
        self.skip_no_id = skip_no_id

        super().__init__(gid='1397718590', **kw)

        self.column_studio   = self.get_column_index('td', text=re.compile('Studio'))
        self.column_scene_id = self.get_column_index('td', text=re.compile('Scene ID'))
        self.columns_remove  = self.get_all_column_indices('td', text=re.compile(r'\(\d+\) Remove/Replace'))
        self.columns_append  = self.get_all_column_indices('td', text=re.compile(r'\(\d+\) Add/With'))
        self.column_note     = self.get_column_index('td', text=re.compile('Edit Note'))

        self._parent_studio_pattern = re.compile(r'^(?P<studio>.+?) \[(?P<parent_studio>.+)\]$')

        self.data: List[ScenePerformersItem] = []
        for row in self.data_rows:
            row = self._transform_row(row)

            scene_id = row.item['scene_id']
            all_entries = get_all_entries(row.item)

            # already processed
            if self.skip_done and row.done:
                continue
            # empty row
            if not scene_id:
                continue
            # no changes
            if len(all_entries) == 0:
                print(f'Row {row.num:<4} | WARNING: Skipped due to no changes.')
                continue

            by_status: Dict[Optional[str], List[AnyPerformerEntry]] = {}
            for entry in all_entries:
                status = entry.get('status')
                target = by_status.setdefault(status, [])
                target.append(entry)

            # skip entries tagged with [merge] as they are marked to be merged into the paired performer
            if self.skip_no_id and by_status.get('merge'):
                formatted_merge_tagged = [format_performer('', i, False) for i in by_status['merge']]
                print(
                    f'Row {row.num:<4} | Skipped due to [merge]-tagged performers: '
                    + ' , '.join(formatted_merge_tagged)
                )
                continue
            # skip entries tagged with [edit] as they are marked to be edited
            #   and given the information of one of the to-append performers
            if self.skip_no_id and by_status.get('edit'):
                formatted_edit_tagged = [format_performer('', i, False) for i in by_status['edit']]
                print(
                    f'Row {row.num:<4} | Skipped due to [edit]-tagged performers: '
                    + ' , '.join(formatted_edit_tagged)
                )
                continue
            # skip entries tagged with [new] as they are marked to be created
            if self.skip_no_id and by_status.get('new'):
                formatted_new_tagged = [format_performer('', i, False) for i in by_status['new']]
                print(
                    f'Row {row.num:<4} | Skipped due to [new]-tagged performers: '
                    + ' , '.join(formatted_new_tagged)
                )
                continue
            # If this item has any performers that do not have a StashDB ID,
            #   skip the whole item for now, to avoid unwanted deletions.
            if self.skip_no_id and (no_id := [i for i in all_entries if not i['id']]):
                formatted_no_id = [format_performer('', i, False) for i in no_id]
                print(
                    f'Row {row.num:<4} | WARNING: Skipped due to missing performer IDs: '
                    + ' , '.join(formatted_no_id)
                )
                continue

            self.data.append(row.item)

    def _is_row_done(self, row: bs4.Tag) -> bool:
        """Override base class method because the first column is sometimes being used for 'submitted' status."""
        try:
            return super()._is_row_done(row, 2)
        except self.CheckboxNotFound:
            return super()._is_row_done(row)

    class RowResult(NamedTuple):
        num: int
        done: bool
        item: ScenePerformersItem

    def _transform_row(self, row: bs4.Tag) -> RowResult:
        done = self._is_row_done(row)
        row_num = int(row.select_one('th').text)

        all_cells = row.select('td')
        remove_cells: List[bs4.Tag] = [c for i, c in enumerate(all_cells) if i in self.columns_remove]
        append_cells: List[bs4.Tag] = [c for i, c in enumerate(all_cells) if i in self.columns_append]

        studio: str = all_cells[self.column_studio].text.strip()
        scene_id: str = all_cells[self.column_scene_id].text.strip()
        remove = self._get_change_entries(remove_cells, row_num)
        append = self._get_change_entries(append_cells, row_num)
        update = self._find_updates(remove, append, row_num)
        note   = get_multiline_text(all_cells[self.column_note]).strip()

        studio_info = {'studio': studio}
        if studio and (parent_studio_match := self._parent_studio_pattern.fullmatch(studio)):
            studio_info.update(parent_studio_match.groupdict())

        item = ScenePerformersItem(
            **studio_info,
            scene_id=scene_id,
            remove=remove,
            append=append,
        )

        if update:
            item['update'] = update

        if note:
            item['comment'] = note

        return self.RowResult(row_num, done, item)

    def _get_change_entries(self, cells: List[bs4.Tag], row_num: int):
        results: List[PerformerEntry] = []

        for cell in cells:
            entry, raw_name = self._get_change_entry(cell, row_num)

            if not entry:
                continue
                print(f'skipped empty/comment/completed/invalid {raw_name}')

            if entry in results:
                print(f'Row {row_num:<4} | WARNING: Skipping duplicate performer: {raw_name}')
                continue

            results.append(entry)

        return results

    def _get_change_entry(self, cell: bs4.Tag, row_num: int) -> Tuple[Optional[PerformerEntry], str]:
        raw_name: str = cell.text.strip()

        # skip empty
        if not raw_name or raw_name.startswith('>>>>>'):
            return None, raw_name

        # skip comments/completed
        if raw_name.startswith(('#', '[v]')):
            return None, raw_name

        # skip completed (legacy)
        if self.skip_done and self.is_cell_done(cell):
            return None, raw_name
            print(f'skipped completed {raw_name}')

        match = re.fullmatch(
            r'(?:\[(?P<status>[a-z]+?)\] )?(?P<name>.+?)(?: \[(?P<dsmbg>.+?)\])?(?: \(as (?P<as>.+)\))?',
            raw_name,
            re.I
        )

        if match:
            status = match.group('status')
            name = match.group('name')
            appearance = match.group('as')
            dsmbg = match.group('dsmbg')
        else:
            print(f'WARNING: Failed to parse name {raw_name}')
            status = None
            name = raw_name.strip()
            appearance = None
            dsmbg = None

        # Extract performer ID from url
        url = get_cell_url(cell)

        if not url:
            if status != 'new':
                print(f'Row {row_num:<4} | WARNING: Missing performer ID: {raw_name}')
            p_id = None

        else:
            obj, uuid = parse_stashdb_url(url)

            if obj == 'performers' and uuid:
                p_id = uuid

            elif obj is None or uuid is None:
                # if not self.skip_no_id:
                #     print(f"Row {row_num:<4} | WARNING: Failed to extract performer ID for: {raw_name}")
                p_id = None

            else:
                p_id = None
                # if obj == 'edits':
                #     if not self.skip_no_id:
                #         print(f"Row {row_num:<4} | WARNING: Edit ID found for: {raw_name}")
                # else:
                if obj != 'edits':
                    print(f"Row {row_num:<4} | WARNING: Failed to extract performer ID for: {raw_name}")

        entry = PerformerEntry(id=p_id, name=name, appearance=appearance)
        if dsmbg:
            entry['disambiguation'] = dsmbg
        if status:
            entry['status'] = status
        return entry, raw_name

    def _find_updates(self, remove: List[PerformerEntry], append: List[PerformerEntry], row_num: int):
        """
        Determine performer appearance update entries from remove & append entries.

        Mutates `remove` & `append` when an update entry is found.
        """
        updates: List[PerformerUpdateEntry] = []

        remove_ids = [i['id'] for i in remove]
        append_ids = [i['id'] for i in append]
        update_ids = [i for i in append_ids if i in remove_ids]

        for pid in update_ids:
            if pid is None:
                continue

            r_item = remove[remove_ids.index(pid)]
            a_item = append[append_ids.index(pid)]

            # This is either not an update, or the one of IDs is incorrect,
            #   unless this is the aftermath of an edited performer.
            if r_item['name'] != a_item['name'] or r_item['appearance'] == a_item['appearance']:
                if r_item.get('status') == 'edit':
                    continue

                print(f"Row {row_num:<4} | WARNING: Unexpected name/ID:"
                      f"\n  {format_performer('-', r_item)}"
                      f"\n  {format_performer('-', a_item)}")
                continue

            u_item = PerformerUpdateEntry(
                id=pid,
                name=a_item['name'],
                appearance=a_item['appearance'],
                old_appearance=r_item['appearance'],
            )
            if 'disambiguation' in a_item:
                u_item['disambiguation'] = a_item['disambiguation']
            if 'status' in a_item:
                u_item['status'] = a_item['status']

            updates.append(u_item)

        # Remove the items from remove & append
        for u_item in updates:
            remove.remove(next(r for r in remove if r['id'] == u_item['id']))
            append.remove(next(a for a in append if a['id'] == u_item['id']))

        return updates

    def sort_key(self, item: ScenePerformersItem):
        return (
            # Studio name, ASC
            (format_studio(item) or '').casefold(),
            # First to-update performer name, ASC
            first_performer_name(item, 'update').casefold(),
            # First to-append performer name, ASC
            first_performer_name(item, 'append').casefold(),
            # First to-remove performer name, ASC
            first_performer_name(item, 'remove').casefold(),
        )

    def __iter__(self):
        return iter(self.data)


class SceneFixes(_BacklogExtractor):
    def __init__(self, skip_done: bool = True, skip_manual: bool = True, **kw):
        """
        Args:
            skip_done   - Skip rows that are marked as done.
            skip_manual - Skip rows that must be applied manually because they
                            don't provide a new data value for the field.
        """
        self.skip_done = skip_done
        self.skip_no_new_data = skip_manual

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
            # no new data
            if self.skip_no_new_data and not row.change['new_data']:
                continue

            self.data.setdefault(row.scene_id, []).append(row.change)

    class RowResult(NamedTuple):
        num: int
        done: bool
        scene_id: str
        change: Optional[SceneChangeItem]

    def _transform_row(self, row: bs4.Tag) -> RowResult:
        done = self._is_row_done(row)
        row_num = int(row.select_one('th').text)

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
            try:
                parts = value.split(':')
            except AttributeError:
                raise ValueError

            parts[0:0] = ('0',) * (3 - len(parts))
            (hours, minutes, seconds) = [int(i) for i in parts]
            return str(hours * 3600 + minutes * 60 + seconds)

        return value

    def __iter__(self):
        return iter(self.data.items())


class DuplicateScenes(_BacklogExtractor, _DoneClassesMixin):
    def __init__(self, **kw):
        super().__init__(gid='1879471751', **kw)

        self.column_studio  = self.get_column_index('td', text=re.compile('Studio'))
        self.column_main_id = self.get_column_index('td', text=re.compile('Main ID'))

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
        done: bool
        item: DuplicateScenesItem

    def _transform_row(self, row: bs4.Tag) -> RowResult:
        done = self._is_row_done(row)

        all_cells = row.select('td')
        studio: str = all_cells[self.column_studio].text.strip()
        main_id: str = all_cells[self.column_main_id].text.strip()
        duplicates: List[str] = self._get_duplicate_scene_ids(all_cells[self.column_main_id:])

        return self.RowResult(done, { 'studio': studio, 'main_id': main_id, 'duplicates': duplicates })

    def _get_duplicate_scene_ids(self, cells: List[bs4.Tag]) -> List[str]:
        results = []

        for cell in cells:
            scene_id: str = cell.text.strip()

            # skip empty
            if not scene_id:
                continue

            # skip anything else
            match = re.fullmatch(r'[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}', scene_id)
            if match is None:
                continue

            # skip completed
            if self.is_cell_done(cell):
                continue
                print(f'skipped completed {name}')

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
        row_num = int(row.select_one('th').text)

        all_cells = row.select('td')

        name: str = all_cells[self.column_name].text.strip()
        main_id: str = all_cells[self.column_main_id].text.strip()
        duplicate_ids: List[str] = self._get_duplicate_performer_ids(all_cells[self.column_main_id:], row_num)

        return self.RowResult(row_num, done, { 'name': name, 'main_id': main_id, 'duplicates': duplicate_ids })

    def _get_duplicate_performer_ids(self, cells: List[bs4.Tag], row_num: int):
        results: List[str] = []

        for cell in cells:
            p_id: str = cell.text.strip()

            # skip empty
            if not p_id:
                continue

            # skip anything else
            match = re.fullmatch(r'[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}', p_id)
            if match is None:
                continue

            # skip completed
            if self.is_cell_done(cell):
                continue
                print(f'skipped completed {p_id}')

            if p_id in results:
                print(f'Row {row_num:<4} | WARNING: Skipping duplicate performer ID: {p_id}')
                continue

            results.append(p_id)

        return results

    def __iter__(self):
        return iter(self.data)


class PerformerToSplitUp(_BacklogExtractor):
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

        self.data: List[PerformersToSplitItem] = []
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

            if match := re.fullmatch(r'[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}', main_id):
                item = PerformersToSplitItem(name=name, main_id=match.group(0))
                self.data.append(item)

    def sort_key(self, item: PerformersToSplitItem):
        # Performer name, ASC
        return item['name'].casefold()

    def __iter__(self):
        return iter(self.data)
