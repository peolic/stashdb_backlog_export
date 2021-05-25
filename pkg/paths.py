from pathlib import Path

script_dir = Path(__file__).parent

path_scene_performers = (script_dir / '../scene_performers.json').resolve()
path_scene_fixes = (script_dir / '../scene_fixes.json').resolve()
path_duplicate_scenes = (script_dir / '../duplicate_scenes.json').resolve()
path_duplicate_performers = (script_dir / '../duplicate_performers.json').resolve()
