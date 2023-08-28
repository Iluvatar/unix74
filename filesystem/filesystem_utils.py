import datetime
from dataclasses import dataclass
from enum import Enum, auto

from filesystem.filesystem import FilePermissions, FileType, INode
from user import GID, UID


@dataclass
class DirEnt:
    name: str
    inode: INode  # parent: 'DirEnt'  # children: List['DirEnt']


@dataclass
class Stat:
    inode: INode
    permissions: FilePermissions
    fileType: FileType
    owner: UID
    group: GID
    timeCreated: datetime.datetime
    timeModified: datetime.datetime
    deviceNumber: int = -1
    references: int = 1


class INodeOperation(Enum):
    GET = auto()
    CREATE = auto()
    DELETE = auto()
