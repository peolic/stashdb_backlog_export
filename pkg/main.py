import argparse
from typing import Callable


def main_export_sheet_data():
    from . import export_sheet_data, paths

    def main_scene_performers():
        data = export_sheet_data.ScenePerformers()
        data.write(paths.path_scene_performers)
        print(f'Success: {len(data)} scene entries')

    def main_scenes_fixes():
        data = export_sheet_data.SceneFixes()
        data.write(paths.path_scene_fixes)
        print(f'Success: {len(data)} scene entries')

    def main_duplicate_scenes():
        data = export_sheet_data.DuplicateScenes()
        data.write(paths.path_duplicate_scenes)
        print(f'Success: {len(data)} scene entries')

    def main_duplicate_performers():
        data = export_sheet_data.DuplicatePerformers()
        data.write(paths.path_duplicate_performers)
        print(f'Success: {len(data)} performer entries')

    def main_performers_to_split_up():
        data = export_sheet_data.PerformersToSplitUp()
        data.write(paths.path_performers_to_split_up)
        print(f'Success: {len(data)} performer entries')

    class Arguments(argparse.Namespace):
        main_method: Callable[[], None]

    parser = argparse.ArgumentParser('Extract Sheet Data')
    subparsers = parser.add_subparsers(help='What')
    parser.set_defaults(main_method=main_scene_performers)

    subparsers.add_parser(name='sp', help="Scene-Performers (Default)") \
        .set_defaults(main_method=main_scene_performers)

    subparsers.add_parser(name='sf', help="Scene Fixes") \
        .set_defaults(main_method=main_scenes_fixes)

    subparsers.add_parser(name='ds', help="Duplicate Scenes") \
        .set_defaults(main_method=main_duplicate_scenes)

    subparsers.add_parser(name='dp', help="Duplicate Performers") \
        .set_defaults(main_method=main_duplicate_performers)

    subparsers.add_parser(name='ps', help="Performers To Split Up") \
        .set_defaults(main_method=main_performers_to_split_up)

    args = parser.parse_args(namespace=Arguments())

    args.main_method()
