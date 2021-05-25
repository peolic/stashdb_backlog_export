# coding: utf-8
import json
import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple, Union
from urllib.parse import parse_qsl, urlparse

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
    ScenePerformersItem,
)
from .utils import format_performer, get_all_entries

# Scene-Performers configuration
# ==============================
# Skip items completely if at least one if the performers' IDs could not be extracted
SKIP_NO_ID = True


def main_scene_performers():
    from .paths import path_scene_performers
    data = ScenePerformers()
    data.write(path_scene_performers)
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


class _DataExtractor:

    class BaseRows(NamedTuple):
        head: int
        data: int

    def __init__(self, gid: str, reuse_soup: Optional[bs4.BeautifulSoup] = None):
        if reuse_soup is not None:
            self.soup = reuse_soup
        else:
            resp = requests.get(
                url='https://docs.google.com/spreadsheets/d/1eiOC-wbqbaK8Zp32hjF8YmaKql_aH-yeGLmvHP1oBKQ/htmlview',
                params={'gid': gid},
            )
            resp.raise_for_status()

            self.soup = bs4.BeautifulSoup(resp.text, 'html.parser')

        # find the class names that are strike/line-through (partially completed entries)
        self.done_styles = self._get_done_classes()

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

    def _get_done_classes(self) -> Set[str]:
        style: Optional[bs4.Tag] = self.soup.select_one('head > style')
        if style is None:
            print('WARNING: Unable to determine partially completed entries')
            return set()

        stylesheet = cssutils.parseString(style.decode_contents(), validate=False)

        classes = set()
        for rule in stylesheet:
            if rule.type == rule.STYLE_RULE and rule.style.textDecoration == 'line-through':
                selector: str = rule.selectorText
                classes.update(c.lstrip('.') for c in selector.split(' ') if c.startswith('.s'))

        return classes

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

    def _is_row_done(self, row: bs4.Tag) -> bool:
        try:
            return row.select_one('td:first-of-type use').attrs['xlink:href'] == '#checkedCheckboxId'
        except (AttributeError, KeyError):
            return False

    def write(self, target: Path):
        target.write_bytes(
            json.dumps(self.data, indent=2).encode('utf-8')
        )

    def __str__(self):
        return '\n'.join(json.dumps(item) for item in self.data)

    def __iter__(self):
        for item in self.data:
            yield item

    def __len__(self):
        return len(self.data)


class ScenePerformers(_DataExtractor):
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

        self._parent_studio_pattern = re.compile(r'^(?P<studio>.+?) \[(?P<parent_studio>.+)\]$')
        self._note_prefix = '# [note] '

        self.data: List[ScenePerformersItem] = []
        for row in self.data_rows:
            row_num, done, item = self._transform_row(row)

            scene_id = item['scene_id']
            all_entries = get_all_entries(item)

            # already processed
            if self.skip_done and done:
                continue
            # empty row
            if not scene_id:
                continue
            # no changes
            if len(all_entries) == 0:
                print(f'Row {row_num:<4} | WARNING: Skipped due to no changes.')
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
                    f'Row {row_num:<4} | Skipped due to [merge]-tagged performers: '
                    + ' , '.join(formatted_merge_tagged)
                )
                continue
            # skip entries tagged with [edit] as they are marked to be edited
            #   and given the information of one of the to-append performers
            if self.skip_no_id and by_status.get('edit'):
                formatted_edit_tagged = [format_performer('', i, False) for i in by_status['edit']]
                print(
                    f'Row {row_num:<4} | Skipped due to [edit]-tagged performers: '
                    + ' , '.join(formatted_edit_tagged)
                )
                continue
            # skip entries tagged with [new] as they are marked to be created
            if self.skip_no_id and by_status.get('new'):
                formatted_new_tagged = [format_performer('', i, False) for i in by_status['new']]
                print(
                    f'Row {row_num:<4} | Skipped due to [new]-tagged performers: '
                    + ' , '.join(formatted_new_tagged)
                )
                continue
            # If this item has any performers that do not have a StashDB ID,
            #   skip the whole item for now, to avoid unwanted deletions.
            if self.skip_no_id and (no_id := [i for i in all_entries if not i['id']]):
                formatted_no_id = [format_performer('', i, False) for i in no_id]
                print(
                    f'Row {row_num:<4} | WARNING: Skipped due to missing performer IDs: '
                    + ' , '.join(formatted_no_id)
                )
                continue

            self.data.append(item)

    def _is_row_done(self, row: bs4.Tag) -> bool:
        """Override base class method because of first column being used for 'submitted' status."""
        cells = row.select('td use')
        if not cells:
            return False
        v_cell = cells[0] if len(cells) == 1 else cells[1]
        return v_cell.attrs['xlink:href'] == '#checkedCheckboxId'

    def _transform_row(self, row: bs4.Tag) -> Tuple[int, bool, ScenePerformersItem]:
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
        note   = self._get_edit_note(remove_cells + append_cells)

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

        return row_num, done, item

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
        if self.skip_done and any(c in self.done_styles for c in cell.attrs.get('class', [])):
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

        try:
            url: str = cell.select_one('a').attrs['href']

            url_p = urlparse(url)
            if url_p.hostname == 'www.google.com' and url_p.path == '/url':
                url = dict(parse_qsl(url_p.query))['q']
                url = urlparse(url)._replace(query=None, fragment=None).geturl()
        except (AttributeError, KeyError):
            if status != 'new':
                print(f'Row {row_num:<4} | WARNING: Missing performer ID: {raw_name}')
            p_id = None
        else:
            match = re.search(r'/([a-z]+)/([0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12})$', url)
            if match is None:
                # if not self.skip_no_id:
                #     print(f"Row {row_num:<4} | WARNING: Failed to extract performer ID for: {raw_name}")
                p_id = None
            else:
                obj = match.group(1)
                p_id = match.group(2)
                if obj != 'performers':
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
        update_ids = set(remove_ids).intersection(append_ids)

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

    def _get_edit_note(self, cells: List[bs4.Tag]) -> Optional[str]:
        notes = []

        for cell in cells:
            raw_name: str = cell.text.strip()
            if raw_name.startswith(self._note_prefix):
                notes.append(
                    raw_name[len(self._note_prefix):]
                )

        if not notes:
            return None

        return '\n'.join(notes)


