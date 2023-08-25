from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum, IntFlag, auto
from typing import Dict

from user import GID, UID


class INodeException(Exception):
    pass


class FilesystemError(Exception):
    pass


class FileType(Enum):
    NONE = auto()
    REGULAR = auto()
    DIRECTORY = auto()
    CHARACTER = auto()
    LINK = auto()
    PIPE = auto()


class Mode(IntFlag):
    READ = 4
    WRITE = 2
    EXEC = 1


class FilePermissions:
    class Entity(Enum):
        OWNER = auto()
        GROUP = auto()
        OTHER = auto()

    class Op(Enum):
        ADD = auto()
        REM = auto()

    def __init__(self, permissions: int):
        self.owner = self.group = self.other = Mode(0)
        self.setPermissions(permissions)

    def setPermissions(self, permissions: int):
        self.owner, self.group, self.other = FilePermissions.parsePermissions(permissions)

    def modifyPermissions(self, entity: Entity, op: Op, mode: Mode):
        if entity == FilePermissions.Entity.OWNER:
            if op == FilePermissions.Op.ADD:
                self.owner |= mode
            else:
                self.owner &= ~mode
        elif entity == FilePermissions.Entity.GROUP:
            if op == FilePermissions.Op.ADD:
                self.group |= mode
            else:
                self.group &= ~mode
        else:
            if op == FilePermissions.Op.ADD:
                self.other |= mode
            else:
                self.other &= ~mode

    @staticmethod
    def parsePermissions(permissions: int) -> (Mode, Mode, Mode):
        otherPermissions = permissions % 10
        groupPermissions = (permissions // 10) % 10
        ownerPermissions = (permissions // 100) % 10
        if not (0 <= otherPermissions < 8 and 0 <= groupPermissions < 8 and 0 <= ownerPermissions < 8):
            raise ValueError(f"Invalid file permissions '{permissions}'")
        return Mode(ownerPermissions), Mode(groupPermissions), Mode(otherPermissions)

    def getPermissionsAsInt(self) -> int:
        return self.owner * 100 + self.group * 10 + self.other

    def copy(self) -> FilePermissions:
        return FilePermissions(self.getPermissionsAsInt())


@dataclass
class INode:
    permissions: FilePermissions
    fileType: FileType
    owner: UID
    group: GID
    timeCreated: datetime.datetime
    timeModified: datetime.datetime
    data: INodeData
    deviceNumber: int = -1
    references: int = 1


class INodeData:
    def __init__(self):
        self.data: str = ""

    def read(self, size: int, offset: int) -> str:
        return self.data[offset:offset + size]

    def write(self, data: str, offset: int) -> int:
        self.data = self.data[:offset] + data
        return len(data)

    def append(self, data: str) -> int:
        self.data += data
        return len(data)

    def size(self) -> int:
        return len(self.data)


class DirectoryData(INodeData):
    def __init__(self, children: Dict[str, INode] | None = None):
        super().__init__()
        if children is None:
            children = {}
        self.children: Dict[str, INode] = children
        self.__makeData()

    def __makeData(self):
        self.data = ""
        for name, inode in self.children.items():
            self.data += f"{name}{id(inode)}"

    def addChildren(self, children: Dict[str, INode]):
        for name, child in children.items():
            self.addChild(name, child)

    def addChild(self, name: str, child: INode):
        self.children[name] = child
        self.__makeData()

    def removeChild(self, name: str):
        try:
            del self.children[name]
        except KeyError:
            raise FileNotFoundError() from None
        self.__makeData()


class RegularFileData(INodeData):
    def __init__(self, data):
        super().__init__()
        self.data = data

    def read(self, size, offset):
        return self.data[offset:offset + size]

    def write(self, data, offset):
        self.data = self.data[:offset] + data

    def append(self, data):
        self.data += data


class SpecialFileData(INodeData):
    def read(self, size, offset):
        raise NotImplementedError()

    def write(self, data, offset):
        raise NotImplementedError()

    def append(self, data):
        raise NotImplementedError()
