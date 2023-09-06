import datetime
from dataclasses import dataclass
from enum import Enum, auto
from uuid import UUID

from filesystem.filesystem import FilePermissions, INumber
from filesystem.flags import FileType
from user import GID, UID


@dataclass
class Mount:
    mountedFsId: UUID
    mountedOnFsId: UUID
    mountedOnINumber: INumber

    @staticmethod
    def __short(uuid: UUID):
        return str(uuid)[:4]

    def __str__(self):
        return f"{self.__short(self.mountedOnFsId)}.{self.mountedOnINumber} -> {self.__short(self.mountedFsId)}"


@dataclass
class Dentry:
    name: str
    iNumber: INumber
    filesystemId: UUID


@dataclass
class Stat:
    iNumber: INumber
    permissions: FilePermissions
    fileType: FileType
    owner: UID
    group: GID
    size: int
    timeCreated: datetime.datetime
    timeModified: datetime.datetime
    filesystemId: UUID
    deviceNumber: int = -1
    references: int = 1


class INodeOperation(Enum):
    GET = auto()
    CREATE = auto()
    CREATE_EXCLUSIVE = auto()
    PARENT = auto()