class DuplicateScenes(_DataExtractor):
    def __init__(self, **kw):
        super().__init__(gid='1879471751', **kw)

        self.column_studio  = self.get_column_index('td', text=re.compile('Studio'))
        self.column_main_id = self.get_column_index('td', text=re.compile('Main ID'))

        self.data: List[DuplicateScenesItem] = []
        for row in self.data_rows:
            done, item = self._transform_row(row)

            # already processed
            if done:
                continue
            # useless row
            if not item['main_id'] or not item['duplicates']:
                continue

            self.data.append(item)

    def _transform_row(self, row: bs4.Tag) -> Tuple[bool, DuplicateScenesItem]:
        done = self._is_row_done(row)

        all_cells = row.select('td')
        studio: str = all_cells[self.column_studio].text.strip()
        main_id: str = all_cells[self.column_main_id].text.strip()
        duplicates: List[str] = self._get_duplicate_scene_ids(all_cells[self.column_main_id:])

        return done, { 'studio': studio, 'main_id': main_id, 'duplicates': duplicates }

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
            if any(c in self.done_styles for c in cell.attrs.get('class', [])):
                continue
                print(f'skipped completed {name}')

            results.append(scene_id)

        return results


class DuplicatePerformers(_DataExtractor):
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
            row_num, done, item = self._transform_row(row)

            # already processed
            if self.skip_done and done:
                continue
            # empty row
            if not item['main_id']:
                continue
            # no duplicates listed
            if not item['duplicates']:
                continue

            self.data.append(item)

    def _transform_row(self, row: bs4.Tag) -> Tuple[int, bool, DuplicatePerformersItem]:
        done = self._is_row_done(row)
        row_num = int(row.select_one('th').text)

        all_cells = row.select('td')

        name: str = all_cells[self.column_name].text.strip()
        main_id: str = all_cells[self.column_main_id].text.strip()
        duplicate_ids: List[str] = self._get_duplicate_performer_ids(all_cells[self.column_main_id:], row_num)

        return row_num, done, { 'name': name, 'main_id': main_id, 'duplicates': duplicate_ids }

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
            if any(c in self.done_styles for c in cell.attrs.get('class', [])):
                continue
                print(f'skipped completed {p_id}')

            if p_id in results:
                print(f'Row {row_num:<4} | WARNING: Skipping duplicate performer ID: {p_id}')
                continue

            results.append(p_id)

        return results
