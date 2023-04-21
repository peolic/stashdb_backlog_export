import os
import re
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from .models import AnyPerformerEntry, ScenePerformersItem
from .paths import script_dir

UUID_PATTERN = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
STASHDB_UUID_PATTERN = re.compile(rf'/([a-z]+)/({UUID_PATTERN.pattern})')
URL_PATTERN = re.compile(r'(https?://[^\s]+)')


def is_uuid(text: str) -> bool:
    return UUID_PATTERN.fullmatch(text) is not None


def parse_duration(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    try:
        parts = text.split(':')
    except AttributeError:
        return None

    parts[0:0] = ('0',) * (3 - len(parts))
    (hours, minutes, seconds) = [int(i) for i in parts]
    return hours * 3600 + minutes * 60 + seconds


def parse_stashdb_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    if match := STASHDB_UUID_PATTERN.search(url):
        return match.group(1), match.group(2)

    return None, None


def first_performer_name(item: ScenePerformersItem, entry_type: Literal['update', 'append', 'remove']) -> str:
    try:
        entries = item.get(entry_type, [])
        return entries[0]['name']
    except IndexError:
        return ''


def get_all_entries(item: ScenePerformersItem) -> List[AnyPerformerEntry]:
    remove, append, update = item['remove'], item['append'], item.get('update', [])
    return remove + append + update  # type: ignore


def performer_name(p: AnyPerformerEntry) -> str:
    p_name = p['name']
    p_dsmbg = p.get('disambiguation')
    p_as = p['appearance']

    parts = []

    if p_as:
        parts.extend((p_as, f'({p_name})'))
    elif p_dsmbg:
        parts.extend((p_name, f'[{p_dsmbg}]'))
    else:
        parts.append(p_name)

    return ' '.join(parts)


def format_studio(item: ScenePerformersItem) -> Optional[str]:
    if not (studio := item['studio']):
        return None

    if parent_studio := item.get('parent_studio'):
        return f'{studio} [{parent_studio}]'

    return studio


def get_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    try:
        dotenv = Path(script_dir / '.env').read_text()
    except FileNotFoundError:
        return env

    for line in dotenv.splitlines():
        if not line.startswith('#'):
            key, value = line.split('=')
            env[key] = value
    return env

def get_google_api_key() -> Optional[str]:
    if api_key := os.environ.get('GOOGLE_API_KEY'):
        return api_key

    return get_env().get('GOOGLE_API_KEY')

def get_proxy() -> Optional[str]:
    if proxy := os.environ.get('PROXY'):
        return proxy

    return get_env().get('PROXY')
