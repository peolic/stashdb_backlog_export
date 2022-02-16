# coding: utf-8
import re
from typing import Dict, List, Optional

from ..base import BacklogBase
from ..classes import Sheet, SheetRow
from ..models import SceneFingerprintsDict, SceneFingerprintsItem
from ..utils import is_uuid, parse_duration


class SceneFingerprints(BacklogBase):
    def __init__(self, sheet: Sheet, skip_done: bool, skip_no_correct_scene: bool, with_user: bool = False):
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
            # already processed
            if self.skip_done and row.is_done():
                continue

            scene_id: str = row.cells[self.column_scene_id].value.strip()
            algorithm: str = row.cells[self.column_algorithm].value.strip()
            fp_hash: str = row.cells[self.column_fingerprint].value.strip()
            correct_scene_id: Optional[str] = row.cells[self.column_correct_scene_id].value.strip() or None
            duration: str = row.cells[self.column_duration].value.strip()
            user: str = row.cells[self.column_user].value.strip()

            # useless row
            if not (scene_id and algorithm and fp_hash):
                continue

            last_row = last_seen.get(scene_id, None)
            if last_row and row.num > (last_row + 1):
                print(f'Row {row.num:<4} | WARNING: Ungrouped entries for scene ID {scene_id!r} last seen row {last_row}')
            else:
                last_seen[scene_id] = row.num

            if algorithm in ('phash', 'oshash', 'md5'):
                pass  # Pylance acting up when using `not in`
            else:
                print(f'Row {row.num:<4} | WARNING: Skipped due to invalid algorithm')
                continue

            if (
                re.fullmatch(r'^[a-f0-9]+$', fp_hash) is None
                or algorithm in ('phash', 'oshash') and len(fp_hash) != 16
                or algorithm == 'md5' and len(fp_hash) != 32
            ):
                print(f'Row {row.num:<4} | WARNING: Skipped due to invalid hash')
                continue

            if not is_uuid(scene_id):
                print(f'Row {row.num:<4} | WARNING: Skipped due to invalid scene ID')
                continue

            if self.skip_no_correct_scene and not correct_scene_id:
                print(f'Row {row.num:<4} | WARNING: Skipped due to missing correct scene ID')
                continue

            if correct_scene_id and not is_uuid(correct_scene_id):
                print(f'Row {row.num:<4} | WARNING: Skipped due to invalid correct scene ID')
                continue

            duration_s = parse_duration(duration) if duration else None
            if duration and duration_s is None:
                print(f'Row {row.num:<4} | WARNING: Invalid duration: {duration}')

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
