from __future__ import annotations

import bz2
import datetime
import hashlib
import inspect
import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, NewType, TYPE_CHECKING, Type
from uuid import UUID

# from filesystem.flags import FileType, Mode, SetId
from filesystem.flags import FileType, Mode, SetId
from kernel.errors import Errno, KernelError
from process.process_code import ProcessCode
from self_keyed_dict import SelfKeyedDict
from user import GID, UID

if TYPE_CHECKING:
    from kernel.unix import Unix

INumber = NewType("INumber", int)


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
        if permissions < 0:
            permissions = 0
        else:
            permissions %= 8 ** 4
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
    filesystemId: UUID
    isMount: bool = False
    deviceNumber: int = -1
    references: int = 1

    def __str__(self):
        return f"[INode {str(self.filesystemId)[:4]}.{self.iNumber} {self.permissions}, {self.fileType}, {self.owner}:{self.group}]"


class INodeData:
    def __init__(self):
        self._data: str = ""

    def read(self, size: int, offset: int) -> str:
        return self._data[offset:offset + size]

    def write(self, data: str, offset: int) -> int:
        self._data = self._data[:offset] + data
        return len(data)

    def append(self, data: str) -> int:
        self._data += data
        return len(data)

    def trunc(self) -> int:
        self._data = ""
        return 0

    def size(self) -> int:
        return len(self._data)


class DirectoryData(INodeData):
    def __init__(self, children: Dict[str, INumber] | None = None):
        super().__init__()
        if children is None:
            children = {}
        self.children: Dict[str, INumber] = children
        self.__makeData()

    def trunc(self):
        raise KernelError("", Errno.EISDIR)

    def __makeData(self) -> None:
        self._data = ""
        for name, inumber in self.children.items():
            self._data += f"{name}{inumber}"

    def addChildren(self, children: Dict[str, INumber]) -> None:
        for name, inumber in children.items():
            self.addChild(name, inumber)

    def addChild(self, name: str, inumber: INumber) -> None:
        if name == "":
            raise KernelError("", Errno.ENOENT)
        self.children[name] = inumber
        self.__makeData()

    def removeChild(self, name: str) -> None:
        try:
            del self.children[name]
        except KeyError:
            raise KernelError("", Errno.ENOENT)
        self.__makeData()


class RegularFileData(INodeData):
    def __init__(self, data):
        super().__init__()
        self._data = data


class SpecialFileData(INodeData):
    def __init__(self, unix: Unix):
        super().__init__()
        self.unix = unix

    def read(self, size, offset):
        pass

    def write(self, data, offset):
        pass

    def append(self, data):
        pass

    def trunc(self):
        pass


class BinaryFileData(INodeData):
    def __init__(self, processCode: Type[ProcessCode]):
        super().__init__()
        self.processCode: Type[ProcessCode] = processCode
        code = inspect.getsource(self.processCode)
        self._data = self.mangleData(code)
        self.__hash = hashlib.sha256(self._data.encode("utf-8")).digest()

    def mangleData(self, data: str) -> str:
        return bz2.compress(data.encode("utf-16")).decode("ascii", errors="replace").replace("\ufffd", "?")

    def isComplete(self) -> bool:
        return hashlib.sha256(self._data.encode("utf-8")).digest() == self.__hash

    def isEmpty(self) -> bool:
        return self.size() == 0


class Filesystem:
    def __init__(self, uuid: UUID, covered: INode | None = None):
        self.uuid = uuid
        self.covered = covered
        self.inodes: SelfKeyedDict[INode, INumber] = SelfKeyedDict("iNumber")
        self.rootINum: INumber | None = None
        self.nextINumber: INumber = INumber(1)
        self.blockSize: int = 512

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

    def size(self):
        return sum([math.ceil(i.data.size() / self.blockSize) * self.blockSize for i in self.inodes])

    def __len__(self):
        return self.size()

    def __str__(self):
        return f"[{self.uuid} {len(self)} bytes]"

    def __repr__(self):
        return self.__str__()
