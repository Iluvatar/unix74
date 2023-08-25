import datetime
from dataclasses import dataclass

from filesystem.filesystem import FilePermissions, FileType, INode
from user import GID, UID


@dataclass
class DirEnt:
    name: str
    inode: INode  # parent: 'DirEnt'  # children: List['DirEnt']


@dataclass
class Stat:
    permissions: FilePermissions
    fileType: FileType
    owner: UID
    group: GID
    timeCreated: datetime.datetime
    timeModified: datetime.datetime
    deviceNumber: int = -1
    references: int = 1
