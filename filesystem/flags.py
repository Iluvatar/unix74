from enum import Enum, IntFlag, auto


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
