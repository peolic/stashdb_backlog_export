# coding: utf-8
import re
import string
from typing import List, NamedTuple, Optional
from urllib.parse import urlsplit

from ..base import BacklogBase
from ..classes import Sheet, SheetCell, SheetRow
from ..models import PerformersToSplitUpItem, SplitShard
from ..utils import URL_PATTERN, is_uuid, parse_stashdb_url


class PerformersToSplitUp(BacklogBase):
    def __init__(self, sheet: Sheet, skip_done: bool):
        self.skip_done = skip_done

        self.column_name    = sheet.get_column_index('Performer')
        self.column_p_id    = sheet.get_column_index(re.compile('Performer ID'))
        self.column_user    = sheet.get_column_index(re.compile('Added by'))
        self.column_notes   = sheet.get_column_index(re.compile('Notes'))
        self.columns_shards = sheet.get_all_column_indices(re.compile(r'Performer \d'))

        self.data = self._parse(sheet.rows)

    def _parse(self, rows: List[SheetRow]) -> List[PerformersToSplitUpItem]:
        data: List[PerformersToSplitUpItem] = []
        for row in rows:
            row = self._transform_row(row)

            # already processed
            if self.skip_done and row.done:
                continue

            # useless row
            if not row.item['id']:
                continue

            data.append(row.item)

        return data

    class RowResult(NamedTuple):
        num: int
        done: bool
        item: PerformersToSplitUpItem

    def _transform_row(self, row: SheetRow) -> RowResult:
        try:
            done = row.is_done()
        except row.CheckboxNotFound as error:
            print(error)
            done = False

        cells_shards = [c for i, c in enumerate(row.cells) if i in self.columns_shards]

        name: str = row.cells[self.column_name].value.strip()
        p_id: str = row.cells[self.column_p_id].value.strip()
        user: str = row.cells[self.column_user].value.strip()
        notes: str = row.cells[self.column_notes].value.strip()
        shards = self._get_shards(cells_shards, row.num)

        if p_id and not is_uuid(p_id):
            print(f"Row {row.num:<4} | WARNING: Invalid performer UUID: '{p_id}'")
            p_id = None  # type: ignore

        item = PerformersToSplitUpItem(name=name, id=p_id, shards=shards)

        notes_lines = list(filter(str.strip, notes.splitlines(False)))
        if notes_lines:
            item['notes'] = notes_lines

        if user:
            item['user'] = user

        return self.RowResult(row.num, done, item)

    LABELS_PATTERN = re.compile(r'\[?((?:stashdb|(?<=\[)stash(?=\]))|iafd|i(?:nde)?xxx|thenude|twitter|gevi)\]?', re.I)

    def _get_shards(self, cells: List[SheetCell], row_num: int) -> List[SplitShard]:
        results: List[SplitShard] = []

        for shard_num, cell in enumerate(cells, 1):
            value = cell.value.strip()

            # skip empty
            if not value:
                continue

            # skip completed
            if cell.done:
                continue
                print(f'Row {row_num:<4} | skipped completed shard {shard_num}: {value}')

            note_links: List[str] = []
            notes = list(filter(str.strip, cell.note.split('\n')))
            for note in notes[:]:
                if url_match := URL_PATTERN.match(note):
                    note_links.append(url_match.group(1))
                    notes.remove(note)

            p_id: Optional[str] = None
            links: List[str] = []

            for url in cell.links + note_links:
                if not p_id:
                    # Extract performer ID from url, if exists
                    obj, uuid = parse_stashdb_url(url)
                    if obj == 'performers' and uuid:
                        p_id = uuid
                        continue

                # Remove unuseful automated links
                urlparts = urlsplit(url)
                if urlparts.scheme == 'http' and urlparts.path == '/':
                    continue

                links.append(url)

            links[:] = list(dict.fromkeys(links))

            tokens: List[str] = []
            possible_name = ''
            for l in value.splitlines(False):
                l = l.strip('-' + string.whitespace)
                if not l:
                    continue

                if not possible_name:
                    possible_name = re.sub(rf'(-\s+)?{self.LABELS_PATTERN.pattern}', '', l, flags=re.I).strip()
                    continue

                for t in l.split(' '):
                    t = t.strip('-' + string.whitespace)
                    if not t:
                        continue
                    if self.LABELS_PATTERN.fullmatch(t):
                        continue
                    tokens.append(t)

            text = ' '.join(tokens)

            shard = SplitShard(
                raw=value,
                id=p_id,
                name=possible_name
            )

            if text:
                shard['text'] = text
            if notes:
                shard['notes'] = notes
            if links:
                shard['links'] = links

            results.append(shard)

        return results

    def sort_key(self, item: PerformersToSplitUpItem):
        # Performer name, ASC
        return item['name'].casefold()

    def __iter__(self):
        return iter(self.data)
