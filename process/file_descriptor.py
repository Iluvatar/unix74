from dataclasses import dataclass
from enum import Enum, Flag, auto
from typing import NewType

from filesystem.filesystem import INode

PID = NewType("PID", int)
FD = NewType("FD", int)
OFD = NewType("OFD", int)


class BadFileNumberError(Exception):
    pass


class FileMode(Flag):
    READ = auto()
    WRITE = auto()
    READ_WRITE = READ | WRITE
    APPEND = auto()
    CREATE = auto()
    TRUNCATE = auto()


class SeekFrom(Enum):
    SET = auto()
    CURRENT = auto()
    END = auto()


@dataclass
class OpenFileDescriptor:
    id: OFD
    mode: FileMode
    file: INode
    refCount: int = 1
    offset: int = 0

    def __str__(self):
        return f"[id: {self.id}, mode: {self.mode}, inode: {self.file.inumber}, refs: {self.refCount}, offset: {self.offset}]"


@dataclass
class ProcessFileDescriptor:
    id: FD
    openFd: OpenFileDescriptor

    def __str__(self):
        return f"{{id: {self.id}, openFd: {self.openFd.id}}}"
