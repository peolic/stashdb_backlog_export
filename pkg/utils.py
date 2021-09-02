import os
import re
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple
from urllib.parse import parse_qsl, urlparse

from bs4.element import Tag

from .models import AnyPerformerEntry, ScenePerformersItem

script_dir = Path(__file__).parent

_uuid = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
UUID_PATTERN = re.compile(_uuid)
STASHDB_UUID_PATTERN = re.compile(r'/([a-z]+)/(' + _uuid + r')')


def is_uuid(text: str) -> bool:
    return UUID_PATTERN.fullmatch(text) is not None


def parse_google_redirect_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None

    try:
        url_p = urlparse(url)

        if url_p.hostname == 'www.google.com' and url_p.path == '/url':
            url_r = dict(parse_qsl(url_p.query))['q']
            url = urlparse(url_r).geturl()

        return url

    except (ValueError, KeyError):
        return None


def get_cell_url(cell: Tag) -> Optional[str]:
    try:
        return parse_google_redirect_url(
            cell.select_one('a').attrs['href']  # type: ignore
        )
    except (AttributeError, KeyError):
        return None


def get_multiline_text(cell: Tag, **get_text_kwargs) -> str:
    for br in cell.find_all('br'):
        br.replace_with('\n')  # type: ignore
    return cell.get_text(**get_text_kwargs)


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


def format_performer(action: str, p: AnyPerformerEntry, with_id: bool = True) -> str:
    p_id = p['id']
    p_name = p['name']
    p_dsmbg = p.get('disambiguation')
    p_as = p['appearance']

    parts = []

    if with_id:
        parts.append(f'[{p_id}]')

    if action:
        parts.append(action)

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
        dotenv = Path(script_dir / '../.env').read_text()
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
