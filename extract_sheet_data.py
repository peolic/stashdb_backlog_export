#!/usr/bin/env python3.8
# coding: utf-8
import json
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qsl
from typing import List, Optional, Set, Tuple, TypedDict

# DEPENDENCIES
import bs4        # pip install beautifulsoup4
import cssutils   # pip install cssutils
import requests   # pip install requests


# Determine performer appearance update entries from remove & append entries
USE_UPDATES = False


def main():
    data = ScenePerformers()
    data.write(Path('scene_performers.json'))
    # data = DuplicateScenes()
    # data.write(Path('duplicate_scenes.json'))
    print('Success')


class _DataExtractor:

    def __init__(self, gid: str):
        resp = requests.get(
            url='https://docs.google.com/spreadsheets/d/1eiOC-wbqbaK8Zp32hjF8YmaKql_aH-yeGLmvHP1oBKQ/htmlview',
            params={'gid': gid},
        )
        resp.raise_for_status()

        self.soup = bs4.BeautifulSoup(resp.text, 'html.parser')

        # find the class names that are strike/line-through (partially completed entries)
        self.done_styles = self.get_done_classes()

        _sheet: Optional[bs4.Tag] = self.soup.select_one(f'div[id="{gid}"]')
        if not _sheet:
            print('ERROR: Sheet not found')
            return

        self.sheet = _sheet

        self.data = []

    def get_done_classes(self) -> Set[str]:
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


class PerformerEntry(TypedDict):
    id: Optional[str]
    name: str
    appearance: Optional[str]


class _ScenePerformersItemOptional(TypedDict, total=False):
    update: List[PerformerEntry]

class ScenePerformersItem(_ScenePerformersItemOptional, TypedDict):
    scene_id: str
    remove: List[PerformerEntry]
    append: List[PerformerEntry]
    # update: List[PerformerEntry]


