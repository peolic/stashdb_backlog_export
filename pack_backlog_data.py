#!/usr/bin/env python3.11
# coding: utf-8
import json
from typing import Dict, List

from make_backlog_data import (
    TCacheData,
    cache_to_json,
    export_cache_format,
    performers_target,
    scenes_target,
    script_dir,
    submitted_target,
)


def get_data():
    print('collecting information...')

    scenes: TCacheData = {
        fp.stem: json.loads(fp.read_bytes())
        for fp in scenes_target.glob('*/*.json')
    }
    performers: TCacheData = {
        fp.stem: json.loads(fp.read_bytes())
        for fp in performers_target.glob('*/*.json')
    }

    submitted: Dict[str, List[str]] = json.loads(submitted_target.read_bytes())

    return scenes, performers, submitted


def main():
    scenes, performers, submitted = get_data()
    submitted_scenes = dict.fromkeys(submitted['scenes'])

    cache_data = export_cache_format(dict(scenes=scenes, performers=performers), submitted=submitted_scenes)
    (script_dir / 'stashdb_backlog.json').write_bytes(cache_to_json(cache_data, True))

    print('done')


if __name__ == '__main__':
    main()
