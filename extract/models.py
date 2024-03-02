from typing import Dict, List, Literal, NotRequired, Optional, TypedDict, Union

class _PerformerEntryCommon(TypedDict):
    name: str
    appearance: Optional[str]
    status: NotRequired[str]
    status_url: NotRequired[str]
    disambiguation: NotRequired[str]
    notes: NotRequired[List[str]]

class PerformerEntry(_PerformerEntryCommon):
    id: Optional[str]

class PerformerUpdateEntry(_PerformerEntryCommon):
    id: str
    old_appearance: Optional[str]

AnyPerformerEntry = Union[PerformerEntry, PerformerUpdateEntry]


class ScenePerformersItem(TypedDict):
    studio: Optional[str]
    scene_id: str
    remove: List[PerformerEntry]
    append: List[PerformerEntry]
    parent_studio: NotRequired[str]
    update: NotRequired[List[PerformerUpdateEntry]]
    comment: NotRequired[str]
    user: NotRequired[str]
    submitted: NotRequired[bool]
    done: NotRequired[bool]


SceneChangeFieldType = Literal[
    'title',
    'details',
    'date',
    'studio_id',
    'code',
    'director',
    'duration',
    'image',
    'url',
]

class SceneChangeItem(TypedDict):
    field: SceneChangeFieldType
    new_data: Optional[str]
    correction: Optional[str]
    user: NotRequired[str]
    submitted: NotRequired[bool]
    done: NotRequired[bool]

SceneFixesDict = Dict[str, List[SceneChangeItem]]


class DuplicateScenesItem(TypedDict):
    studio: str
    main_id: str
    duplicates: List[str]
    category: NotRequired[str]
    user: NotRequired[str]


class DuplicatePerformersItem(TypedDict):
    name: str
    main_id: str
    duplicates: List[str]
    notes: NotRequired[List[str]]
    user: NotRequired[str]
    submitted: NotRequired[bool]


class SceneFingerprintsItem(TypedDict):
    algorithm: Literal['phash', 'oshash', 'md5']
    hash: str
    correct_scene_id: Optional[str]
    duration: NotRequired[int]
    user: NotRequired[str]

SceneFingerprintsDict = Dict[str, List[SceneFingerprintsItem]]


class SplitFragment(TypedDict):
    raw: str
    id: Optional[str]
    name: str
    text: NotRequired[str]
    notes: NotRequired[List[str]]
    links: NotRequired[List[str]]
    done: NotRequired[bool]


class PerformersToSplitUpItem(TypedDict):
    name: str
    id: str
    fragments: List[SplitFragment]
    status: NotRequired[str]
    notes: NotRequired[List[str]]
    links: NotRequired[List[str]]
    user: NotRequired[str]


class PerformerURLItem(TypedDict):
    url: str
    name: str
    text: str
    submitted: NotRequired[bool]

PerformerURLsDict = Dict[str, List[PerformerURLItem]]
