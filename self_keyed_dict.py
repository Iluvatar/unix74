from __future__ import annotations

from collections.abc import Generator
from typing import Dict, Generic, TypeVar

Type = TypeVar("Type")
KeyType = TypeVar("KeyType")


class SelfKeyedDict(Generic[Type, KeyType]):
    def __init__(self, key: str):
        self.backingDict: Dict[KeyType, Type] = {}
        self.key: str = key

    def __len__(self) -> int:
        return len(self.backingDict)

    def __contains__(self, key: KeyType) -> bool:
        return key in self.backingDict

    def __getitem__(self, key: KeyType) -> Type:
        return self.backingDict[key]

    def __setitem__(self, key: KeyType, value: Type) -> None:
        raise Exception("Use add(item) to add values")

    def __iter__(self) -> Generator[Type, None, None]:
        yield from self.backingDict.values()

    def add(self, item: Type) -> None:
        key: KeyType = getattr(item, self.key)
        self.backingDict[key] = item

    def get(self, key: KeyType, default=None):
        return self.backingDict.get(key, default)

    def remove(self, key: KeyType) -> None:
        del self.backingDict[key]

    def clear(self) -> None:
        self.backingDict.clear()

    def __str__(self) -> str:
        return str(self.backingDict)
