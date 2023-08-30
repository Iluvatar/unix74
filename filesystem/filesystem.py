from __future__ import annotations

import datetime
import typing
from dataclasses import dataclass
from enum import Enum, IntFlag, auto
from typing import Dict

from self_keyed_dict import SelfKeyedDict
from user import GID, UID

if typing.TYPE_CHECKING:
    from unix import Unix


class INodeException(Exception):
    pass


class FilesystemError(Exception):
    pass


INumber = typing.NewType("INumber", int)


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
    ALL = READ | WRITE | EXEC


class SetId(IntFlag):
    SET_UID = 4
    SET_GID = 2
    STICKY = 1
    ALL = SET_UID | SET_GID | STICKY


class FilePermissions:
    class PermGroup(Enum):
        HIGH = auto()
        OWNER = auto()
        GROUP = auto()
        OTHER = auto()

    class Op(Enum):
        ADD = auto()
        REM = auto()

    def __init__(self, permissions: int):
        self.high = SetId(0)
        self.owner = self.group = self.other = Mode(0)
        self.setPermissions(permissions)

    def __str__(self) -> str:
        return f"{self.high}{self.owner}{self.group}{self.other}"

    def __repr__(self) -> str:
        return self.__str__()

    def setPermissions(self, permissions: int):
        self.high, self.owner, self.group, self.other = FilePermissions.parsePermissions(permissions)

    def modifyPermissions(self, entity: PermGroup, op: Op, mode: Mode | SetId):
        if entity == FilePermissions.PermGroup.HIGH:
            if op == FilePermissions.Op.ADD:
                self.high |= mode
            else:
                self.high &= ~mode
        elif entity == FilePermissions.PermGroup.OWNER:
            if op == FilePermissions.Op.ADD:
                self.owner |= mode
            else:
                self.owner &= ~mode
        elif entity == FilePermissions.PermGroup.GROUP:
            if op == FilePermissions.Op.ADD:
                self.group |= mode
            else:
                self.group &= ~mode
        elif entity == FilePermissions.PermGroup.OTHER:
            if op == FilePermissions.Op.ADD:
                self.other |= mode
            else:
                self.other &= ~mode
        else:
            raise ValueError(f"Invalid permissions group {entity}")

    @staticmethod
    def parsePermissions(permissions: int) -> (SetId, Mode, Mode, Mode):
        if permissions < 0 or permissions >= 8 ** 4:
            raise ValueError(f"Invalid file permissions '{permissions}'")
        otherPermissions = permissions % 8
        groupPermissions = (permissions // 8) % 8
        ownerPermissions = (permissions // 8 ** 2) % 8
        highPermissions = (permissions // 8 ** 3) % 8
        return SetId(highPermissions), Mode(ownerPermissions), Mode(groupPermissions), Mode(otherPermissions)

    def getPermissionsAsInt(self) -> int:
        return self.high * 8 ** 3 + self.owner * 8 ** 2 + self.group * 8 + self.other

    def copy(self) -> FilePermissions:
        return FilePermissions(self.getPermissionsAsInt())


@dataclass
class INode:
    iNumber: INumber
    permissions: FilePermissions
    fileType: FileType
    owner: UID
    group: GID
    timeCreated: datetime.datetime
    timeModified: datetime.datetime
    data: INodeData
    deviceNumber: int = -1
    references: int = 1

    def __str__(self):
        return f"[INode {self.permissions}, {self.fileType}, {self.owner}:{self.group}]"

    def __repr__(self):
        return self.__str__()


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
    def __init__(self, children: Dict[str, INumber] | None = None):
        super().__init__()
        if children is None:
            children = {}
        self.children: Dict[str, INumber] = children
        self.__makeData()

    def __makeData(self):
        self.data = ""
        for name, inumber in self.children.items():
            self.data += f"{name}{inumber}"

    def addChildren(self, children: Dict[str, INumber]):
        for name, inumber in children.items():
            self.addChild(name, inumber)

    def addChild(self, name: str, inumber: INumber):
        if name == "":
            raise FilesystemError("File names cannot be empty")
        self.children[name] = inumber
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
    def __init__(self, unix: Unix):
        super().__init__()
        self.unix = unix

    def read(self, size, offset):
        raise NotImplementedError()

    def write(self, data, offset):
        raise NotImplementedError()

    def append(self, data):
        raise NotImplementedError()


class Filesystem:
    def __init__(self):
        self.inodes: SelfKeyedDict[INode, INumber] = SelfKeyedDict("iNumber")
        self.rootINum: INumber | None = None
        self.nextINumber: INumber = INumber(1)

    def claimNextINumber(self) -> INumber:
        iNumber = self.nextINumber
        if self.rootINum is None:
            self.rootINum = iNumber
        self.nextINumber += 1
        return iNumber

    def root(self) -> INode | None:
        if self.rootINum:
            return self.inodes[self.rootINum]
        return None

    def add(self, inode: INode):
        self.inodes.add(inode)
        return inode

    def __len__(self):
        return len(self.inodes)
