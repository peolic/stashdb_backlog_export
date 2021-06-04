#!/usr/bin/env python3.8
# coding: utf-8
import json
import re
from pathlib import Path
from typing import Any, Dict, List


from pkg.export_sheet_data import ScenePerformers, SceneFixes


def main():
    script_dir = Path(__file__).parent

    target = script_dir / 'stashdb_backlog.json'

    scene_performers = ScenePerformers(skip_no_id=False)
    scene_fixes = SceneFixes(reuse_soup=scene_performers.soup)

    scenes: Dict[str, Dict[str, Any]] = {}

    for scene_id, fixes in scene_fixes:
        change = scenes.setdefault(scene_id, {})
        for fix in fixes:
            change[fix['field']] = fix['new_data']
            if (correction := fix['correction']) and (urls := re.findall(r'(https?://[^\s]+)', correction)):
                comments: List[str] = change.setdefault('comments', [])
                comments.extend(urls)


    for item in scene_performers:
        change = scenes.setdefault(item['scene_id'], {})
        change['performers'] = {}
        change['performers']['remove'] = item['remove']
        change['performers']['append'] = item['append']
        if update := item.get('update'):
            change['performers']['update'] = update
        if comment := item.get('comment'):
            comments: List[str] = change.setdefault('comments', [])
            comments.append(comment)

    data = dict(scenes=scenes, performers={})
    target.write_bytes(json.dumps(data, indent=2).encode('utf-8'))
    print('done')


if __name__ == '__main__':
    main()
