from pathlib import Path

script_dir = Path(__file__).parent

path_scene_performers = (script_dir / '../scene_performers.json').resolve()
path_scene_fixes = (script_dir / '../scene_fixes.json').resolve()
path_duplicate_scenes = (script_dir / '../duplicate_scenes.json').resolve()
path_duplicate_performers = (script_dir / '../duplicate_performers.json').resolve()
path_scene_fingerprints = (script_dir / '../scene_fingerprints.json').resolve()
path_performers_to_split_up = (script_dir / '../performers_to_split_up.json').resolve()
path_performer_urls = (script_dir / '../performer_urls.json').resolve()
