import argparse
import os
from typing import Callable

from . import BacklogExtractor, paths
from .utils import get_google_api_key, get_proxy

def main():
    def main_scene_performers(**kwargs):
        data = api.scene_performers(**kwargs)
        data.write(paths.path_scene_performers)
        print(f'Success: {len(data)} scene entries')

    def main_scenes_fixes():
        data = api.scene_fixes()
        data.write(paths.path_scene_fixes)
        print(f'Success: {len(data)} scene entries')

    def main_duplicate_scenes():
        data = api.duplicate_scenes()
        data.write(paths.path_duplicate_scenes)
        print(f'Success: {len(data)} scene entries')

    def main_duplicate_performers():
        data = api.duplicate_performers()
        data.write(paths.path_duplicate_performers)
        print(f'Success: {len(data)} performer entries')

    def main_scene_fingerprints():
        data = api.scene_fingerprints()
        data.write(paths.path_scene_fingerprints)
        print(f'Success: {len(data)} scene entries')

    def main_performers_to_split_up(**kwargs):
        data = api.performers_to_split_up(**kwargs)
        data.write(paths.path_performers_to_split_up)
        print(f'Success: {len(data)} performer entries')

    def main_performer_urls():
        data = api.performer_urls()
        data.write(paths.path_performer_urls)
        print(f'Success: {len(data)} performer entries')

    class Arguments(argparse.Namespace):
        main_method: Callable[[], None]
        legacy: bool

    parser = argparse.ArgumentParser('Extract Sheet Data')
    parser.set_defaults(main_method=main_scene_performers)
    parser.add_argument('-l', '--legacy', action='store_true', help='Force legacy extractor.')

    subparsers = parser.add_subparsers(help='What')

    sp_parser = subparsers.add_parser(name='sp', help="Scene-Performers (Default)")
    sp_parser.set_defaults(main_method=main_scene_performers)
    sp_parser.add_argument(
        '-id', '--include-no-id', dest='skip_no_id', action='store_false',
        help="Skip items completely if at least one if the performers' IDs could not be extracted",
    )

    subparsers.add_parser(name='sf', help="Scene Fixes") \
        .set_defaults(main_method=main_scenes_fixes)

    subparsers.add_parser(name='ds', help="Duplicate Scenes") \
        .set_defaults(main_method=main_duplicate_scenes)

    subparsers.add_parser(name='dp', help="Duplicate Performers") \
        .set_defaults(main_method=main_duplicate_performers)

    subparsers.add_parser(name='sfp', help="Scene Fingerprints") \
        .set_defaults(main_method=main_scene_fingerprints)

    ps_parser = subparsers.add_parser(name='ps', help="Performers To Split Up")
    ps_parser.set_defaults(main_method=main_performers_to_split_up)
    ps_parser.add_argument(
        '-d', '--include-done', dest='skip_done_rows', action='store_false',
        help="Skip items that are marked as completed",
    )
    ps_parser.add_argument(
        '-df', '--include-done-fragments', dest='skip_done_fragments', action='store_false',
        help="Skip fragments that are marked as completed",
    )

    subparsers.add_parser(name='pu', help="Performer URLs") \
        .set_defaults(main_method=main_performer_urls)

    args = parser.parse_args(namespace=Arguments())

    kwargs = {
        k: v for k, v in args.__dict__.items()
        if k not in Arguments.__annotations__
    }

    api_key = None if args.legacy else get_google_api_key()

    if proxy := get_proxy():
        os.environ['ALL_PROXY'] = proxy

    api = BacklogExtractor(api_key=api_key)

    args.main_method(**kwargs)
