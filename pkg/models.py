from typing import Dict, List, Literal, Optional, TypedDict, Union

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
    comment: str

class ScenePerformersItem(_ScenePerformersItemOptional, TypedDict):
    studio: Optional[str]
    scene_id: str
    remove: List[PerformerEntry]
    append: List[PerformerEntry]


SceneChangeFieldType = Literal[
    'title',
    'details',
    'date',
    'studio_id',
    'director',
    'duration',
    'image',
    'url',
]

class SceneChangeItem(TypedDict):
    field: SceneChangeFieldType
    new_data: Optional[str]
    correction: Optional[str]

SceneFixesDict = Dict[str, List[SceneChangeItem]]


class DuplicateScenesItem(TypedDict):
    studio: str
    main_id: str
    duplicates: List[str]


class DuplicatePerformersItem(TypedDict):
    name: str
    main_id: str
    duplicates: List[str]


class SceneFingerprintsItem(TypedDict):
    algorithm: str
    hash: str
    correct_scene_id: Optional[str]

SceneFingerprintsDict = Dict[str, List[SceneFingerprintsItem]]


class PerformersToSplitUpItem(TypedDict):
    name: str
    main_id: str
