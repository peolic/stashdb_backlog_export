import argparse
from typing import Callable


def main_export_sheet_data():
    from .export_sheet_data import (
        main_scene_performers,
        main_scenes_fixes,
        main_duplicate_scenes,
        main_duplicate_performers,
    )

    class Arguments(argparse.Namespace):
        main_method: Callable[[], None]

    parser = argparse.ArgumentParser('Extract Sheet Data')
    subparsers = parser.add_subparsers(help='What')
    parser.set_defaults(main_method=main_scene_performers)

    sp_parser = subparsers.add_parser(name='sp', help="Scene-Performers (Default)")
    sp_parser.set_defaults(main_method=main_scene_performers)

    sf_parser = subparsers.add_parser(name='sf', help="Scene Fixes")
    sf_parser.set_defaults(main_method=main_scenes_fixes)

    ds_parser = subparsers.add_parser(name='ds', help="Duplicate Scenes")
    ds_parser.set_defaults(main_method=main_duplicate_scenes)

    dp_parser = subparsers.add_parser(name='dp', help="Duplicate Performers")
    dp_parser.set_defaults(main_method=main_duplicate_performers)

    args = parser.parse_args(namespace=Arguments())

    args.main_method()
