#!/usr/bin/env python3.8
# coding: utf-8
import json
import re
from contextlib import suppress
from pathlib import Path
from shutil import rmtree
from typing import Any, Dict, List

from pkg.export_sheet_data import PerformerToSplitUp, ScenePerformers, SceneFixes


def main():
    script_dir = Path(__file__).parent

    target_path = script_dir / 'backlog_data'

    scenes_target = target_path / 'scenes'
    # performers_target = target_path / 'performers'

    index_path = target_path / 'index.json'

    scene_performers = ScenePerformers(skip_no_id=False)
    scene_fixes = SceneFixes(reuse_soup=scene_performers.soup)
    performers_to_split_up = PerformerToSplitUp(reuse_soup=scene_performers.soup)

    scene_performers.data.sort(key=scene_performers.sort_key)

    scenes: Dict[str, Dict[str, Any]] = {}

    pattern_find_urls = re.compile(r'(https?://[^\s]+)')

    for scene_id, fixes in scene_fixes:
        change = scenes.setdefault(scene_id, {})
        for fix in fixes:
            change[fix['field']] = fix['new_data']
            if (correction := fix['correction']) and (urls := pattern_find_urls.findall(correction)):
                comments: List[str] = change.setdefault('comments', [])
                comments[:] = list(dict.fromkeys(comments + urls))

    pattern_comment_delimiter = re.compile(r' [;\n] ')

    for item in scene_performers:
        change = scenes.setdefault(item['scene_id'], {})
        change['performers'] = {}
        change['performers']['remove'] = item['remove']
        change['performers']['append'] = item['append']
        if update := item.get('update'):
            change['performers']['update'] = update
        if comment := item.get('comment'):
            comments: List[str] = change.setdefault('comments', [])
            comments[:] = list(dict.fromkeys(comments + pattern_comment_delimiter.split(comment)))

    def get_keys(entry: Dict[str, Any]):
        return ','.join(k for k in sorted(entry.keys()) if k != 'comments')

    # "scene_id": "title,date,performers"
    scenes_index = dict(zip(
        scenes.keys(),
        map(get_keys, scenes.values()),
    ))

    # "performer_id": "split"
    performers_index = {
        uuid: 'split'
        for uuid in performers_to_split_up
    }

    index = dict(scenes=scenes_index, performers=performers_index)
    index_path.write_bytes(json.dumps(index, indent=2).encode('utf-8'))

    def make_object_path(uuid: str) -> str:
        return f'{uuid[:2]}/{uuid}.json'

    def with_sorted_toplevel_keys(data: Dict[str, Any]) -> Dict[str, Any]:
        return dict(sorted(data.items(), key=lambda p: p[0]))

    with suppress(FileNotFoundError):
        rmtree(scenes_target)

    for scene_id, scene in scenes.items():
        scene_path = scenes_target / make_object_path(scene_id)
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        scene_data = with_sorted_toplevel_keys(scene)
        scene_path.write_bytes(json.dumps(scene_data, indent=2).encode('utf-8'))

    # with suppress(FileNotFoundError):
    #     rmtree(performers_target)

    print('done')


if __name__ == '__main__':
    main()
