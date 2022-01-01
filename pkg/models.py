from typing import Dict, List, Literal, Optional, TypedDict, Union

class _PerformerEntryOptional(TypedDict, total=False):
    status: str
    status_url: str
    disambiguation: str
    notes: List[str]

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
    user: str

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

class _SceneChangeItemOptional(TypedDict, total=False):
    user: str

class SceneChangeItem(_SceneChangeItemOptional, TypedDict):
    field: SceneChangeFieldType
    new_data: Optional[str]
    correction: Optional[str]

SceneFixesDict = Dict[str, List[SceneChangeItem]]


class _DuplicateScenesItemOptional(TypedDict, total=False):
    category: str
    user: str

class DuplicateScenesItem(_DuplicateScenesItemOptional, TypedDict):
    studio: str
    main_id: str
    duplicates: List[str]


class _DuplicatePerformersItemOptional(TypedDict, total=False):
    user: str

class DuplicatePerformersItem(_DuplicatePerformersItemOptional, TypedDict):
    name: str
    main_id: str
    duplicates: List[str]


class _SceneFingerprintsItemOptional(TypedDict, total=False):
    user: str

class SceneFingerprintsItem(_SceneFingerprintsItemOptional, TypedDict):
    algorithm: str
    hash: str
    correct_scene_id: Optional[str]

SceneFingerprintsDict = Dict[str, List[SceneFingerprintsItem]]


class _PerformersToSplitUpItemOptional(TypedDict, total=False):
    user: str

class PerformersToSplitUpItem(_PerformersToSplitUpItemOptional, TypedDict):
    name: str
    main_id: str
