from typing import List

from .models import AnyPerformerEntry, ScenePerformersItem


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