class ScenePerformers(_DataExtractor):
    def __init__(self):
        super().__init__(gid='1397718590')

        all_rows = self.sheet.select('tbody > tr')
        first_row: bs4.Tag = all_rows[0]

        _scene_id_column: Optional[bs4.Tag] = first_row.find('td', text=re.compile('Scene ID'))
        _remove_columns: List[bs4.Tag] = first_row.find_all('td', text=re.compile(r'\(\d+\) Remove/Replace'))
        _append_columns: List[bs4.Tag] = first_row.find_all('td', text=re.compile(r'\(\d+\) Add/With'))

        # indices start at 1, we need 0
        self.column_scene_id = -1 + first_row.index(_scene_id_column)
        self.columns_remove  = [-1 + first_row.index(c) for c in _remove_columns]
        self.columns_append  = [-1 + first_row.index(c) for c in _append_columns]

        self.data = []
        for row in all_rows[2:]:
            done, item = self._transform_row(row)

            # already processed
            if done:
                continue
            # empty row
            if not item['scene_id']:
                continue
            # no changes
            if len(item['remove'] + item['append'] + item.get('update', [])) == 0:
                continue

            self.data.append(item)

    def _transform_row(self, row: bs4.Tag) -> Tuple[bool, ScenePerformersItem]:
        done = self._is_row_done(row)

        all_cells = row.select('td')
        remove_cells: List[bs4.Tag] = [c for i, c in enumerate(all_cells) if i in self.columns_remove]
        append_cells: List[bs4.Tag] = [c for i, c in enumerate(all_cells) if i in self.columns_append]

        scene_id: str = all_cells[self.column_scene_id].text.strip()
        remove = self._get_change_entries(remove_cells, scene_id)
        append = self._get_change_entries(append_cells, scene_id)
        update = self._find_updates(remove, append, scene_id, extract=USE_UPDATES)

        if USE_UPDATES:
            return done, { 'scene_id': scene_id, 'remove': remove, 'append': append, 'update': update }

        return done, { 'scene_id': scene_id, 'remove': remove, 'append': append }

    def _get_change_entries(self, cells: List[bs4.Tag], scene_id: str):
        results: List[PerformerEntry] = []

        for cell in cells:
            name: str = cell.text.strip()

            # skip empty
            if not name or name.startswith('>>>>>'):
                continue

            # skip comments
            if name.startswith('#'):
                continue

            # skip completed
            if any(c in self.done_styles for c in cell.attrs.get('class', [])):
                continue
                print(f'skipped completed {name}')

            entry = self._get_change_entry(name, cell, scene_id)
            if not entry:
                continue
                print(f'skipped invalid {name}')

            results.append(entry)

        return results

    def _get_change_entry(self, raw_name: str, cell: bs4.Tag, scene_id: str) -> Optional[PerformerEntry]:
        match = re.search(r'(?:^\[[a-z]+\]\s)?(.+?)(?: \(as (.+?)\))', raw_name)
        if match is None:
            name = raw_name
            appearance = None
        else:
            name = match.group(1)
            appearance = match.group(2)

        try:
            url: str = cell.select_one('a').attrs['href']

            url_p = urlparse(url)
            if url_p.hostname == 'www.google.com' and url_p.path == '/url':
                url = dict(parse_qsl(url_p.query))['q']
                url = urlparse(url)._replace(query=None, fragment=None).geturl()
        except (AttributeError, KeyError):
            print(f'WARNING: Missing performer ID: {raw_name} | Scene: {scene_id}')
            p_id = None
        else:
            match = re.search(r'/([a-z]+)/([0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12})$', url)
            if match is None:
                print(f"WARNING: Failed to extract performer ID for: {raw_name} | Scene: {scene_id}")
                p_id = None
            else:
                obj = match.group(1)
                p_id = match.group(2)
                if obj != 'performers':
                    p_id = None
                    if obj == 'edits':
                        print(f"WARNING: New performer? Edit ID found for: {raw_name} | Scene: {scene_id}")
                    else:
                        print(f"WARNING: Failed to extract performer ID for: {raw_name} | Scene: {scene_id}")

        return { 'id': p_id, 'name': name, 'appearance': appearance }

    def _find_updates(
        self,
        remove: List[PerformerEntry],
        append: List[PerformerEntry],
        scene_id: str,
        extract: bool
    ) -> List[PerformerEntry]:
        updates: List[PerformerEntry] = []

        remove_ids = [i['id'] for i in remove]
        append_ids = [i['id'] for i in append]
        update_ids = set(remove_ids).intersection(append_ids)

        for pid in update_ids:
            if pid is None:
                continue

            r_item = remove[remove_ids.index(pid)]
            a_item = append[append_ids.index(pid)]

            # This is either not an update, or the one of IDs is incorrect
            if r_item['name'] != a_item['name'] or r_item['appearance'] == a_item['appearance']:
                print(f"WARNING: Unexpected name/ID for scene {scene_id} :"
                      f"\n  {r_item['name']:<20} // {str(r_item['appearance']):<20} // {r_item['id']}"
                      f"\n  {a_item['name']:<20} // {str(a_item['appearance']):<20} // {a_item['id']}")
                continue

            updates.append(a_item)

        if not extract:
            return updates

        for u_item in updates:
            remove.remove(next(r for r in remove if r['id'] == u_item['id']))
            append.remove(u_item)

        return updates


class DuplicateScenes(_DataExtractor):
    def __init__(self):
        super().__init__(gid='1879471751')

        all_rows: bs4.ResultSet = self.sheet.select('tbody > tr')

        # indices start at 1, we need 0
        self.column_studio: int  = -1 + all_rows[0].index(all_rows[0].find('td', text=re.compile('Studio')))
        self.column_main_id: int = -1 + all_rows[0].index(all_rows[0].find('td', text=re.compile('Main ID')))

        self.data = []
        for row in all_rows[2:]:
            done, item = self._transform_row(row)

            # already processed
            if done:
                continue
            # useless row
            if not item['main_id'] or not item['duplicates']:
                continue

            self.data.append(item)

    def _transform_row(self, row: bs4.Tag):
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


if __name__ == '__main__':
    main()
