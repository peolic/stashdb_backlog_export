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
    submitted: bool
    done: bool

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
    submitted: bool
    done: bool

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
    notes: List[str]
    user: str

class DuplicatePerformersItem(_DuplicatePerformersItemOptional, TypedDict):
    name: str
    main_id: str
    duplicates: List[str]


class _SceneFingerprintsItemOptional(TypedDict, total=False):
    user: str

class SceneFingerprintsItem(_SceneFingerprintsItemOptional, TypedDict):
    algorithm: Literal['phash', 'oshash', 'md5', 'duration']
    hash: str
    correct_scene_id: Optional[str]

SceneFingerprintsDict = Dict[str, List[SceneFingerprintsItem]]


class _SplitShardOptional(TypedDict, total=False):
    text: str
    notes: List[str]
    links: List[str]

class SplitShard(_SplitShardOptional, TypedDict):
    raw: str
    id: Optional[str]
    name: str

class _PerformersToSplitUpItemOptional(TypedDict, total=False):
    user: str
    notes: List[str]

class PerformersToSplitUpItem(_PerformersToSplitUpItemOptional, TypedDict):
    name: str
    id: str
    shards: List[SplitShard]

class PerformerURLItem(TypedDict):
    url: str
    name: str

PerformerURLsDict = Dict[str, List[PerformerURLItem]]
