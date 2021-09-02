import argparse
from typing import Callable

from .utils import get_google_api_key


def main_export_sheet_data():
    from . import export_sheet_data, extract, paths

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
        data = export_sheet_data.DuplicatePerformers()
        data.write(paths.path_duplicate_performers)
        print(f'Success: {len(data)} performer entries')

    def main_scene_fingerprints():
        data = export_sheet_data.SceneFingerprints()
        data.write(paths.path_scene_fingerprints)
        print(f'Success: {len(data)} scene entries')

    def main_performers_to_split_up():
        data = export_sheet_data.PerformersToSplitUp()
        data.write(paths.path_performers_to_split_up)
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

    subparsers.add_parser(name='ps', help="Performers To Split Up") \
        .set_defaults(main_method=main_performers_to_split_up)

    args = parser.parse_args(namespace=Arguments())

    kwargs = {
        k: v for k, v in args.__dict__.items()
        if k not in Arguments.__annotations__
    }

    api_key = None if args.legacy else get_google_api_key()
    api = extract.BacklogExtractor(api_key=api_key)

    args.main_method(**kwargs)
