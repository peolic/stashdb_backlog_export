#!/usr/bin/env python3.8
# coding: utf-8
import json
import os
import re
import sys
from contextlib import suppress
from datetime import datetime, timedelta
from itertools import groupby
from operator import itemgetter
from pathlib import Path
from shutil import rmtree
from typing import Any, Dict, Iterable, List, Tuple, Union

from extract import BacklogExtractor
from extract.utils import get_google_api_key

TAnyDict = Dict[str, Any]
TCacheData = Dict[str, TAnyDict]


def get_data():
    print('fetching information...')

    api = BacklogExtractor(api_key=get_google_api_key())

    print('>>> Scene-Performers')
    scene_performers = api.scene_performers(skip_no_id=False)
    print('>>> Scene Fixes')
    scene_fixes = api.scene_fixes()
    print('>>> Scene Fingerprints')
    scene_fingerprints = api.scene_fingerprints(skip_no_correct_scene=False)
    print('>>> Duplicate Scenes')
    duplicate_scenes = api.duplicate_scenes()
    print('>>> Performers To Split Up')
    performers_to_split_up = api.performers_to_split_up()
    print('>>> Duplicate Performers')
    duplicate_performers = api.duplicate_performers()

    print('processing information...')

    scenes: TCacheData = {}

    pattern_find_urls = re.compile(r'(https?://[^\s]+)')
    pattern_comment_delimiter = re.compile(r' ; | *\n')

    for scene_id, fixes in scene_fixes:
        change = scenes.setdefault(scene_id, {})
        for fix in fixes:
            field = fix['field']
            new_data = fix['new_data']
            correction = fix['correction']

            # "studio_id": <uuid> => "studio": [<uuid>, <studio-name>]
            if field == 'studio_id':
                studio_name = None
                if correction:
                    lines = pattern_comment_delimiter.split(correction)
                    if lines and not lines[0].startswith(('http://', 'https://')):
                        studio_name = lines[0]
                change['studio'] = [new_data, studio_name]
            else:
                change[field] = new_data

            if correction:
                lc = correction.strip().lower()
                full_comment = (
                    field in ('date', )
                    or (field == 'image' and lc != 'missing image')
                )
                if full_comment:
                    filtered = pattern_comment_delimiter.split(correction)
                else:
                    filtered = pattern_find_urls.findall(correction)

                if filtered:
                    comments: List[str] = change.setdefault('comments', [])
                    comments[:] = filter_empty(dict.fromkeys(comments + filtered))

    for scene_id, fingerprints in scene_fingerprints:
        change = scenes.setdefault(scene_id, {})
        change['fingerprints'] = fingerprints

    for ds_item in duplicate_scenes:
        main_id = ds_item['main_id']
        scene = scenes.setdefault(main_id, {})
        scene['duplicates'] = (
            list(dict.fromkeys(scene['duplicates'] + ds_item['duplicates']))
            if 'duplicates' in scene else
            ds_item['duplicates'][:]
        )
        for dup in ds_item['duplicates']:
            dup_scene = scenes.setdefault(dup, {})
            dup_scene['duplicate_of'] = main_id

    for item in scene_performers:
        change = scenes.setdefault(item['scene_id'], {})
        change['performers'] = {}
        change['performers']['remove'] = item['remove']
        change['performers']['append'] = item['append']
        if update := item.get('update'):
            change['performers']['update'] = update
        if comment := item.get('comment'):
            comments: List[str] = change.setdefault('comments', [])
            comments[:] = filter_empty(dict.fromkeys(comments + pattern_comment_delimiter.split(comment)))

    performers: TCacheData = {}

    for item in performers_to_split_up:
        p_id = item['main_id']
        performer = performers.setdefault(p_id, {})
        if 'split' in performer:
            print(f'WARNING: Duplicate Performers-To-Split-Up entry found: {p_id}')
            continue
        performer['split'] = {}

    for p in duplicate_performers:
        main_id = p['main_id']
        performer = performers.setdefault(main_id, {})
        if 'duplicates' in performer:
            print(f'WARNING: Duplicate "Duplicate Performers" entry found: {main_id}')
            continue
        duplicates = performer['duplicates'] = {}
        duplicates['ids'] = p['duplicates'][:]
        if notes := p.get('notes'):
            duplicates['notes'] = notes
        for dup in p['duplicates']:
            dup_performer = performers.setdefault(dup, {})
            dup_performer['duplicate_of'] = main_id

    return scenes, performers


