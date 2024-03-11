# coding: utf-8
import re
from typing import List, NamedTuple, Optional
from urllib.parse import urlsplit

from ..base import BacklogBase
from ..classes import Sheet, SheetCell, SheetRow
from ..models import PerformersToSplitUpItem, SplitFragment
from ..utils import URL_PATTERN, is_uuid, parse_stashdb_url


def compile_labels_pattern():
    labels = '|'.join([
        r'stash(db)?',
        r'iafd',
        r'i(nde)?xxx',
        r'(the)?nude',
        r'[be]gafd',
        r'd(ata)?18',
        r'gevi',
        r'adt',
        r'studio',
        r'scene',
    ])
    return re.compile(rf'(- )? *\[({labels})( ?\d)?\]', re.I)


class PerformersToSplitUp(BacklogBase):
    def __init__(self, sheet: Sheet, skip_done_rows: bool, skip_done_fragments: bool):
        self.skip_done = skip_done_rows
        self.skip_done_fragments = skip_done_fragments

        self.column_status = sheet.get_column_index(re.compile(r'Status|Claimed by'))
        self.column_name = sheet.get_column_index('Performer')
        self.column_p_id = sheet.get_column_index(re.compile('Performer ID'))
        self.column_user = sheet.get_column_index(re.compile('Added by'))
        self.column_notes = sheet.get_column_index(re.compile('Notes'))
        self.columns_fragments = sheet.get_all_column_indices(re.compile(r'(Performer|Fragment) \d'))

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

        cells_fragments = [c for i, c in enumerate(row.cells) if i in self.columns_fragments]

        status: str = row.cells[self.column_status].value.strip()
        name: str = row.cells[self.column_name].value.strip()
        p_id: str = row.cells[self.column_p_id].value.strip()
        user: str = row.cells[self.column_user].value.strip()
        notes_c   = row.cells[self.column_notes]
        notes: str = notes_c.value.strip()
        fragments = self._get_fragments(cells_fragments, row.num)

        if p_id and not is_uuid(p_id):
            print(f"Row {row.num:<4} | WARNING: Invalid performer ID: '{p_id}'")
            p_id = None  # type: ignore

        item = PerformersToSplitUpItem(name=name, id=p_id, fragments=fragments)

        if status:
            if (status[0], status[-1]) == ('[', ']'):
                item['status'] = status[1:-1]

        notes_lines = list(filter(str.strip, notes.splitlines(False)))
        if notes_lines:
            item['notes'] = notes_lines

        notes_links = list(dict.fromkeys(
            l for l in notes_c.links
            if not notes_lines or l not in notes_lines
        ))
        if notes_links:
            item['links'] = notes_links

        if user:
            item['user'] = user

        return self.RowResult(row.num, done, item)

    def _get_fragments(self, cells: List[SheetCell], row_num: int) -> List[SplitFragment]:
        results: List[SplitFragment] = []

        for cell_num, cell in enumerate(cells, 1):
            # skip empty
            if not cell.value.strip():
                continue

            # skip completed
            if cell.done and self.skip_done_fragments:
                continue
                print(f'Row {row_num:<4} | skipped completed fragment {cell_num}: {cell.value}')

            if fragment := self._parse_fragment_cell(cell):
                results.append(fragment)

        return results

    LIST_PATTERN = re.compile(r'^([\u0002\u0003])?- ')
    LABELS_PATTERN = compile_labels_pattern()
    ST_LINK_PATTERN = re.compile(r'\u0002' + URL_PATTERN.pattern + r'\u0003')

    def _parse_fragment_cell(self, cell: SheetCell) -> Optional[SplitFragment]:
        value = cell.value.strip()
        lines = value.splitlines()

        first_line = lines.pop(0)
        if not lines and (labels := list(self.LABELS_PATTERN.finditer(first_line))):
            name = first_line[:labels[0].start()]
            lines = [first_line[labels[-1].end():]]
        else:
            name = self.LABELS_PATTERN.sub('', first_line)
        name = name.strip() or '[no name provided]'

        cleaned: List[str] = []
        for line in lines:
            if line := self.LABELS_PATTERN.sub('', line).strip():
                cleaned.append(line)

        text: str = ''
        notes: List[str] = []
        note_links: List[str] = []

        for note in filter(str.strip, cell.note.splitlines()):
            note = self.ST_LINK_PATTERN.sub('', note)
            if not note.strip():
                continue

            if url_match := URL_PATTERN.match(note):
                note_links.append(url_match.group(1))
            else:
                notes.append(note)

        if cleaned:
            text = cleaned[0]
            # '\n- ...\n- ...'
            # /or/ (text) '\n- ...' + (note) '- ...\n- ...'
            if (rest := cleaned[1:] + notes) and all(map(self.LIST_PATTERN.match, (text, rest[0]))):
                text = ''
                notes[0:0] = cleaned
            else:
                text = self.LIST_PATTERN.sub(r'\1', text)
                notes[0:0] = cleaned[1:]

        p_id: Optional[str] = None
        links: List[str] = []

        for url in cell.links + note_links:
            if not p_id and url in cell.links:
                # Extract performer ID from url, if exists
                obj, uuid = parse_stashdb_url(url)
                if obj == 'performers' and uuid:
                    p_id = uuid
                    continue

            if url in cell.links:
                # Remove unuseful automated links
                url_parts = urlsplit(url)
                if url_parts.scheme == 'http' and url_parts.path == '/':
                    continue

            links.append(url)

        links[:] = list(dict.fromkeys(links))

        fragment = SplitFragment(
            raw=value,
            **(dict(done=cell.done) if cell.done else dict()),
            id=p_id,
            name=name,
        )

        if text:
            fragment['text'] = text
        if notes:
            fragment['notes'] = notes
        if links:
            fragment['links'] = links

        return fragment

    def sort_key(self, item: PerformersToSplitUpItem):
        # Performer name, ASC
        return item['name'].casefold()

    def __iter__(self):
        return iter(self.data)
