#!/usr/bin/env python3.11
# coding: utf-8
import yaml

from make_backlog_data import (
    TCacheData,
    TSubmitted,
    cache_to_json,
    export_cache_format,
    performers_target,
    scenes_target,
    script_dir,
    submitted_target,
)

def main():
    print('collecting information...')

    scenes: TCacheData = {
        fp.stem: yaml.safe_load(fp.read_bytes())
        for fp in scenes_target.glob('*/*.yml')
    }
    performers: TCacheData = {
        fp.stem: yaml.safe_load(fp.read_bytes())
        for fp in performers_target.glob('*/*.yml')
    }

    submitted: TSubmitted = yaml.safe_load(submitted_target.read_bytes())

    cache_data = export_cache_format({'scenes': scenes, 'performers': performers}, submitted=submitted)
    (script_dir / 'stashdb_backlog.json').write_bytes(cache_to_json(cache_data, True))

    print('done')


if __name__ == '__main__':
    main()
