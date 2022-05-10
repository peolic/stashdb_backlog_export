# coding: utf-8
import re
from typing import Dict, List, NamedTuple, Optional, Tuple

from ..base import BacklogBase
from ..classes import Sheet, SheetCell, SheetRow
from ..models import (
    AnyPerformerEntry,
    PerformerEntry,
    PerformerUpdateEntry,
    ScenePerformersItem
)
from ..utils import (
    first_performer_name,
    performer_name,
    format_studio,
    get_all_entries,
    is_uuid,
    parse_stashdb_url
)


class ScenePerformers(BacklogBase):
    def __init__(self, sheet: Sheet, skip_done: bool, skip_no_id: bool):
        self.skip_done = skip_done
        self.skip_no_id = skip_no_id

        self.column_studio   = sheet.get_column_index(re.compile('Studio'))
        self.column_scene_id = sheet.get_column_index(re.compile('Scene ID'))
        self.columns_remove  = sheet.get_all_column_indices(re.compile(r'\(\d+\) Remove/Replace'))
        self.columns_append  = sheet.get_all_column_indices(re.compile(r'\(\d+\) Add/With'))
        self.column_note     = sheet.get_column_index(re.compile('Edit Note'))
        self.column_user     = sheet.get_column_index(re.compile('Added by'))

        self._parent_studio_pattern = re.compile(r'^(?P<studio>.+?) \[(?P<parent_studio>.+)\]$')

        self.data = self._parse(sheet.rows)

    def _parse(self, rows: List[SheetRow]) -> List[ScenePerformersItem]:
        data: Dict[str, ScenePerformersItem] = {}
        for row in rows:
            row = self._transform_row(row)

            scene_id = row.item['scene_id']
            all_entries = get_all_entries(row.item)

            # already processed
            if not self.skip_done:
                row.item['done'] = row.done
            elif row.done:
                continue

            if row.submitted:
                row.item['submitted'] = row.submitted

            # empty row
            if not scene_id:
                continue
            # skip anything else
            if not is_uuid(scene_id):
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
                formatted_merge_tagged = [performer_name(i) for i in by_status['merge']]
                print(
                    f'Row {row.num:<4} | Skipped due to [merge]-tagged performers: '
                    + ' , '.join(formatted_merge_tagged)
                )
                continue
            # skip entries tagged with [edit] as they are marked to be edited
            #   and given the information of one of the to-append performers
            if self.skip_no_id and by_status.get('edit'):
                formatted_edit_tagged = [performer_name(i) for i in by_status['edit']]
                print(
                    f'Row {row.num:<4} | Skipped due to [edit]-tagged performers: '
                    + ' , '.join(formatted_edit_tagged)
                )
                continue
            # skip entries tagged with [new] as they are marked to be created
            if self.skip_no_id and by_status.get('new'):
                formatted_new_tagged = [performer_name(i) for i in by_status['new']]
                print(
                    f'Row {row.num:<4} | Skipped due to [new]-tagged performers: '
                    + ' , '.join(formatted_new_tagged)
                )
                continue
            # If this item has any performers that do not have a StashDB ID,
            #   skip the whole item for now, to avoid unwanted deletions.
            if self.skip_no_id and (no_id := [i for i in all_entries if not i['id']]):
                formatted_no_id = [performer_name(i) for i in no_id]
                print(
                    f'Row {row.num:<4} | WARNING: Skipped due to missing performer IDs: '
                    + ' , '.join(formatted_no_id)
                )
                continue

            if scene_id in data:
                data[scene_id]['remove'].extend(row.item['remove'])

                data[scene_id]['append'].extend(row.item['append'])

                if this_update := row.item.get('update'):
                    if previous_update := data[scene_id].get('update'):
                        previous_update.extend(this_update)
                    else:
                        data[scene_id]['update'] = this_update

                if this_comment := row.item.get('comment'):
                    if previous_comment := data[scene_id].get('comment'):
                        data[scene_id]['comment'] = previous_comment + '\n' + this_comment
                    else:
                        data[scene_id]['comment'] = this_comment

            else:
                data[scene_id] = row.item

        return list(data.values())

    class RowResult(NamedTuple):
        num: int
        submitted: bool
        done: bool
        item: ScenePerformersItem

    def _transform_row(self, row: SheetRow) -> RowResult:
        try:
            submitted = row.is_done(1)
            done = row.is_done(2)
        except row.CheckboxNotFound:
            submitted = False
            try:
                done = row.is_done()
            except row.CheckboxNotFound as error:
                print(error)
                done = False

        remove_cells = [c for i, c in enumerate(row.cells) if i in self.columns_remove]
        append_cells = [c for i, c in enumerate(row.cells) if i in self.columns_append]

        studio: str = row.cells[self.column_studio].value.strip()
        scene_id: str = row.cells[self.column_scene_id].value.strip()
        remove = self._get_change_entries(remove_cells, row.num)
        append = self._get_change_entries(append_cells, row.num)
        update = self._find_updates(remove, append, row.num)

        note_c = row.cells[self.column_note]
        note   = note_c.value.strip()

        user: str = row.cells[self.column_user].value.strip()

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

        comment = '\n\n'.join(filter(str.strip, filter(None, [note, note_c.note])))
        if comment:
            item['comment'] = comment

        if user:
            item['user'] = user

        return self.RowResult(row.num, submitted, done, item)

    def _get_change_entries(self, cells: List[SheetCell], row_num: int):
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

    def _get_change_entry(self, cell: SheetCell, row_num: int) -> Tuple[Optional[PerformerEntry], str]:
        raw_name: str = cell.value.strip()

        # skip empty
        if not raw_name or raw_name.startswith('>>>>>'):
            return None, raw_name

        # skip comments/completed
        if raw_name.startswith(('#', '[v]')):
            return None, raw_name

        # skip completed (legacy)
        if self.skip_done and cell.done:
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
        url = cell.first_link
        if url is None:
            if status != 'new':
                print(f'Row {row_num:<4} | WARNING: Missing performer ID: {raw_name}')
            p_id = None

        else:
            obj, uuid = parse_stashdb_url(url)

            if obj == 'performers' and uuid:
                p_id = uuid

            elif obj is None or uuid is None:
                p_id = None
                if status != 'new':
                    print(f"Row {row_num:<4} | WARNING: Failed to extract performer ID for: {raw_name}")

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
        if status in ('new', 'c') and url:
            entry['status_url'] = url
        if cell.note:
            entry['notes'] = [n for n in cell.note.split('\n') if n.strip()]
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
                      f"\n  [{r_item['id']}] - {performer_name(r_item)}"
                      f"\n  [{a_item['id']}] - {performer_name(a_item)}")
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
