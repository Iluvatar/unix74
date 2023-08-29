import datetime
from dataclasses import dataclass
from enum import Enum, auto

from filesystem.filesystem import FilePermissions, FileType, INumber
from user import GID, UID


@dataclass
class DirEnt:
    name: str
    iNumber: INumber  # parent: 'DirEnt'  # children: List['DirEnt']


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
    deviceNumber: int = -1
    references: int = 1


class INodeOperation(Enum):
    GET = auto()
    CREATE = auto()
    DELETE = auto()
