# coding: utf-8
import json
from pathlib import Path

class BacklogBase:
    def __init__(self) -> None:
        self.data = []

    def sort(self):
        if sort_key := getattr(self, 'sort_key', None):
            self.data.sort(key=sort_key)

    def write(self, target: Path):
        self.sort()

        target.write_bytes(
            json.dumps(self.data, indent=2).encode('utf-8')
        )

    def __str__(self):
        return '\n'.join(json.dumps(item) for item in self.data)

    def __len__(self):
        return len(self.data)
