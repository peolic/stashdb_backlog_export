#!/usr/bin/env python3.8
# coding: utf-8
import base64
import hashlib
import json
import operator
import os
import re
import sys
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from shutil import rmtree
from typing import Any, Callable, Dict, List, Union

from pkg.export_sheet_data import (
    DuplicatePerformers,
    DuplicateScenes,
    PerformersToSplitUp,
    SceneFingerprints,
    ScenePerformers,
    SceneFixes,
)


def get_data():
    print('fetching information...')

    scene_performers = ScenePerformers(skip_no_id=False)
    scene_fixes = SceneFixes(reuse_soup=scene_performers.soup)
    scene_fingerprints = SceneFingerprints(skip_no_correct_scene=False, reuse_soup=scene_performers.soup)
    duplicate_scenes = DuplicateScenes(reuse_soup=scene_performers.soup)
    performers_to_split_up = PerformersToSplitUp(reuse_soup=scene_performers.soup)
    duplicate_performers = DuplicatePerformers(reuse_soup=scene_performers.soup)

    print('processing information...')

    scenes: Dict[str, Dict[str, Any]] = {}

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
                studio_name = pattern_comment_delimiter.split(correction)[0] if correction else None
                change['studio'] = [new_data, studio_name]
            else:
                change[field] = new_data

            if correction:
                if field in ('date',):
                    filtered = pattern_comment_delimiter.split(correction)
                else:
                    filtered = pattern_find_urls.findall(correction)

                if filtered:
                    comments: List[str] = change.setdefault('comments', [])
                    comments[:] = list(dict.fromkeys(comments + filtered))

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
            comments[:] = list(dict.fromkeys(comments + pattern_comment_delimiter.split(comment)))

    def get_keys(entry: Dict[str, Any]):
        return [make_short_hash(entry), *(k for k in sorted(entry.keys()) if k != 'comments')]

    # "scene_id": [content_hash, "date", "performers", "title"]
    scenes_index = dict(sorted(zip(
        scenes.keys(),
        map(get_keys, scenes.values()),
    )))

    performers: Dict[str, Dict[str, Any]] = {}

    for p in duplicate_performers:
        main_id = p['main_id']
        performer = performers.setdefault(main_id, {})
        performer['duplicates'] = p['duplicates'][:]
        for dup in p['duplicates']:
            dup_performer = performers.setdefault(dup, {})
            dup_performer['duplicate_of'] = main_id

    # "performer_id": [content_hash, "duplicates", "split"]
    performers_index = dict(sorted(zip(
        performers.keys(),
        map(get_keys, performers.values()),
    )))

    for item in performers_to_split_up:
        performer = performers_index.setdefault(item['main_id'], [''])  # empty content hash
        performer[1:] = sorted(['split'] + performer[1:])

    performers_index = dict(sorted(performers_index.items()))

    index: Dict[str, Dict[str, List[str]]] = dict(scenes=scenes_index, performers=performers_index)

    return index, scenes, performers


def main():
    script_dir = Path(__file__).parent

    target_path = script_dir / 'backlog_data'
    index_path = target_path / 'index.json'
    scenes_target = target_path / 'scenes'
    performers_target = target_path / 'performers'

    index, scenes, performers = get_data()

    CI = os.environ.get('CI') == 'true' or 'ci' in sys.argv[1:]
    CACHE_ONLY = 'cache' in sys.argv[1:]

    if not CACHE_ONLY:
        index_path.write_bytes(json.dumps(index, indent=2, cls=CompactJSONEncoder).encode('utf-8'))
    if CI or CACHE_ONLY:
        index['lastChecked'] = make_timestamp()  # type: ignore
        index['lastUpdated'] = make_timestamp()  # type: ignore
        (script_dir / '.stashdb_backlog_index.json') \
            .write_bytes(json.dumps(index, indent=2, cls=CompactJSONEncoder).encode('utf-8'))

    def make_object_path(uuid: str) -> str:
        return f'{uuid[:2]}/{uuid}.json'

    def with_sorted_toplevel_keys(data: Dict[str, Any]) -> Dict[str, Any]:
        return dict(sorted(data.items(), key=operator.itemgetter(0)))

    if CI or CACHE_ONLY:
        export_cache_format(
            script_dir / '.stashdb_backlog.json',
            dict(scenes=scenes, performers=performers),
            with_sorted_toplevel_keys,
        )
        if CACHE_ONLY:
            return

    with suppress(FileNotFoundError):
        rmtree(scenes_target)

    for scene_id, scene in scenes.items():
        scene_path = scenes_target / make_object_path(scene_id)
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        scene_data = with_sorted_toplevel_keys(scene)
        scene_path.write_bytes(json.dumps(scene_data, indent=2).encode('utf-8'))

    with suppress(FileNotFoundError):
        rmtree(performers_target)

    for performer_id, performer in performers.items():
        performer_path = performers_target / make_object_path(performer_id)
        performer_path.parent.mkdir(parents=True, exist_ok=True)
        performer_data = with_sorted_toplevel_keys(performer)
        performer_path.write_bytes(json.dumps(performer_data, indent=2).encode('utf-8'))

    print('done')


# Hashing based on https://stackoverflow.com/a/42151923
def make_short_hash(o):
    hasher = hashlib.md5()
    hasher.update(repr(make_hashable(o)).encode())
    return base64.b64encode(hasher.digest()).decode()

def make_hashable(o):
    if isinstance(o, (tuple, list)):
        return tuple((make_hashable(e) for e in o))

    if isinstance(o, dict):
        return tuple(sorted((k, make_hashable(v)) for k,v in o.items()))

    if isinstance(o, (set, frozenset)):
        return tuple(sorted(make_hashable(e) for e in o))

    return o


def make_timestamp() -> str:
    return datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'


TAnyDict = Dict[str, Any]
TCacheData = Dict[str, TAnyDict]

def export_cache_format(target: Path, objects: Dict[str, TCacheData], contents_func: Callable[[TAnyDict], TAnyDict]):
    data: TCacheData = {}
    for obj, obj_data in objects.items():
        for obj_id, item in obj_data.items():
            key = f'{obj[:-1]}/{obj_id}'
            data[key] = contents_func(item)
            data[key]['lastUpdated'] = make_timestamp()
            data[key]['contentHash'] = make_short_hash(item)
    target.write_bytes(json.dumps(data, indent=2, cls=CompactJSONEncoder).encode('utf-8'))


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
