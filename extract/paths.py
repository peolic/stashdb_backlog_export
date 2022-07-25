from pathlib import Path

module_dir = Path(__file__).resolve().parent
script_dir = module_dir.parent

path_scene_performers = module_dir / 'scene_performers.json'
path_scene_fixes = module_dir / 'scene_fixes.json'
path_duplicate_scenes = module_dir / 'duplicate_scenes.json'
path_duplicate_performers = module_dir / 'duplicate_performers.json'
path_scene_fingerprints = module_dir / 'scene_fingerprints.json'
path_performers_to_split_up = module_dir / 'performers_to_split_up.json'
path_performer_urls = module_dir / 'performer_urls.json'
