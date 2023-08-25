from __future__ import annotations

from collections.abc import Generator
from typing import Generic, TypeVar, Dict

Type = TypeVar("Type")
KeyType = TypeVar("KeyType")


class SelfKeyedDict(Generic[Type, KeyType]):
    def __init__(self, key: str):
        self.backingDict: Dict[KeyType, Type] = {}
        self.key: str = key

    def __len__(self) -> int:
        return len(self.backingDict)

    def __contains__(self, item: Type | KeyType) -> bool:
        if type(item) == Type:
            key: KeyType = getattr(item, self.key)
        else:
            key: KeyType = item
        return key in self.backingDict

    def __getitem__(self, keyValue: KeyType) -> Type:
        return self.backingDict[keyValue]

    def __setitem__(self, key: KeyType, value: Type) -> None:
        raise Exception("Use add(item) to add values")

    def __iter__(self) -> Generator[Type, None, None]:
        yield from self.backingDict.values()

    def add(self, item: Type) -> None:
        key: KeyType = getattr(item, self.key)
        self.backingDict[key] = item

    def remove(self, item: Type | KeyType) -> None:
        if type(item) == Type:
            key: KeyType = getattr(item, self.key)
        else:
            key: KeyType = item
        del self.backingDict[key]

    def clear(self) -> None:
        self.backingDict.clear()

    def __str__(self) -> str:
        return str(self.backingDict)
