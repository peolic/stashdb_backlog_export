# coding: utf-8
from typing import Dict, Generic, TypeVar


T = TypeVar('T')

class InterfaceBase(Generic[T]):

    def __init__(self):
        self._sheets: Dict[int, T] = {}

    def get_sheet(self, sheet_id: int):
        return self._sheets[sheet_id]
