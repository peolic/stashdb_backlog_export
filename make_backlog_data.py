#!/usr/bin/env python3.8
# coding: utf-8
import base64
import hashlib
import json
import re
from contextlib import suppress
from pathlib import Path
from shutil import rmtree
from typing import Any, Dict, List, Union

from pkg.export_sheet_data import PerformerToSplitUp, ScenePerformers, SceneFixes


def main():
    script_dir = Path(__file__).parent

    target_path = script_dir / 'backlog_data'

    scenes_target = target_path / 'scenes'
    # performers_target = target_path / 'performers'

    index_path = target_path / 'index.json'

    print('fetching information...')

    scene_performers = ScenePerformers(skip_no_id=False)
    scene_fixes = SceneFixes(reuse_soup=scene_performers.soup)
    performers_to_split_up = PerformerToSplitUp(reuse_soup=scene_performers.soup)

    scene_performers.sort()
    performers_to_split_up.sort()

    print('processing information...')

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
        return [make_short_hash(entry), *(k for k in sorted(entry.keys()) if k != 'comments')]

    # "scene_id": [content_hash, "date", "performers", "title"]
    scenes_index = dict(zip(
        scenes.keys(),
        map(get_keys, scenes.values()),
    ))

    # "performer_id": "split"
    performers_index = {
        item['main_id']: 'split'
        for item in performers_to_split_up
    }

    index = dict(scenes=scenes_index, performers=performers_index)
    index_path.write_bytes(json.dumps(index, indent=2, cls=CompactJSONEncoder).encode('utf-8'))

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
        elif isinstance(o, str):  # escape newlines
            o = o.replace("\n", "\\n")
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
