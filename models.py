from typing import List, Optional, TypedDict

class _PerformerEntryOptional(TypedDict, total=False):
    status: Optional[str]
    disambiguation: str

class PerformerEntry(_PerformerEntryOptional, TypedDict):
    id: Optional[str]
    name: str
    appearance: Optional[str]

class PerformerUpdateEntry(PerformerEntry, TypedDict):
    old_appearance: Optional[str]


class _ScenePerformersItemOptional(TypedDict, total=False):
    parent_studio: str

class ScenePerformersItem(_ScenePerformersItemOptional, TypedDict):
    studio: Optional[str]
    scene_id: str
    remove: List[PerformerEntry]
    append: List[PerformerEntry]
    update: List[PerformerUpdateEntry]


class DuplicateScenesItem(TypedDict):
    studio: str
    main_id: str
    duplicates: List[str]


class DuplicatePerformersItem(TypedDict):
    name: str
    main_id: str
    duplicates: List[str]
