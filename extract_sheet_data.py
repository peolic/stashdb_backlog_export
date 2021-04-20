# coding: utf-8
import json
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qsl
from typing import List, Set

# DEPENDENCIES
import bs4        # pip install beautifulsoup4
import cssutils   # pip install cssutils
import requests   # pip install requests


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

        self.sheet = self.soup.select_one(f'div[id="{gid}"]')

        self.data = []

    def get_done_classes(self) -> Set[str]:
        style = self.soup.select_one('head > style').renderContents()
        stylesheet = cssutils.parseString(style, validate=False)

        classes = set()
        for rule in stylesheet:
            if rule.type == rule.STYLE_RULE and rule.style.textDecoration == 'line-through':
                classes.update([
                    c.lstrip('.')
                    for c in rule.selectorText.split(' ')
                    if c.startswith('.s')
                ])

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


class ScenePerformers(_DataExtractor):
    def __init__(self):
        super().__init__(gid='1397718590')

        all_rows = self.sheet.select('tbody > tr')

        # indices start at 1, we need 0
        self.column_scene_id   = -1 + all_rows[0].index(all_rows[0].find('td', text=re.compile('Scene ID')))
        self.column_first_info = -1 + all_rows[0].index(all_rows[0].find('td', text=re.compile('Remove/Replace|Add/With')))

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
            if len(item['remove'] + item['append']) == 0:
                continue

            self.data.append(item)

    def _transform_row(self, row: bs4.Tag):
        done = self._is_row_done(row)

        all_cells = row.select('td')
        remove_cells: List[bs4.Tag] = all_cells[self.column_first_info:][::2][:3]
        append_cells: List[bs4.Tag] = all_cells[self.column_first_info + 1:][::2][:3]

        id_: str = all_cells[self.column_scene_id].text.strip()
        remove = self._get_change_entries(remove_cells)
        append = self._get_change_entries(append_cells)

        return done, { 'scene_id': id_, 'remove': remove, 'append': append }

    def _get_change_entries(self, cells: List[bs4.Tag]):
        results = []

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

            results.append(
                self._get_change_entry(name, cell)
            )

        return results

    def _get_change_entry(self, raw_name: str, cell: bs4.Tag):
        match = re.search(r'(?:^\[new\]\s)?(.+?)(?: \(as (.+?)\))', raw_name)
        if match is None:
            name = raw_name
            as_ = None
        else:
            name = match.group(1)
            as_ = match.group(2)

        try:
            url: str = cell.select_one('a').attrs['href']

            url_p = urlparse(url)
            if url_p.hostname == 'www.google.com' and url_p.path == '/url':
                url = dict(parse_qsl(url_p.query))['q']
                url = urlparse(url)._replace(query=None, fragment=None).geturl()
        except (AttributeError, KeyError):
            id_ = None
        else:
            match = re.search(r'\/([0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12})$', url)
            if match is None:
                id_ = None
            else:
                id_ = match.group(1)

        return { 'id': id_, 'name': name, 'as': as_ }


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
