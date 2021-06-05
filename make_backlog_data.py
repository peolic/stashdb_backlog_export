#!/usr/bin/env python3.8
# coding: utf-8
import json
import re
from contextlib import suppress
from pathlib import Path
from shutil import rmtree
from typing import Any, Dict, List


from pkg.export_sheet_data import ScenePerformers, SceneFixes


def main():
    script_dir = Path(__file__).parent

    target_path = script_dir / 'backlog_data'

    scenes_target = target_path / 'scenes'
    with suppress(FileNotFoundError):
        rmtree(scenes_target)

    # performers_target = target_path / 'performers'
    # with suppress(FileNotFoundError):
    #     rmtree(performers_target)

    index_path = target_path / 'index.json'

    scene_performers = ScenePerformers(skip_no_id=False)
    scene_fixes = SceneFixes(reuse_soup=scene_performers.soup)

    scenes: Dict[str, Dict[str, Any]] = {}

    for scene_id, fixes in scene_fixes:
        change = scenes.setdefault(scene_id, {})
        for fix in fixes:
            change[fix['field']] = fix['new_data']
            if (correction := fix['correction']) and (urls := re.findall(r'(https?://[^\s]+)', correction)):
                comments: List[str] = change.setdefault('comments', [])
                comments[:] = list(dict.fromkeys(comments + urls))


    for item in scene_performers:
        change = scenes.setdefault(item['scene_id'], {})
        change['performers'] = {}
        change['performers']['remove'] = item['remove']
        change['performers']['append'] = item['append']
        if update := item.get('update'):
            change['performers']['update'] = update
        if comment := item.get('comment'):
            comments: List[str] = change.setdefault('comments', [])
            comments[:] = list(dict.fromkeys(comments + [comment]))

    index = dict(scenes=list(scenes.keys()), performers=[])
    index_path.write_bytes(json.dumps(index, indent=2).encode('utf-8'))

    def make_object_path(uuid: str) -> str:
        return f'{uuid[:2]}/{uuid}.json'

    for scene_id, scene in scenes.items():
        scene_path = scenes_target / make_object_path(scene_id)
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        scene_path.write_bytes(json.dumps(scene, indent=2).encode('utf-8'))

    print('done')


if __name__ == '__main__':
    main()