def main():
    script_dir = Path(__file__).parent

    target_path = script_dir / 'backlog_data'
    scenes_target = target_path / 'scenes'
    performers_target = target_path / 'performers'

    scenes, performers = get_data()

    CI = os.environ.get('CI') == 'true' or 'ci' in sys.argv[1:]
    CACHE_ONLY = 'cache' in sys.argv[1:]

    def cache_to_json(data: TAnyDict) -> bytes:
        indent = None if CI else 2
        separators = (',', ':') if CI else None
        cls = None if CI else CompactJSONEncoder
        return json.dumps(data, indent=indent, separators=separators, cls=cls).encode('utf-8')

    cache_target = script_dir
    if CACHE_ONLY:
        cache_target = script_dir / 'cache'
        cache_target.mkdir(exist_ok=True)

    if CI or CACHE_ONLY:
        cache_data = export_cache_format(dict(scenes=scenes, performers=performers))
        (cache_target / 'stashdb_backlog.json').write_bytes(cache_to_json(cache_data))
        if CACHE_ONLY:
            return

    with suppress(FileNotFoundError):
        rmtree(scenes_target)

    scenes_target.mkdir(parents=True, exist_ok=True)
    for target, data in make_groups(scenes, scenes_target):
        target.write_bytes(json.dumps(data, indent=2).encode('utf-8'))

    with suppress(FileNotFoundError):
        rmtree(performers_target)

    performers_target.mkdir(parents=True, exist_ok=True)
    for target, data in make_groups(performers, performers_target):
        target.write_bytes(json.dumps(data, indent=2).encode('utf-8'))

    print('done')


def filter_empty(it: Iterable[str]) -> List[str]:
    return list(filter(str.strip, it))


def make_timestamp(add_seconds: int = 0) -> str:
    dt = datetime.utcnow()
    if add_seconds:
        dt += timedelta(seconds=add_seconds)
    return dt.isoformat(timespec='milliseconds') + 'Z'


def get_prefix(item: Tuple[str, Any]):
    key, value = item
    return key[:2]


def with_sorted_toplevel_keys(data: TAnyDict) -> TAnyDict:
    return dict(sorted(data.items(), key=itemgetter(0)))


def make_groups(dataset: TCacheData, target_base: Path):
    sorted_data = sorted(dataset.items(), key=itemgetter(0))
    for group, items in groupby(sorted_data, get_prefix):
        target = target_base / f'{group}.json'
        data = {
            item_id: with_sorted_toplevel_keys(item)
            for item_id, item in items
        }
        yield target, data


def export_cache_format(objects: Dict[str, TCacheData]):
    data: TCacheData = {}
    for obj, obj_data in objects.items():
        for obj_id, item in obj_data.items():
            key = f'{obj[:-1]}/{obj_id}'
            data[key] = with_sorted_toplevel_keys(item)
    data['lastUpdated'] = make_timestamp(10)  # type: ignore
    data['lastChecked'] = make_timestamp()  # type: ignore
    return data

# https://gist.github.com/jannismain/e96666ca4f059c3e5bc28abb711b5c92
class CompactJSONEncoder(json.JSONEncoder):
    """A JSON Encoder that puts small containers on single lines."""

    CONTAINER_TYPES = (list, tuple, dict)
    """Container datatypes include primitives or other containers."""

    MAX_WIDTH = 200
    """Maximum width of a container that might be put on a single line."""

    MAX_ITEMS = 20
    """Maximum number of items in container that might be put on single line."""

    INDENTATION_CHAR = " "

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.indentation_level = 0

    def encode(self, o):
        """Encode JSON object *o* with respect to single line lists."""
        if isinstance(o, (list, tuple)):
            if self._put_on_single_line(o):
                return "[" + ", ".join(self.encode(el) for el in o) + "]"
            else:
                self.indentation_level += 1
                output = [self.indent_str + self.encode(el) for el in o]
                self.indentation_level -= 1
                return "[\n" + ",\n".join(output) + "\n" + self.indent_str + "]"
        elif isinstance(o, dict):
            if o:
                if self._put_on_single_line(o):
                    return "{ " + ", ".join(f"{self.encode(k)}: {self.encode(el)}" for k, el in o.items()) + " }"
                else:
                    self.indentation_level += 1
                    output = [self.indent_str + f"{json.dumps(k)}: {self.encode(v)}" for k, v in o.items()]
                    self.indentation_level -= 1
                    return "{\n" + ",\n".join(output) + "\n" + self.indent_str + "}"
            else:
                return "{}"
        elif isinstance(o, float):  # Use scientific notation for floats, where appropiate
            return format(o, "g")
        elif isinstance(o, str):
            # escape newlines
            o = o.replace("\n", "\\n")
            # escape quotes
            o = o.replace('"', '\\"')
            return f'"{o}"'
        else:
            return json.dumps(o)

    def _put_on_single_line(self, o):
        return self._primitives_only(o) and len(o) <= self.MAX_ITEMS and len(str(o)) - 2 <= self.MAX_WIDTH

    def _primitives_only(self, o: Union[list, tuple, dict]):
        if isinstance(o, (list, tuple)):
            return not any(isinstance(el, self.CONTAINER_TYPES) for el in o)
        elif isinstance(o, dict):
            return not any(isinstance(el, self.CONTAINER_TYPES) for el in o.values())

    @property
    def indent_str(self) -> str:
        return self.INDENTATION_CHAR*(self.indentation_level*self.indent)


if __name__ == '__main__':
    main()
