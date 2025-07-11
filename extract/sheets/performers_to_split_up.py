# coding: utf-8
import re
import string
from typing import List, NamedTuple, Optional
from urllib.parse import urlsplit

from ..base import BacklogBase
from ..classes import Sheet, SheetCell, SheetRow
from ..logger import LoggerMixin
from ..models import PerformersToSplitUpItem, SplitFragment
from ..utils import URL_PATTERN, is_uuid, parse_stashdb_url


def column_letter(cell_num: int) -> str:
    """Converts a number to letter column as used in Sheets/Excel."""
    cell_col = ''
    while cell_num > 0:
        cell_num, rem = divmod(cell_num - 1, 26)
        cell_col = string.ascii_uppercase[rem] + cell_col
    return cell_col

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


class PerformersToSplitUp(BacklogBase, LoggerMixin):
    def __init__(self, sheet: Sheet, skip_done_rows: bool, skip_done_fragments: bool):
        LoggerMixin.__init__(self, __name__, 'performer')
        self.skip_done = skip_done_rows
        self.skip_done_fragments = skip_done_fragments

        self.column_done = sheet.get_column_index('V')
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
            self.log('error', str(error), error.row_num)
            done = False

        cells_fragments = [c for i, c in enumerate(row.cells) if i in self.columns_fragments]

        done_note: str = row.cells[self.column_done].note.strip()
        status: str = row.cells[self.column_status].value.strip()
        name: str = row.cells[self.column_name].value.strip()
        p_id: str = row.cells[self.column_p_id].value.strip()
        user: str = row.cells[self.column_user].value.strip()
        notes_c   = row.cells[self.column_notes]
        notes: str = notes_c.value.strip()
        fragments = self._get_fragments(cells_fragments, row.num)

        if p_id and not is_uuid(p_id):
            self.log('warning', f"Invalid performer ID: '{p_id}'", row.num)
            p_id = None  # type: ignore

        item = PerformersToSplitUpItem(row=row.num, name=name, id=p_id, fragments=fragments)

        if status:
            item['status'] = status
        if done_note.startswith('https://stashdb.org/edits/'):
            item['submitted'] = True
            item['status'] = '[queued to be marked as done]'

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

        column_1 = self.columns_fragments[0]

        for cell_num, cell in enumerate(cells, 1):
            # skip empty
            if not cell.value.strip():
                continue

            cell_col = column_letter(cell_num + column_1)

            # skip completed
            if cell.done and self.skip_done_fragments:
                continue
                self.log('', f'skipped completed fragment {cell_col} ({cell_num}): {cell.value}', row_num)

            if fragment := self._parse_fragment_cell(cell, cell_col):
                results.append(fragment)

        return results

    LIST_PATTERN = re.compile(r'^([\u0002\u0003])?- ')
    LABELS_PATTERN = compile_labels_pattern()
    ST_LINK_PATTERN = re.compile(r'\u0002' + URL_PATTERN.pattern + r'\u0003')

    def _parse_fragment_cell(self, cell: SheetCell, cell_col: str) -> Optional[SplitFragment]:
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
            # a symbol to stop processing the notes
            if note == '### ARCHIVE ###':
                break

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
            url_parts = urlsplit(url)

            if not p_id and url in cell.links:
                # Extract performer ID from url, if exists
                obj, uuid = parse_stashdb_url(url)
                if obj == 'performers' and uuid and not url_parts.query:
                    p_id = uuid
                    continue

            if url in cell.links:
                # Remove unuseful automated links
                if url_parts.scheme == 'http' and url_parts.path == '/':
                    continue

            links.append(url)

        links[:] = list(dict.fromkeys(links))

        fragment = SplitFragment(
            raw=value,
            column=cell_col,
            id=p_id,
            name=name,
        )

        if text:
            fragment['text'] = text
        if notes:
            fragment['notes'] = notes
        if links:
            fragment['links'] = links
        if cell.done:
            fragment['done'] = cell.done

        return fragment

    def sort_key(self, item: PerformersToSplitUpItem):
        # Performer name, ASC
        return item['name'].casefold()

    def __iter__(self):
        return iter(self.data)
