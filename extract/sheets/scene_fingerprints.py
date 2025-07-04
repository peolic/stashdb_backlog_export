# coding: utf-8
import re
from typing import Dict, List, Optional

from ..base import BacklogBase
from ..classes import Sheet, SheetRow
from ..logger import LoggerMixin
from ..models import SceneFingerprintsDict, SceneFingerprintsItem
from ..utils import is_uuid, parse_duration


class SceneFingerprints(BacklogBase, LoggerMixin):
    def __init__(self, sheet: Sheet, skip_done: bool, skip_no_correct_scene: bool, with_user: bool = False):
        LoggerMixin.__init__(self, __name__, 'scene')
        self.skip_done = skip_done
        self.skip_no_correct_scene = skip_no_correct_scene
        self.with_user = with_user

        self.column_scene_id = sheet.get_column_index(re.compile('Scene ID'))
        self.column_algorithm = sheet.get_column_index(re.compile('Algorithm'))
        self.column_fingerprint = sheet.get_column_index(re.compile('Fingerprint'))
        self.column_correct_scene_id = sheet.get_column_index(re.compile('Correct Scene ID'))
        self.column_duration = sheet.get_column_index(re.compile('Duration'))
        self.column_user = sheet.get_column_index(re.compile('Added by'))

        self.data = self._parse(sheet.rows)

    def _parse(self, rows: List[SheetRow]) -> SceneFingerprintsDict:
        data: SceneFingerprintsDict = {}
        last_seen: Dict[str, int] = {}

        for row in rows:
            try:
                done = row.is_done()
            except row.CheckboxNotFound as error:
                self.log('error', str(error), error.row_num)
                done = False

            scene_id: str = row.cells[self.column_scene_id].value.strip()
            algorithm: str = row.cells[self.column_algorithm].value.strip()
            fp_hash: str = row.cells[self.column_fingerprint].value.strip()
            correct_scene_id: Optional[str] = row.cells[self.column_correct_scene_id].value.strip() or None
            duration: str = row.cells[self.column_duration].value.strip()
            user: str = row.cells[self.column_user].value.strip()

            last_row = last_seen.get(scene_id, None)

            # already processed
            if self.skip_done and done:
                if last_row:
                    last_seen[scene_id] = row.num
                continue

            # useless row
            if not (scene_id and algorithm and fp_hash):
                continue

            if last_row and row.num > (last_row + 1):
                self.log('warning', f'Ungrouped entries for scene ID {scene_id!r} last seen row {last_row}',
                         row.num, uuid=scene_id)
            else:
                last_seen[scene_id] = row.num

            if algorithm in ('phash', 'oshash', 'md5'):
                pass  # Pylance acting up when using `not in`
            else:
                self.log('warning', f'Skipped due to invalid algorithm', row.num)
                continue

            if (
                re.fullmatch(r'^[a-f0-9]+$', fp_hash) is None
                or algorithm in ('phash', 'oshash') and len(fp_hash) != 16 and fp_hash != '0'
                or algorithm == 'md5' and len(fp_hash) != 32
            ):
                self.log('warning', f'Skipped due to invalid hash', row.num)
                continue

            # invalid scene id
            if not is_uuid(scene_id):
                self.log('warning', f'Skipped due to invalid scene ID: {scene_id}', row.num)
                continue

            if self.skip_no_correct_scene and not correct_scene_id:
                self.log('warning', f'Skipped due to missing correct scene ID', row.num, uuid=scene_id)
                continue

            if correct_scene_id and not is_uuid(correct_scene_id):
                self.log('warning', f'Ignored invalid correct scene ID: {correct_scene_id}', row.num, uuid=scene_id)
                correct_scene_id = None

            if not duration or duration == '-':
                duration_s = None
            else:
                duration_s = parse_duration(duration)
                if duration_s is None:
                    self.log('warning', f'Invalid duration: {duration}', row.num, uuid=scene_id)

            item = SceneFingerprintsItem(
                algorithm=algorithm,
                hash=fp_hash,
                correct_scene_id=correct_scene_id,
            )

            if duration_s:
                item['duration'] = duration_s

            if self.with_user and user:
                item['user'] = user

            data.setdefault(scene_id, []).append(item)

        # dedupe
        for items in data.values():
            items[:] = list({
                (item['algorithm'], item['hash']): item
                for item in items
            }.values())

        return data

    def __iter__(self):
        return iter(self.data.items())
