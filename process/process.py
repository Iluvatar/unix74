from __future__ import annotations

import typing
from collections.abc import MutableSet
from dataclasses import dataclass, field

from environment import Environment
from filesystem.filesystem import INode
from process.file_descriptor import FD, PID, ProcessFileDescriptor
from process.process_code import ProcessCode
from self_keyed_dict import SelfKeyedDict
from user import GID, UID

if typing.TYPE_CHECKING:
    from unix import Unix


@dataclass
class Process:
    pid: PID
    parent: Process
    command: str
    realUid: UID
    realGid: GID
    currentDir: INode
    env: Environment
    uid: UID | None = None
    gid: GID | None = None
    tty: int = -1
    fdTable: SelfKeyedDict[ProcessFileDescriptor, FD] = field(default_factory=lambda: SelfKeyedDict("id"))
    children: MutableSet[Process] = field(default_factory=set)

    def __post_init__(self):
        if self.uid is None:
            self.uid = self.realUid
        if self.gid is None:
            self.gid = self.realGid

    def claimNextFdNum(self):
        i: FD = FD(0)
        while i in self.fdTable:
            i += 1
        return i

    def __hash__(self) -> int:
        return self.pid

    def __eq__(self, other) -> bool:
        return self.pid == other.pid

    def __str__(self) -> str:
        fds = ",".join([str(fd) for fd in self.fdTable])
        return f"['{self.command}', pid: {self.pid}, owner: {self.uid}, fd: [{fds}]]"


class OsProcess:
    def __init__(self, unix: Unix, process: Process, code: ProcessCode):
        self.unix = unix
        self.process = process
        self.code = code

    def run(self):
        self.code.run()

        # clean up loose fds
        for fd in self.process.fdTable:
            ofd = self.unix.openFileTable[fd.openFd.id]
            ofd.refCount -= 1
            if ofd.refCount == 0:
                self.unix.openFileTable.remove(ofd.id)
