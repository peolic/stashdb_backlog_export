# coding: utf-8
from typing import Optional

class BacklogExtractor:

    SPREADSHEET_ID = '1eiOC-wbqbaK8Zp32hjF8YmaKql_aH-yeGLmvHP1oBKQ'
    SHEET_WHITELIST = {
        'performers_to_split_up': 1067038397,
        'scene_performers': 1397718590,
        'scene_fixes': 1419170166,
        'duplicate_performers': 651710198,
        'duplicate_scenes': 1879471751,
        'scene_fingerprints': 357846927,
    }

    def __init__(self, api_key: Optional[str]):
        args = {
            'spreadsheet_id': self.SPREADSHEET_ID,
            'sheet_ids': list(self.SHEET_WHITELIST.values()),
        }

        if api_key:
            from .interfaces.api import DataInterface
            self.interface = DataInterface(api_key=api_key, **args)
            self.type = 'API'
            return

        from .interfaces.html import HTMLInterface
        self.interface = HTMLInterface(**args)
        self.type = 'HTML'

    def scene_performers(self, skip_done: bool = True, skip_no_id: bool = True):
        """
        Args:
            skip_done   - Skip rows and/or cells that are marked as done.
            skip_no_id  - Skip items completely if at least one if the performers' IDs could not be extracted
        """
        from .sheets.scene_performers import ScenePerformers
        sheet = self.interface.get_sheet(self.SHEET_WHITELIST['scene_performers'])
        return ScenePerformers(
            sheet=sheet,
            skip_done=skip_done,
            skip_no_id=skip_no_id,
        )

    def scene_fixes(self, skip_done: bool = True):
        """
        Args:
            skip_done   - Skip rows that are marked as done.
        """
        from .sheets.scene_fixes import SceneFixes
        sheet = self.interface.get_sheet(self.SHEET_WHITELIST['scene_fixes'])
        return SceneFixes(
            sheet=sheet,
            skip_done=skip_done,
        )

    def duplicate_scenes(self):
        from .sheets.duplicate_scenes import DuplicateScenes
        sheet = self.interface.get_sheet(self.SHEET_WHITELIST['duplicate_scenes'])
        return DuplicateScenes(
            sheet=sheet,
        )

    def duplicate_performers(self, skip_done: bool = True):
        """
        Args:
            skip_done - Skip rows and/or cells that are marked as done.
        """
        from .sheets.duplicate_performers import DuplicatePerformers
        sheet = self.interface.get_sheet(self.SHEET_WHITELIST['duplicate_performers'])
        return DuplicatePerformers(
            sheet=sheet,
            skip_done=skip_done,
        )

    def scene_fingerprints(self, skip_done: bool = True, skip_no_correct_scene: bool = False):
        """
        Args:
            skip_done             - Skip rows and/or cells that are marked as done.
            skip_no_correct_scene - Skip rows that don't provide the correct scene's ID.
        """
        from .sheets.scene_fingerprints import SceneFingerprints
        sheet = self.interface.get_sheet(self.SHEET_WHITELIST['scene_fingerprints'])
        return SceneFingerprints(
            sheet=sheet,
            skip_done=skip_done,
            skip_no_correct_scene=skip_no_correct_scene,
        )

    def performers_to_split_up(self, skip_done: bool = True):
        """
        NOTE: PARTIAL EXTRACTOR

        Args:
            skip_done - Skip rows and/or cells that are marked as done.
        """
        from .sheets.performers_to_split_up import PerformersToSplitUp
        sheet = self.interface.get_sheet(self.SHEET_WHITELIST['performers_to_split_up'])
        return PerformersToSplitUp(
            sheet=sheet,
            skip_done=skip_done,
        )
