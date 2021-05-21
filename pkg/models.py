from typing import List, Optional, TypedDict, Union

class _PerformerEntryOptional(TypedDict, total=False):
    status: Optional[str]
    disambiguation: str

class _PerformerEntryCommon(_PerformerEntryOptional, TypedDict):
    name: str
    appearance: Optional[str]

class PerformerEntry(_PerformerEntryCommon, TypedDict):
    id: Optional[str]

class PerformerUpdateEntry(_PerformerEntryCommon, TypedDict):
    id: str
    old_appearance: Optional[str]

AnyPerformerEntry = Union[PerformerEntry, PerformerUpdateEntry]


class _ScenePerformersItemOptional(TypedDict, total=False):
    parent_studio: str
    update: List[PerformerUpdateEntry]

class ScenePerformersItem(_ScenePerformersItemOptional, TypedDict):
    studio: Optional[str]
    scene_id: str
    remove: List[PerformerEntry]
    append: List[PerformerEntry]


class DuplicateScenesItem(TypedDict):
    studio: str
    main_id: str
    duplicates: List[str]


class DuplicatePerformersItem(TypedDict):
    name: str
    main_id: str
    duplicates: List[str]
