from __future__ import annotations

import datetime
from collections.abc import MutableSet, Generator
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, ClassVar


class INodeException(Exception):
    pass


class NoSuchFileException(INodeException):
    pass


class FileType(Enum):
    NONE = 0
    FILE = 1
    DIRECTORY = 2
    SPECIAL = 3
    LINK = 4


class FilePermissions:
    def __init__(self, permissions: int):
        self.owner = self.group = self.other = 0
        self.setPermissions(permissions)

    def setPermissions(self, permissions: int):
        self.owner, self.group, self.other = FilePermissions.parsePermissions(permissions)

    @staticmethod
    def parsePermissions(permissions: int):
        otherPermissions = permissions % 10
        groupPermissions = (permissions // 10) % 10
        ownerPermissions = (permissions // 100) % 10
        if not (0 <= otherPermissions < 8 and 0 <= groupPermissions < 8 and 0 <= ownerPermissions < 8):
            raise ValueError(f"Invalid file permissions '{permissions}'")
        return ownerPermissions, groupPermissions, otherPermissions


class File:
    def read(self) -> Generator[str, None, None]:
        raise NotImplementedError()

    def write(self, data: str) -> None:
        raise NotImplementedError()

    def append(self, data: str) -> None:
        raise NotImplementedError()


class RegularFile(File):
    def __init__(self, data: str):
        self.data = data

    def read(self):
        for line in self.data.split("\n"):
            yield line

    def write(self, data):
        self.data = data

    def append(self, data):
        self.data += data


class SpecialFile(File):
    def read(self):
        raise NotImplementedError()

    def write(self, data):
        raise NotImplementedError()

    def append(self, data):
        raise NotImplementedError()


class DevNull(SpecialFile):
    def read(self):
        yield from ()

    def write(self, data):
        pass

    def append(self, data):
        pass


class DevConsole(SpecialFile):
    def read(self):
        try:
            while True:
                yield input() + "\n"
        except EOFError:
            pass

    def write(self, data):
        print(data)

    def append(self, data):
        print(data)


@dataclass
class INode:
    parent: INode
    name: str
    permissions: FilePermissions
    owner: int
    group: int
    timeCreated: datetime.datetime
    timeModified: datetime.datetime

    filetype: ClassVar[FileType] = FileType.NONE

    def __getPath(self) -> str:
        if self.parent == self:
            return ""
        return self.parent.__getPath() + "/" + self.name

    def getCanonicalPath(self) -> str:
        if self.parent == self:
            return "/"
        return self.__getPath()


@dataclass
class INodeFile(INode):
    filetype: ClassVar[FileType] = FileType.FILE
    file: File


@dataclass
class INodeDirectory(INode):
    filetype: ClassVar[FileType] = FileType.DIRECTORY
    children: MutableSet[INode] = field(default_factory=set)

    __childrenDict: Dict[str, INode] = field(init=False, repr=False)

    def __post_init__(self):
        self.rehashChildren()

    def rehashChildren(self) -> None:
        self.__childrenDict = {child.name: child for child in self.children}

    def setChildren(self, children: MutableSet[INode]) -> None:
        self.children = children
        self.rehashChildren()

    def addChild(self, child: INode) -> None:
        self.children.add(child)
        self.rehashChildren()

    def getChild(self, name: str) -> INode:
        try:
            return self.__childrenDict[name]
        except KeyError:
            raise NoSuchFileException(f"{name}: No such file or directory") from None

    def getChildren(self) -> MutableSet[INode]:
        return self.children

    def getINodeFromRelativePath(self, path: str) -> INode:
        parts = path.split("/")
        currentNode = self

        for part in parts:
            if part == "" or part == ".":
                continue
            elif part == "..":
                currentNode = currentNode.parent
            else:
                currentNode = currentNode.getChild(part)

        return currentNode


class INodeSpecialFile(INode):
    filetype = FileType.SPECIAL
    fileHandler: SpecialFile
