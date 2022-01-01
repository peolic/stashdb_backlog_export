# coding: utf-8
import re
from typing import List, Optional

from ..models import SceneFingerprintsDict, SceneFingerprintsItem
from ..utils import is_uuid
from .base import BacklogBase
from .classes import Sheet, SheetRow


class SceneFingerprints(BacklogBase):
    def __init__(self, sheet: Sheet, skip_done: bool, skip_no_correct_scene: bool):
        self.skip_done = skip_done
        self.skip_no_correct_scene = skip_no_correct_scene

        self.column_scene_id = sheet.get_column_index(re.compile('Scene ID'))
        self.column_algorithm = sheet.get_column_index(re.compile('Algorithm'))
        self.column_fingerprint = sheet.get_column_index(re.compile('Fingerprint'))
        self.column_correct_scene_id = sheet.get_column_index(re.compile('Correct Scene ID'))
        self.column_user = sheet.get_column_index(re.compile('Added by'))

        self.data = self._parse(sheet.rows)

    def _parse(self, rows: List[SheetRow]) -> SceneFingerprintsDict:
        data: SceneFingerprintsDict = {}
        for row in rows:
            # already processed
            if self.skip_done and row.is_done():
                continue

            scene_id: str = row.cells[self.column_scene_id].value.strip()
            algorithm: str = row.cells[self.column_algorithm].value.strip()
            fp_hash: str = row.cells[self.column_fingerprint].value.strip()
            correct_scene_id: Optional[str] = row.cells[self.column_correct_scene_id].value.strip() or None
            user: str = row.cells[self.column_user].value.strip()

            # useless row
            if not (scene_id and algorithm and fp_hash):
                continue

            if self.skip_no_correct_scene and not correct_scene_id:
                print(f'Row {row.num:<4} | WARNING: Skipped due to missing correct scene ID')
                continue

            if algorithm not in ('phash', 'oshash', 'md5'):
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

            if correct_scene_id and not is_uuid(correct_scene_id):
                print(f'Row {row.num:<4} | WARNING: Skipped due to invalid correct scene ID')
                continue

            item = SceneFingerprintsItem(
                algorithm=algorithm,
                hash=fp_hash,
                correct_scene_id=correct_scene_id,
            )

            if user:
                item['user'] = user

            data.setdefault(scene_id, []).append(item)

        return data

    def __iter__(self):
        return iter(self.data.items())
